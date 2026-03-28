---
layout: article
title: Claude Code Hooks 开发踩坑记录
date: 2026-03-26 22:00:00 +0800
tags: agent mcp hook
---


## 问题场景

在为 Claude Code 的 MCP 工具开发 PreToolUse Hook 时，遇到了一个典型但隐蔽的问题：stdin输入相对路径，Hook 脚本确实执行了路径转换逻辑（将相对路径 `.` 转换为绝对路径），日志也显示转换成功，但 MCP 服务器最终接收到的参数仍然是原始的相对路径。

本文基于一个 C++ 静态代码检测 MCP 插件的实际开发经验，记录 PreToolUse Hook 开发中的两个陷阱及其解决方案。

## 背景：MCP 静态代码检测插件

该插件基于 cppcheck 实现 C++ 代码静态分析能力，通过 MCP 协议暴露 `check_code` 工具供 Claude Code 调用。插件的核心功能包括：

- **项目感知**：自动检测项目根目录、编译数据库（`compile_commands.json`）和配置文件
- **输出优化**：清洗 cppcheck 的冗长 XML 输出，移除 `verbose` 和 `column` 等冗余属性
- **标准化接口**：通过 `check_code(target_path, mode)` 提供统一的调用方式

由于 MCP 服务器作为独立进程运行，无法获取 Claude Code 的当前工作目录（cwd），因此必须接收绝对路径作为 `target_path` 参数。当 Claude 传递相对路径（如 `.`）时，需要通过 PreToolUse Hook 将其转换为绝对路径后再传递给 MCP 工具。

## 陷阱一：返回字段名称错误

### 问题表现

最初的 Hook 脚本返回结构如下：

```python
output = {
    "hookSpecificOutput": {
        "modifiedToolInput": {
            "target_path": absolute_path,
            "mode": "quick"
        },
        "shouldProceed": True
    }
}
print(json.dumps(output))
```

日志中也显示路径转换成功，但 MCP 工具仍然收到相对路径 `.`。

### 根本原因

PreToolUse Hook 的返回协议要求使用 `updatedInput` 字段，而非 `modifiedToolInput`。错误的字段名导致 Claude Code 忽略了 Hook 的参数改写结果。

此外，`shouldProceed` 字段也不是 PreToolUse 事件的标准控制字段。正确的决策字段应为 `permissionDecision`。

### 正确实现

PreToolUse Hook 必须返回以下标准结构：

```python
output = {
    "hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "allow",
        "permissionDecisionReason": "Normalize target_path to absolute path",
        "updatedInput": {
            "target_path": absolute_path,
            "mode": mode
        }
    }
}
```

**关键字段说明**：

- `hookEventName`：必须为 `"PreToolUse"`，标识 Hook 事件类型
- `permissionDecision`：取值为 `"allow"` 或 `"deny"`，控制工具调用是否继续执行
- `permissionDecisionReason`：决策原因的文本描述，用于日志和调试
- `updatedInput`：改写后的工具参数，完整替换原始 `tool_input`

### 字段命名的重要性

MCP Hook 协议采用严格的字段名匹配机制。使用错误的字段名不会触发错误提示，而是导致返回值被静默忽略。这种设计增加了调试难度，开发者必须严格遵循官方文档的字段定义。

参考文档：
- https://docs.claude.com/en/docs/claude-code/hooks
- https://code.claude.com/docs/zh-TW/hooks

## 陷阱二：多 Hook 链式覆盖问题

### 问题表现

修正字段名后，Hook 在某些会话中仍然失效。通过分析日志发现，同一次工具调用触发了两个 PreToolUse Hook：

```
[2026-03-26 21:26:56] Hook 1: cppcheck-path-resolver-debug.py
  Input: {"target_path": ".", "mode": "quick"}
  Output: {"updatedInput": {"target_path": "D:\\alc\\c\\g33ddc\\src\\app", "mode": "quick"}}

[2026-03-26 21:26:56] Hook 2: python3 ${CLAUDE_PLUGIN_ROOT}/hooks/pretooluse.py
  Input: {"target_path": ".", "mode": "quick"}
  Output: (no updatedInput)
```

