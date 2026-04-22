---
layout: article
title: 基于 MCP 的 C++ 静态分析工具封装实践
date: 2026-03-25 16:00:00 +0800
tags:
  - agents
  - mcp
  - cppcheck
  - llm
---

## 问题背景

C++ 静态分析工具如 cppcheck 在实际使用中存在明显的使用门槛：开发者需要记忆复杂的命令行参数、手动配置项目路径、处理大量冗余输出信息。这些问题在将静态分析工具集成到 AI 辅助开发工作流时尤为突出。

cppcheck 的原始输出通常包含数千行信息，其中大量为 information 级别的提示和重复性警告（如 Qt 宏相关的误报）。这些未经过滤的输出会迅速占满大语言模型的上下文窗口，导致对话中断或关键信息丢失。更重要的是，直接通过 bash 调用命令行工具无法实现智能化的项目感知和输出优化。

本文介绍一种基于 Model Context Protocol (MCP) 的解决方案，通过对 cppcheck 进行智能封装，实现了项目配置自动检测、输出信息清洗和标准化接口暴露，使静态分析能力无缝融入 AI Agent 的工作流。

这里先贴一下最终的调用效果：

![cc_res](https://noonafter.cn/assets/images/posts/2026-03-27-cppcheck-mcp-wrapper/cc_result.png)

## MCP 封装的核心价值

### 项目感知能力

传统的命令行调用方式要求用户明确指定所有参数。MCP 插件通过实现项目上下文检测机制，能够自动完成以下工作：

- 向上遍历目录树定位项目根目录（通过 `.git` 或 `compile_commands.json` 标识）
- 自动检测并应用 `compile_commands.json` 编译数据库
- 识别项目文件类型（`.sln`、`.vcxproj`、`.cbp`）并选择合适的分析策略
- 查找并应用 `.cppcheck` 配置文件

这种项目感知能力显著提升了工具的针对性。例如，当检测到 `compile_commands.json` 时，插件会自动使用 `--project` 参数，使 cppcheck 获得完整的编译上下文，通过发现项目根目录，还能自动添加上一些常用的头文件目录，从而减少因头文件路径缺失导致的误报，。

### 上下文管理与输出优化

符合 Harness 工程原则的关键在于为大语言模型提供高质量的工作环境。MCP 插件在输出阶段执行以下优化：

**XML 结构清洗**：移除 `verbose` 属性（包含冗长的详细说明）和 `column` 属性（列号信息对 AI 分析价值有限），仅保留核心字段：`id`（错误类型）、`severity`（严重程度）、`msg`（错误描述）、`file`（文件路径）、`line`（行号）。

**信息密度控制**：通过检查模式参数控制输出规模。`quick` 模式仅启用 `--enable=warning`，聚焦于高价值警告；`full` 模式启用 `--enable=all`，适用于深度审查场景。

清洗后的输出示例：

```xml
<?xml version="1.0" encoding="UTF-8"?>
<results version="2">
  <cppcheck version="2.20.0"/>
  <errors>
    <error id="nullPointer" severity="error" msg="Null pointer dereference">
      <location file="src/main.cpp" line="42"/>
    </error>
  </errors>
</results>
```

这种结构化输出使大语言模型能够高效解析错误信息，并在后续步骤中精确定位问题代码。

### 标准化接口与工作流集成

MCP 协议通过 JSON-RPC 提供统一的工具调用接口，使静态分析能力能够被不同的 AI Agent 平台无缝集成。插件暴露的工具函数包括：

**check_code**：执行代码检查，接收目标路径和检查模式参数，返回清洗后的 XML 结果。

**get_project_context**：返回项目环境信息的 JSON 表示，用于调试和验证项目检测逻辑。

这种标准化接口支持构建完整的代码质量保障闭环：AI Agent 调用检查工具 → 解析 XML 错误报告 → 读取源文件定位问题 → 分析错误原因 → 生成修复方案 → 应用代码修改 → 再次检查验证。整个流程可在用户监督下自动执行，显著提升开发效率。

## 技术实现架构

### 模块设计

项目采用职责分离的模块化设计，核心模块包括：

**project_detector.py**：实现 `ProjectContext` 类，负责项目环境检测。初始化时接收目标路径，通过 `_find_project_root()` 方法向上遍历目录树，识别 `.git` 或 `compile_commands.json` 作为项目根标识。`_find_file()` 方法在项目根目录查找配置文件，`to_dict()` 方法将检测结果序列化为字典格式供后续使用。

**cppcheck_runner.py**：实现 `CppcheckRunner` 类，封装 cppcheck 的执行逻辑。`_build_command()` 方法根据项目上下文和检查模式构建命令行参数。命令构建遵循以下优先级：如果指定了配置文件则使用 `--project <config_file>`；否则若目标本身是项目文件则使用 `--project <target_path>`；否则若检测到 `compile_commands.json` 则使用 `--project <compile_commands.json>`；最后才直接分析目标路径。`_clean_xml()` 方法通过 XML 解析移除冗余属性。

**server.py**：基于 FastMCP 框架实现 MCP 服务器。使用 `@mcp.tool()` 装饰器将 Python 函数注册为 MCP 工具，FastMCP 自动生成 JSON Schema 并处理协议层通信。`mcp.run()` 启动 stdio 服务器，通过标准输入输出与客户端进行 JSON-RPC 通信。

### 执行流程

当 AI Agent 调用 `check_code` 工具时，执行流程如下：

1. MCP 客户端通过 JSON-RPC 发送工具调用请求
2. FastMCP 服务器解析请求参数，调用 `check_code()` 函数
3. 创建 `ProjectContext` 对象，执行项目环境检测
4. 创建 `CppcheckRunner` 对象，根据检测结果构建 cppcheck 命令
5. 通过 `subprocess.run()` 执行 cppcheck，捕获 stderr 输出（cppcheck 将 XML 结果输出到 stderr）
6. 解析 XML 输出，移除 `verbose` 和 `column` 属性
7. 将清洗后的 XML 字符串封装为 MCP 响应返回客户端

整个过程对 AI Agent 透明，Agent 只需提供文件路径和检查模式，即可获得结构化的分析结果。

## MCP 协议基础

### 协议定位

Model Context Protocol 是一个标准化协议，用于规范应用程序向大语言模型提供上下文的方式。MCP 服务器通过 stdio 或 HTTP 与客户端通信，暴露三种资源类型：

- **Tools**：可调用的函数，接收结构化参数并返回结果
- **Resources**：静态或动态的数据源（如文件、数据库查询结果）
- **Prompts**：预定义的提示词模板

本项目使用 Tools 类型，将 cppcheck 的能力封装为可被 AI Agent 调用的函数。

### FastMCP 开发框架

FastMCP 是 MCP 协议的高层封装，简化了服务器开发流程。相比底层 Server API，FastMCP 适用于业务逻辑实现场景，自动处理协议细节：

```python
from mcp import FastMCP

mcp = FastMCP("cppcheck")

@mcp.tool()
def check_code(target_path: str, mode: str = "quick") -> str:
    """检查 C++ 代码"""
    context = ProjectContext(target_path)
    runner = CppcheckRunner(context)
    return runner.run(mode)
```

装饰器自动生成工具的 JSON Schema，定义参数类型和描述。`mcp.run()` 启动异步服务器，监听 stdin 并通过 stdout 返回响应。

底层 Server API 适用于需要实现复杂协议逻辑的场景，如多用户服务、限流控制、身份隔离等。对于单纯的工具封装需求，FastMCP 提供了更简洁的开发体验。

### 调试方法

MCP 插件开发的调试分为两个阶段：

**本地脚本调试**：直接导入模块并调用函数，验证业务逻辑正确性。

```python
from mcp_cppcheck.project_detector import ProjectContext
from mcp_cppcheck.cppcheck_runner import CppcheckRunner

context = ProjectContext("/path/to/code.cpp")
print(context.to_dict())
runner = CppcheckRunner(context)
result = runner.run("quick")
print(result)
```

**协议层调试**：使用 MCP Inspector 工具测试完整的协议交互。

```bash
npx @modelcontextprotocol/inspector uv run python -m mcp_cppcheck
```

Inspector 提供 Web 界面，可视化展示工具列表、发送调用请求、查看响应结果，验证 JSON-RPC 通信是否正常。

建议先完成本地调试，确认业务逻辑无误后再进行协议层测试，最后集成到 AI Agent 平台。

## 项目实现细节

### 项目结构

```
mcp_cppcheck/
├── src/mcp_cppcheck/
│   ├── __init__.py          # 包初始化
│   ├── __main__.py          # 程序入口
│   ├── server.py            # MCP 服务器和工具定义
│   ├── project_detector.py  # 项目配置检测
│   └── cppcheck_runner.py   # cppcheck 执行和输出清洗
├── pyproject.toml           # 项目配置
├── README.md                # 使用说明
└── test_local.py            # 本地测试脚本
```

### 项目检测逻辑

`ProjectContext` 类的核心方法 `_find_project_root()` 实现了向上查找逻辑：

```python
def _find_project_root(self):
    current = self.target_path.parent if self.target_path.is_file() else self.target_path
    while current != current.parent:
        if (current / ".git").exists() or (current / "compile_commands.json").exists():
            return current
        current = current.parent
    return None
```

从目标路径开始，逐级向上遍历父目录，直到找到包含 `.git` 或 `compile_commands.json` 的目录。这种设计使插件能够在项目的任意子目录或文件上工作，自动定位项目根目录。

`_is_project_file()` 方法通过文件扩展名判断目标是否为项目文件：

```python
def _is_project_file(self):
    if not self.target_path.is_file():
        return False
    return self.target_path.suffix in [".sln", ".vcxproj", ".cbp"]
```

Visual Studio 解决方案文件（`.sln`）、项目文件（`.vcxproj`）和 Code::Blocks 项目文件（`.cbp`）会被识别为项目文件，触发 `--project` 参数的使用。

### 命令构建策略

`CppcheckRunner` 的 `_build_command()` 方法实现了智能的参数选择逻辑：

```python
def _build_command(self, mode, config_file):
    cmd = ["cppcheck", "--xml", "--xml-version=2"]

    # 根据模式添加检查级别
    if mode == "full":
        cmd.append("--enable=all")
    else:
        cmd.append("--enable=warning")

    # 选择输入方式（优先级递减）
    if  self.context.is_project_file:
        cmd.extend(["--project", str(self.context.target_path)])
    elif self.context.compile_commands:
        cmd.extend(["--project", self.context.compile_commands])
    else:
        cmd.append(str(self.context.target_path))

    return cmd
```

这种优先级设计确保了最佳的分析效果：显式指定的配置文件优先级最高，其次是项目文件本身，再次是自动检测到的编译数据库，最后才是直接分析目标路径。

### XML 清洗实现

`_clean_xml()` 方法通过 XML 解析和重构移除冗余属性：

```python
def _clean_xml(self, xml_output):
    root = ET.fromstring(xml_output)
    for error in root.findall(".//error"):
        error.attrib.pop("verbose", None)
        for location in error.findall("location"):
            location.attrib.pop("column", None)
    return ET.tostring(root, encoding="unicode")
```

解析 XML 字符串为 DOM 树，遍历所有 `<error>` 元素移除 `verbose` 属性，遍历所有 `<location>` 元素移除 `column` 属性，最后序列化回字符串。这种处理保持了 XML 结构的完整性，仅精简了冗余信息。

## 集成与使用

### 安装部署

项目使用 uv 包管理器进行依赖管理和安装：

```bash
uv pip install -e .
```

前置要求包括 Python 3.10 及以上版本，以及系统中已安装的 cppcheck 工具。Windows 平台需要额外安装 `pywin32` 库以支持路径处理。

### Agent 平台集成

**Cherry Studio 集成**：点击设置 -> MCP 服务器 -> 快速创建。具体配置如下图所示，也可以选择从json导入

![cherry_config](https://noonafter.cn/assets/images/posts/2026-03-27-cppcheck-mcp-wrapper/cherry_mcp_config.png)

```json
{
  "mcpServers": {
    "cppcheck": {
      "command": "uv",
      "args": [
        "--directory",
        "/path/to/mcp_cppcheck",
        "run",
        "-m",
        "mcp_cppcheck"
      ]
    }
  }
}
```

**Claude Code 集成**：在 `.claude/mcp.json` 中添加配置，或使用命令行工具：

```bash
claude mcp add mcpServer "uv --directory /path/to/server run -m mcp_cppcheck" --scope user
```

配置完成后，AI Agent 可通过工具调用接口使用静态分析能力。--scope user表示添加的工具为用户级配置，否则仅在当前项目中生效

### 工作流示例

典型的代码审查工作流如下：

1. 用户向 AI Agent 提出需求："检查 `src/main.cpp` 中的潜在问题"
2. Agent 调用 `check_code` 工具，传递文件的绝对路径和 `quick` 模式
3. MCP 插件自动检测项目环境，构建优化的 cppcheck 命令
4. 返回清洗后的 XML 结果给 Agent
5. Agent 解析 XML，提取错误信息（错误类型、严重程度、行号、描述）
6. Agent 调用文件读取工具，定位具体代码行
7. Agent 分析错误原因，生成修复建议或直接修改代码
8. 可选：再次调用 `check_code` 验证修复效果

这种闭环工作流使代码质量保障过程高度自动化，用户只需监督关键决策点。




## 设计权衡与未来优化

### 关键设计决策

**为何输出 XML 而非 JSON**：保持与 cppcheck 原生格式一致，避免格式转换导致的信息丢失。大语言模型对 XML 和 JSON 的理解能力相当，XML 格式的结构化特性足以支持高效解析。

**为何不区分项目和单文件**：cppcheck 本身支持文件和目录作为输入，统一处理可简化接口设计。通过项目检测逻辑自动应用不同策略，对用户透明。

**为何选择 FastMCP**：项目需求聚焦于业务逻辑封装，不涉及复杂的协议层控制。FastMCP 提供的声明式开发方式显著降低了实现复杂度。仅当需要实现多用户服务、限流控制、身份隔离等高级功能时，才需要切换到底层 Server API。

### 优化方向

**编译参数智能提取**：当检测到 `compile_commands.json` 但目标不是项目文件时，可解析 JSON 提取 include 路径（`-I`）、预定义宏（`-D`）、编译标准（`-std`）等参数，应用到 cppcheck 命令中。这能显著减少因缺少编译上下文导致的误报。

实现思路：

```python
def _extract_compile_flags(compile_commands_path):
    with open(compile_commands_path) as f:
        commands = json.load(f)
    include_paths = set()
    defines = set()
    for entry in commands:
        args = entry.get("command", "").split()
        for i, arg in enumerate(args):
            if arg == "-I" and i + 1 < len(args):
                include_paths.add(args[i + 1])
            elif arg.startswith("-D"):
                defines.add(arg)
    return list(include_paths), list(defines)
```

**常见目录自动检测**：除项目根目录外，自动添加常见的 include 目录到搜索路径：`{project_root}/include`、`{project_root}/src`、`{project_root}/lib`。

**误报过滤接口**：提供配置选项屏蔽特定类型的误报，如 Qt 宏相关的警告。可通过 `--suppress` 参数或后处理 XML 实现。

**报告持久化**：支持 `--output-file` 参数，将检查结果保存到本地文件，文件名包含时间戳和检查参数，便于历史对比和审计。

## 总结

基于 MCP 协议封装静态分析工具的核心价值在于构建适合大语言模型工作的环境。通过项目感知能力、输出优化和标准化接口，插件将复杂的命令行工具转化为 AI Agent 可直接调用的能力模块。这种封装不仅降低了工具使用门槛，更重要的是实现了上下文管理和信息密度控制，使静态分析能够无缝融入 AI 辅助开发的工作流。

项目地址：https://github.com/noonafter/mcp_cppcheck

cppcheck 官方文档：https://cppcheck.sourceforge.io/manual.html
