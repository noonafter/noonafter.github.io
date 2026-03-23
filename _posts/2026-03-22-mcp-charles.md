---
title: Claude Code MCP 插件踩坑与底层抓包全过程分析
tags: llm mcp agent
---


随着大模型的发展，MCP（Model Context Protocol）协议逐渐成为连接 LLM 与外部工具的标配。最近我动手使用 Python 写了一个简单的 MCP 插件（包含一个计算器 `add` 工具），并将其接入到 Claude Code 中。

在这个过程中，我遇到了一些环境路径的坑，并顺手抓包分析了 Claude Code 与大模型之间到底是如何通过 MCP 协议交互的。这篇博客将对整个过程复盘。

## 一、 环境搭建与配置踩坑

### 1. 初始化与本地调试
首先，我使用了 `uv` 来创建和管理 Python MCP 项目，具体过程参考[官方教程](https://github.com/modelcontextprotocol/python-sdk)。在正式接入 Claude 前，强烈建议先使用官方提供的 inspector 工具进行本地调试：
```bash
npx @modelcontextprotocol/inspector uv run python main.py
```
确认无误后，就可以将其添加到 Claude Code 中了。

### 2. 插件的安装与作用域
在 Claude Code 中添加 MCP 插件时，有**项目级**和**用户级**（全局）两种配置：
```bash
# 添加为用户级配置（--scope user）
claude mcp add my-calculator "uv --directory D:\mcp_demo run main.py" --scope user
```
MCP 的配置会保存在 `.claude.json` 文件中。你可以使用 `/mcp` 命令查看所有已连接的服务器，或者使用 `claude mcp remove my-calculator -s user` 来删除特定作用域的插件。

### 3. 踩坑：为什么切换目录后 MCP 工具就失效了？
**现象：**
当我在工程目录 `D:\alc\c\mcp_demo` 下运行 Claude 时，工具秒开；但当我在外部目录（如 `C:\Users\lc`）唤起 Claude 时，工具连接失败：`ModuleNotFoundError: No module named 'mcp'`。

**原因分析：**
当我们在外部目录启动时，`uv` 在拉起 python 子进程时，Windows 的 PATH 搜索逻辑可能会优先去找系统全局的 Python，而不是项目虚拟环境（`.venv`）里的 Python。

**解决方案：**
放弃使用 `uv run` 包装层，直接在配置文件中写死绝对路径，显式指定虚拟环境解释器和 `PYTHONPATH`。修改 `C:\Users\lc\.claude.json` 如下：

```json
"my-calculator": {
  "type": "stdio",
  "command": "D:\\alc\\c\\mcp_demo\\.venv\\Scripts\\python.exe",
  "args": [
    "D:\\alc\\c\\mcp_demo\\main.py"
  ],
  "env": {
    "PYTHONPATH": "D:\\alc\\c\\mcp_demo"
  }
}
```
这样做的好处是：
1. **直接锁定执行器**：保证 mcp 依赖一定能被正确加载。
2. **消除路径歧义**：无论在哪个盘符启动 Claude，都能精准找到脚本。


## 二、 抓包分析：Claude 是如何调用 MCP 工具的？

配置好后，我向 Claude 发送了一句指令：`"帮我计算23423452加76882034"`。
通过抓包，我截获了宿主应用（Claude Code）与大模型后端的两次完整 API 交互。这清晰地展示了 Tool Calling 的执行脉络。

**抓包环境说明**

由于Claude Code默认使用的是双向 HTTPS 协议，Charles无法进行抓包，所以只能使用支持 HTTP 的地址，具体配置如下:

*   工具：Charles
*   代理：HTTP\_PROXY=”<http://127.0.0.1:8888”>
*   协议：HTTP（原 HTTPS 双向通信）
*   API：火山引擎 API
*   模型：doubao-seed-2-0-lite-260215   
   

Claude Code配置如下：
```json
{
  "env": {
    "ANTHROPIC_AUTH_TOKEN": "xxxx",
    "ANTHROPIC_BASE_URL": "http://ark.cn-beijing.volces.com/api/compatible",
    "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
    "ANTHROPIC_MODEL": "Doubao-Seed-2.0-lite"
  },
  "permissions": {
    "allow": [],
    "deny": []
  },
  "primaryApiKey": "fox",
  "model": "opus"
}
```

### 第一次交互：模型决定调用工具

**请求 (Request):**
Claude Code 将我们的 MCP 工具转换成了大模型能看懂的 JSON Schema，并塞入 `tools` 数组中发给大模型：
```json
{
    "model": "Doubao-Seed-2.0-lite",
    "messages": [
        {"role": "user", "content": [{"type": "text", "text": "帮我计算23423452加76882034"}]}
    ],
    "tools": [
        // ... 其他工具 ...
        {
            "name": "mcp__my-calculator__add",
            "description": "Add two numbers",
            "input_schema": {
                "type": "object",
                "properties": {
                    "a": {"type": "integer"},
                    "b": {"type": "integer"}
                },
                "required": ["a", "b"]
            }
        }
    ]
}
```

**响应 (Response):**
大模型以后端 SSE（Server-Sent Events）流式返回数据。*（注：以下为了便于阅读，将冗长的流式 Delta 字符拼接进行了合并压缩）*：

> **[Thinking 思考过程]**： "用户让我计算两个数相加，我看到有一个 MCP 工具 `add` 可以用。让我调用这个工具来计算。"
> 
> **[Tool Use 工具调用]**：
> ```json
> {
>   "type": "tool_use",
>   "id": "call_uluah3g52mli6ioybbordmsh",
>   "name": "mcp__my-calculator__add",
>   "input": {"a": 23423452, "b": 76882034}
> }
> ```
> *(模型触发 `stop_reason: "tool_use"`，暂停生成)*

### 第二次交互：宿主返回结果，模型输出最终答案

此时，Claude Code（宿主）在本地拦截到了 `tool_use` 指令，通过 stdio 与我们的 Python 脚本通信，拿到结果 `100305486`，然后发起第二次大模型请求。

**请求 (Request):**
这次的请求包含了历史上下文，并附带了工具执行的返回值：
```json
{
    "messages": [
        {"role": "user", "content": [{"type": "text", "text": "帮我计算..."}]},
        {"role": "assistant", "content": [
            {"type": "thinking", "thinking": "用户让我计算..."},
            {"type": "tool_use", "id": "call_uluah...", "name": "mcp__my-calculator__add", "input": {"a": 23423452, "b": 76882034}}
        ]},
        {"role": "user", "content": [
            // 这里就是宿主塞进去的执行结果！
            {
                "tool_use_id": "call_uluah...",
                "type": "tool_result",
                "content": "{\"result\":100305486}"
            }
        ]}
    ]
}
```

**响应 (Response):**
大模型收到结果后，再次流式生成最终回复：

> **[Thinking 思考过程]**： "工具已经返回了结果，23423452 + 76882034 = 100305486。我直接告诉用户结果。"
> 
> **[Text 文本输出]**："计算结果：**100305486**"


## 三、 深度思考：为什么抓包时能看到 Tools，却看不到 Resources？

在把玩 MCP 时，很多人会发现：`Tools`（工具）很容易在抓包时看到，但 `Resources`（资源，比如 `greeting://{name}` 这种 URI）却毫无踪影。为什么？

通过分析 MCP 的底层逻辑，我得出以下结论：

1. **主动与被动的差异：**
   `Tools` 是主动的“技能”。在 MCP 握手阶段，Claude Code 等客户端会在启动时自动调用 `list_tools`，并将获取到的工具列表一股脑作为 Prompt/Schema 塞给大模型（如上面抓包的第一步）。
   而 `Resources` 类似于文件或数据库条目，是“被动”的数据。客户端通常不会在每次请求时去拉取所有资源，除非该资源具有静态 URI 或被明确订阅。

2. **动态 URI（Resource Templates）的局限性：**
   如果你定义的资源是类似于 `greeting://{name}` 这样的模板化资源，MCP 规范中服务器会通过 `list_resource_templates` 宣告它。
   **但目前的痛点在于：** 很多 MCP 客户端（包括早期的 Claude Code 或某些集成的 Cherry Studio 版本）对资源模板的支持远不如工具成熟。大模型知道怎么“传参调用”一个工具，但往往不知道该如何“填充”一个资源模板的 URI 参数，除非宿主程序显式地将这些模板逻辑翻译给大模型。

## 结语

通过这次从配置到抓包的完整实战，我们可以清晰地看到 MCP 架构的本质：**它其实是一个标准化的中介层**。它让宿主应用（Claude Code）能够通过标准协议（stdio/sse/http）与本地脚本通信，然后将其转化为大模型原生支持的 Tool Calling Schema。

建议大家在开发 MCP 插件时，遇到奇怪的环境问题，果断采用 **“绝对解释器路径”** 法；而在设计插件能力时，优先使用 `Tools` 而非 `Resources`，会获得更好的大模型兼容性。

*(希望这篇记录对正在开发 MCP 插件的你有所帮助！)*

## 附录：MCP插件代码
```python
from mcp.server.fastmcp import FastMCP
# Create an MCP server
mcp = FastMCP("Demo")

# Add an addition tool
@mcp.tool()
def add(a: int, b: int) -> int:
    """Add two numbers"""
    return a + b

# Add a dynamic greeting resource
@mcp.resource("greeting://{name}")
def get_greeting(name: str) -> str:
    """Get a personalized greeting"""
    return f"Hello, {name}!"

if __name__ == "__main__":
    mcp.run(transport="stdio")
```