第二个 Hook 来自全局启用的 `hookify` 插件，其 PreToolUse 执行器在没有匹配规则时返回空结构，导致第一个 Hook 的 `updatedInput` 被覆盖。

### 根本原因

Claude Code 的 Hook 执行机制采用**链式调用**模式：当多个 Hook 监听同一事件时，按配置顺序依次执行，后一个 Hook 的返回值会**完全覆盖**前一个 Hook 的状态。

这种设计类似于"last writer wins"策略，不存在参数合并或增量更新机制。如果后续 Hook 返回的 `updatedInput` 为空或缺失该字段，前面 Hook 的参数改写将被丢弃。

### 覆盖行为的技术细节

以下场景会导致参数覆盖：

1. **后续 Hook 返回空 `updatedInput`**：即使前面的 Hook 已改写参数，后续 Hook 返回 `{}` 或不包含 `updatedInput` 字段时，改写失效
2. **后续 Hook 返回部分字段**：如果后续 Hook 只返回 `{"target_path": "."}`，会丢失前面 Hook 添加的其他字段（如 `cwd`）
3. **全局插件的隐式执行**：像 `hookify` 这样的全局插件会对所有工具调用执行 Hook，即使没有匹配规则也会返回结构，干扰其他 Hook

### 解决方案

**方案一：禁用冲突的全局 Hook**

在 `~/.claude/settings.json` 中禁用 `hookify` 插件：

```json
{
  "plugins": {
    "hookify@claude-plugins-official": false
  }
}
```

这是最直接的解决方案，适用于不依赖 `hookify` 功能的场景。

**方案二：调整 Hook 执行顺序**

确保参数改写 Hook 在链路中最后执行。但这需要修改插件配置或 Hook 注册顺序，实现复杂度较高。

**方案三：在 MCP 服务端实现路径兜底**

最稳健的方案是让 MCP 服务器自行处理相对路径，不依赖 Hook 注入。但这引入了新的问题：MCP 服务器作为独立进程，无法获取 Claude Code 的 cwd。

可行的实现方式包括：

1. **显式传递 cwd 参数**：修改工具签名为 `check_code(target_path, cwd=None, mode="quick")`，在 Hook 中将 `input_data["cwd"]` 写入 `updatedInput.cwd`。但这仍然受链式覆盖问题影响。

2. **强制要求绝对路径**：服务端在给大模型的注释中要求输入绝对路径，但是大模型并不一定会按照提示来，所以在执行代码中，仍然需要检测输入是否是绝对路径，如果检测到相对路径，直接报错并要求上游重试。

```python
@mcp.tool()
def check_code(target_path: str, mode: str = "quick") -> str:
    """Check code with cppcheck
    Args:
        target_path: ABSOLUTE path to file, directory, compile_commands.json, or .cppcheck file
        mode: Check mode - 'quick' (default) or 'full'

    Important: target_path must be an absolute path. Relative paths cannot be resolved.
    """
    # ...其他代码

    # 不接受相对路径输入
    if not path.is_absolute():
        raise ValueError(f"Relative path not supported: {path}. Please provide absolute path.")
    # 继续执行检查逻辑
```

### 为何 Matcher 无法解决覆盖问题

在自己的 `hooks.json` 中添加 `matcher` 配置，只能控制**当前 Hook 何时触发**，无法阻止**后续 Hook 覆盖返回值**。

例如，以下配置仅限制 Hook 在特定工具调用时执行：

```json
{
  "hooks": {
    "PreToolUse": {
      "command": "python3",
      "args": ["cppcheck-path-resolver.py"],
      "matcher": {
        "tool_name": "mcp__plugin_cpp-checker_cppcheck__check_code"
      }
    }
  }
}
```

但如果全局插件（如 `hookify`）没有对应的 `matcher` 限制，它仍然会在所有工具调用时执行，并覆盖当前 Hook 的结果。

真正有效的方案是在 `hookify` 侧添加排除规则，或确保参数改写 Hook 最后执行。

## 设计反思

### Hook 链式覆盖的合理性

这种"last writer wins"设计在某些场景下是合理的：

- **权限控制链**：后续 Hook 可以覆盖前面 Hook 的 `permissionDecision`，实现更严格的访问控制
- **参数校验链**：后续 Hook 可以在前面 Hook 的基础上进一步修正参数

但在参数改写场景下，这种设计容易引发冲突。更理想的机制应该是：

1. **增量更新**：后续 Hook 的 `updatedInput` 与前面 Hook 的结果合并，而非完全覆盖
2. **显式覆盖标记**：通过 `overwrite: true` 字段明确表示完全覆盖意图
3. **Hook 优先级**：允许配置 Hook 执行顺序或优先级

### 全局插件的兼容性问题

`hookify` 插件的设计目标是规则拦截和提示，而非参数改写透传。其 PreToolUse 执行器在无匹配规则时仍然返回结构，这在多 Hook 环境下容易引发兼容性问题。

这可以视为 `hookify` 在该场景下的设计缺陷。建议在官方仓库提交 Issue，要求：

- 无匹配规则时不返回 `hookSpecificOutput`，或明确返回 `null`
- 提供配置选项排除特定工具或插件的 Hook 执行

## 最佳实践建议

### Hook 开发规范

1. **严格遵循字段命名**：使用 `updatedInput` 而非 `modifiedToolInput`，使用 `permissionDecision` 而非 `shouldProceed`
2. **完整返回参数**：`updatedInput` 必须包含工具的所有参数，即使某些参数未修改
3. **添加详细日志**：记录输入参数、转换逻辑和输出结果，便于调试链式覆盖问题
4. **测试多 Hook 场景**：在启用全局插件的环境下测试 Hook 行为，确认参数改写不被覆盖

### 架构设计建议

1. **服务端兜底优于 Hook 注入**：关键参数处理逻辑应在 MCP 服务端实现，Hook 仅作为辅助优化
2. **显式参数优于隐式推断**：通过工具签名明确要求必需参数（如 `cwd`），而非依赖 Hook 注入
3. **错误快速失败**：服务端检测到无效参数时立即报错，避免静默使用错误值

### 调试方法

当 Hook 参数改写失效时，按以下步骤排查：

1. **检查字段命名**：确认使用 `updatedInput` 和 `permissionDecision`
2. **查看 Hook 日志**：确认 Hook 是否执行以及返回值格式
3. **分析会话 Transcript**：检查 `hook_progress` 事件，确认是否有多个 Hook 执行
4. **检查全局插件**：在 `~/.claude/settings.json` 中查看启用的插件列表
5. **查看 MCP 服务端日志**：确认最终接收到的参数值

## 总结

Claude Code 的 PreToolUse Hook 开发中存在两个关键陷阱：

1. **字段命名错误**：必须使用 `updatedInput` 和 `permissionDecision`，错误的字段名会被静默忽略
2. **链式覆盖问题**：多个 Hook 按顺序执行时，后续 Hook 会完全覆盖前面 Hook 的返回值，全局插件（如 `hookify`）容易引发冲突

解决方案的优先级为：

1. **禁用冲突的全局插件**（最简单）
2. **在 MCP 服务端实现参数校验和兜底逻辑**（最稳健）
3. **调整 Hook 执行顺序或添加排除规则**（最复杂）

从架构设计角度，关键业务逻辑应在 MCP 服务端实现，而非依赖 Hook 的参数注入。Hook 更适合用于权限控制、日志记录和辅助优化，而非核心功能的实现路径。

## 参考资源

- Claude Code Hooks 官方文档：https://docs.claude.com/en/docs/claude-code/hooks
- MCP 协议规范：https://modelcontextprotocol.io/
- 本文涉及的 C++ 静态检测插件：https://github.com/noonafter/mcp_cppcheck
