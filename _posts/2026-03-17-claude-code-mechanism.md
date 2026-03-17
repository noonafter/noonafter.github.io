---
title: Claude Code 工作机制深度解析：基于抓包数据逆向分析
tags: llm agent skills
---

本文通过对 Claude Code CLI 工具进行 HTTP 抓包，分析并探讨其底层工作机制，包括 System Prompt 设计、Tools 架构、Skills 系统以及渐进式披露（Progressive Disclosure）策略。这些设计理念对构建高质量的 AI Agent 对话系统具有重要参考价值。

**抓包环境说明**

由于Claude Code默认使用的是双向 HTTPS 协议，Charles无法进行抓包，所以只能使用支持 HTTP 的地址，具体配置如下:

- 工具：Charles
- 代理：HTTP_PROXY="http://127.0.0.1:8888"
- 协议：HTTP（原 HTTPS 双向通信）
- API：火山引擎 API
- 模型：doubao-seed-2-0-lite-260215

## 一、整体架构概览

### 1.1 请求结构
拦截到Claude Code发出的API请求如下图所示。

![cc_http](https://noonafter.cn/assets/images/posts/2026-03-17-claude-code-mechanism/cc_http_request.png)

一级结构如下（这里展开了简单的键值）：

```json

{
    "model": "doubao-seed-2-0-lite-260215", // 具体模型版本
    "messages": Array[1], // 用户消息和上下文
    "system": Array[3], // 系统提示词
    "tools": Array[25], // 可用工具定义
    "metadata": { // 元数据，用户id
        "user_id": "user_xxxx_account__session_xxxx"
    },
    "max_tokens": 32000, // 最大生成 Token 数
    "thinking": { // 推理模式开关，token预算等
        "budget_tokens": 31999,
        "type": "enabled"
    },
    "output_config": { // 计算力度：中等
        "effort": "medium"
    },
    "stream": true // 流式输出
}
```

可以发现，Claude Code 使用标准的 Anthropic API 格式，主要包含三个核心部分：

- **messages**: 用户消息和上下文
- **system**: 系统提示词（System Prompt）
- **tools**: 可用工具定义

### 1.2 缓存机制

在message和system中都可以看到cache_control字段，

```json
{
  "type": "text",
  "text": "...",
  "cache_control": {
    "type": "ephemeral"
  }
}
```

这是因为 Claude Code 使用了 `cache_control` 机制来优化性能。这种缓存策略可以减少重复内容的传输，提高响应速度。

## 二、System Prompt 设计

这里将系统提示词单独copy下来进行分析，发现其内容非常多并且复杂（1.5w+字符），以下仅抽取一些重要的片段进行分析，感兴趣的大佬可以自行抓取分析。

### 2.1 身份定位

```
You are Claude Code, Anthropic's official CLI for Claude.
You are an interactive agent that helps users with software engineering tasks.
```

明确的身份定位让 AI 清楚自己的角色和职责范围。

### 2.2 核心原则

System Prompt 包含多个层次的指导原则：

#### **安全原则**
- 支持授权的安全测试、防御性安全、CTF 挑战
- 拒绝破坏性技术、DoS 攻击、供应链攻击
- 不生成或猜测 URL（除非用于编程帮助）

#### **任务执行原则**
- 专注于软件工程任务（修复 bug、添加功能、重构代码等）
- 先读取代码再提出修改建议
- 避免过度工程，保持简单专注
- 不添加未请求的功能或"改进"

#### **风险管理原则**
```
Carefully consider the reversibility and blast radius of actions.
```

对于不可逆或影响范围大的操作（删除文件、force push、修改 CI/CD 等），需要先征求用户确认。

### 2.3 工具使用策略

System Prompt 明确规定了工具使用的优先级：

```
Do NOT use Bash when a relevant dedicated tool is provided:
- Read files → Use Read (not cat/head/tail)
- Edit files → Use Edit (not sed/awk)
- Write files → Use Write (not echo/cat)
- Search files → Use Glob (not find/ls)
- Search content → Use Grep (not grep/rg)
```

这种设计有两个优势：
1. **用户体验**：专用工具提供更好的权限审查界面
2. **可控性**：每个工具调用都可以被单独审核和批准

### 2.4 并行执行优化

```
If you intend to call multiple tools and there are no dependencies between them,
make all independent tool calls in parallel.
```

这是性能优化的关键设计，鼓励 AI 并行执行独立任务。

## 三、Tools 架构设计

### 3.1 核心工具清单

从抓包数据中可以发现，Claude Code默认提供25个工具（8.5w+字符），其中主要工具包括：

| 工具名称 | 功能描述 | 典型用途 |
|---------|---------|---------|
| **Agent** | 启动子代理处理复杂任务 | 代码探索、计划制定 |
| **Bash** | 执行 Shell 命令 | 系统操作、Git 命令 |
| **Read** | 读取文件内容 | 查看代码、配置文件 |
| **Edit** | 精确字符串替换 | 修改代码 |
| **Write** | 写入文件 | 创建新文件 |
| **Glob** | 文件模式匹配 | 查找文件 |
| **Grep** | 内容搜索 | 搜索代码片段 |
| **AskUserQuestion** | 询问用户 | 澄清需求 |

其他工具包括Enter/ExitPlanMode、NotebookEdit、WebFetch/Search、TaskCreate/Stop/Get/Output/Update/List、Skill、Enter/ExitWorktree、CronCreate/Delete/List。这里发现Skill其实也是工具之一，关于详细的tools说明，可以参考我另一篇blog[]()。


### 3.2 Agent 工具：子代理系统

Agent 工具是 Claude Code 的核心创新，支持多种专用子代理：

#### **子代理类型**

1. **general-purpose**: 通用代理，可访问所有工具
2. **Explore**: 代码库探索专家（快速搜索、关键词查找）
3. **Plan**: 软件架构师（设计实现计划）
4. **statusline-setup**: 配置状态栏
5. **claude-code-guide**: 回答 Claude Code 相关问题

#### **关键特性**

```json
{
  "name": "Agent",
  "description": "Launch a new agent to handle complex, multi-step tasks autonomously.",
  "input_schema": {
    "properties": {
      "description": "A short (3-5 word) description",
      "prompt": "The task for the agent to perform",
      "subagent_type": "The type of specialized agent",
      "run_in_background": "Set to true to run in background",
      "resume": "Optional agent ID to resume from"
    }
  }
}
```

**特点**：
- **后台执行**：长任务可在后台运行，完成后通知
- **可恢复**：通过 `resume` 参数继续之前的代理会话
- **隔离执行**：可在 git worktree 中隔离运行

### 3.3 Bash 工具：受控的命令执行

Bash 工具设计体现了安全性和用户体验的平衡：

#### **安全限制**

```
- NEVER update git config
- NEVER run destructive commands unless explicitly requested
- NEVER skip hooks (--no-verify)
- NEVER force push to main/master
```

#### **Git 提交流程**

System Prompt 详细规定了 Git 提交的标准流程：

1. 并行执行：`git status`、`git diff`、`git log`
2. 分析变更并起草提交信息
3. 添加文件并创建提交（附带 Co-Authored-By）
4. 验证提交成功

#### **超时和后台执行**

```json
{
  "timeout": "Optional timeout in milliseconds (max 600000)",
  "run_in_background": "Set to true to run in background"
}
```

### 3.4 Read/Edit/Write：文件操作三剑客

#### **Read 工具特性**
- 支持多种格式：文本、图片、PDF、Jupyter Notebook
- 分段读取：通过 `offset` 和 `limit` 处理大文件
- 多模态：可直接读取和显示图片

#### **Edit 工具设计**
```
- Must use Read tool before editing
- Preserve exact indentation after line number prefix
- Edit fails if old_string is not unique
- Use replace_all for renaming variables
```

这种设计确保编辑的精确性和可追溯性。

#### **Write 工具限制**
```
- Must use Read tool first for existing files
- Prefer Edit for modifications (only sends diff)
- NEVER create documentation files unless requested
```

## 四、Skills 系统：可扩展的能力模块

### 4.1 Skills 架构

从抓包数据中发现的 Skills 系统：

```xml
<system-reminder>
The following skills are available for use with the Skill tool:

- simplify: Review changed code for reuse, quality, and efficiency
- loop: Run a prompt on a recurring interval (e.g. /loop 5m /foo)
- claude-api: Build apps with the Claude API or Anthropic SDK
</system-reminder>
```

### 4.2 Skills 触发机制

Skills 通过两种方式触发：

1. **用户显式调用**：`/skill-name` (如 `/commit`, `/simplify`)
2. **条件自动触发**：基于代码特征自动激活

**示例：claude-api skill**
```
TRIGGER when: code imports `anthropic`/@anthropic-ai/sdk
DO NOT TRIGGER when: code imports `openai`/other AI SDK
```

### 4.3 Skills vs Tools 的区别

| 维度 | Tools | Skills |
|-----|-------|--------|
| **定义位置** | API 请求中的 tools 数组 | System reminder 中动态注入 |
| **调用方式** | 直接工具调用 | 通过 Skill 工具间接调用 |
| **扩展性** | 需要修改 API 定义 | 可动态添加/移除 |
| **用途** | 基础能力（文件操作、命令执行） | 高级工作流（代码审查、提交） |

## 五、渐进式披露（Progressive Disclosure）策略

### 5.1 什么是渐进式披露

渐进式披露是 Claude Code 的核心设计模式，通过 `<system-reminder>` 标签在用户消息中动态注入上下文信息。

### 5.2 实现机制

从抓包数据中可以看到，用户消息包含多个部分：

```json
{
  "role": "user",
  "content": [
    {
      "type": "text",
      "text": "<system-reminder>\nThe following skills are available...\n</system-reminder>"
    },
    {
      "type": "text",
      "text": "<system-reminder>\nAs you answer the user's questions...\n# currentDate\nToday's date is 2026-03-15.\n</system-reminder>"
    },
    {
      "type": "text",
      "text": "你是谁",
      "cache_control": {"type": "ephemeral"}
    }
  ]
}
```

### 5.3 渐进式披露的优势

#### **1. 减少认知负担**
- 只在需要时提供相关信息
- 避免一次性加载所有上下文

#### **2. 动态上下文注入**
- 根据当前状态注入相关提示
- 例如：只在有可用 Skills 时显示 Skills 列表

#### **3. 提高 Token 效率**
- 通过 `cache_control` 缓存常用内容
- 减少重复传输

### 5.4 System Reminder 的类型

从抓包数据中可以发现，在message中存在 System Reminder 类型，定位到System Reminder，可以发现其主要用于以下三个方面：


1. **Skills 可用性提醒**
```xml
<system-reminder>
The following skills are available for use with the Skill tool:
- simplify: Review changed code...
- claude-api: Build apps with Claude API...
</system-reminder>
```

1. **上下文信息提醒**
```xml
<system-reminder>
# currentDate
Today's date is 2026-03-15.
IMPORTANT: this context may or may not be relevant to your tasks.
</system-reminder>
```

1. **工具使用提醒**
```xml
<system-reminder>
The TodoWrite tool hasn't been used recently.
Consider using it if relevant to current work.
</system-reminder>
```

## 六、Agent 对话机制深度剖析

### 6.1 多轮对话的状态管理

Claude Code 通过以下机制维护对话状态：

#### **1. 持久化内存系统**
```
You have a persistent auto memory directory at:
C:\Users\lc\.claude\projects\<project-id>\memory\

- MEMORY.md: 始终加载到上下文（限制 200 行）
- 主题文件: debugging.md, patterns.md 等
```

**记忆策略**：
- 保存：稳定的模式、架构决策、用户偏好
- 不保存：会话特定上下文、临时状态、推测性结论

#### **2. 上下文压缩**
```
The system will automatically compress prior messages
as it approaches context limits.
```

这使得对话不受上下文窗口限制。

### 6.2 权限模型

#### **权限模式**
- **Autopilot 模式**：自主修改文件
- **Supervised 模式**：用户可在应用后撤销更改

#### **工具权限控制**
```
Tools are executed in a user-selected permission mode.
When you attempt to call a tool that is not automatically allowed,
the user will be prompted to approve or deny.
```

### 6.3 错误处理和自适应

#### **失败处理策略**
```
If your approach is blocked, do not brute force.
Consider alternative approaches or use AskUserQuestion.
```

#### **Hook 系统**
```
Users may configure 'hooks', shell commands that execute
in response to events like tool calls.
Treat feedback from hooks as coming from the user.
```

## 七、关键设计模式总结

### 7.1 分层提示词架构

Claude Code 采用三层提示词结构：

```
┌─────────────────────────────────────┐
│   System Prompt (静态核心指令)      │
│   - 身份定位                         │
│   - 核心原则                         │
│   - 工具使用规范                     │
└─────────────────────────────────────┘
           ↓
┌─────────────────────────────────────┐
│   System Reminder (动态上下文)      │
│   - Skills 列表                      │
│   - 当前日期                         │
│   - 工具使用提醒                     │
└─────────────────────────────────────┘
           ↓
┌─────────────────────────────────────┐
│   User Message (用户输入)           │
│   - 实际问题                         │
│   - 文件引用                         │
└─────────────────────────────────────┘
```

### 7.2 工具调用的最佳实践

#### **1. 优先使用专用工具**
```
Read > cat
Edit > sed
Write > echo
Glob > find
Grep > grep
```

#### **2. 并行化独立操作**
```python
# 好的做法：并行读取多个文件
[Read(file1), Read(file2), Read(file3)]

# 避免：串行读取
Read(file1) → Read(file2) → Read(file3)
```

#### **3. 先读后写**
```
Must use Read tool before editing existing files
```

### 7.3 安全性设计原则

#### **最小权限原则**
- 默认拒绝破坏性操作
- 需要用户明确授权

#### **可逆性优先**
```
Carefully consider the reversibility and blast radius of actions.
```

#### **审计和追溯**
- 每个工具调用都可被审查
- Git 提交包含 Co-Authored-By 标记

## 八、对 Agent 系统设计的启示

### 8.1 提示词工程最佳实践

#### **1. 明确的角色定位**
```
✓ You are Claude Code, Anthropic's official CLI
✗ You are an AI assistant
```

#### **2. 具体的行为规范**
不要说"要小心"，而是给出具体规则：
```
NEVER update git config
NEVER skip hooks (--no-verify)
NEVER force push to main/master
```

#### **3. 提供示例和反例**
```xml
<example>
user: "Please write a function..."
assistant: Uses Write tool...
</example>
```

### 8.2 工具设计原则

#### **1. 单一职责**
每个工具只做一件事，做好一件事：
- Read：只读取
- Edit：只编辑
- Write：只写入

#### **2. 组合优于复杂**
通过组合简单工具实现复杂功能，而不是创建复杂工具。

#### **3. 明确的前置条件**
```
Edit tool: Must use Read tool first
Write tool: Must use Read tool first for existing files
```

### 8.3 用户体验设计

#### **1. 渐进式披露**
- 不要一次性展示所有功能
- 根据上下文动态提供相关信息

#### **2. 可预测的行为**
```
Your responses should be short and concise.
Do not use a colon before tool calls.
```

#### **3. 透明的操作**
- 明确说明将要执行的操作
- 对危险操作请求确认

### 8.4 性能优化策略

#### **1. 缓存机制**
```json
"cache_control": {"type": "ephemeral"}
```
对静态内容（System Prompt、工具定义）使用缓存。

#### **2. 并行执行**
```
Launch multiple agents concurrently whenever possible
Make all independent tool calls in parallel
```

#### **3. 后台任务**
```
run_in_background: true
You will be notified when it completes
```

## 九、技术实现细节

### 9.1 消息结构解析

完整的请求消息结构：

```json
{
  "model": "doubao-seed-2-0-lite-260215",
  "messages": [
    {
      "role": "user",
      "content": [
        {"type": "text", "text": "<system-reminder>...</system-reminder>"},
        {"type": "text", "text": "<system-reminder>...</system-reminder>"},
        {"type": "text", "text": "实际用户消息", "cache_control": {"type": "ephemeral"}}
      ]
    }
  ],
  "system": [
    {"type": "text", "text": "版本信息"},
    {"type": "text", "text": "身份定位", "cache_control": {"type": "ephemeral"}},
    {"type": "text", "text": "详细指令", "cache_control": {"type": "ephemeral"}}
  ],
  "tools": [...]
}
```

### 9.2 工具定义规范

每个工具遵循统一的 JSON Schema 格式：

```json
{
  "name": "ToolName",
  "description": "详细的工具描述，包括使用场景和注意事项",
  "input_schema": {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "properties": {...},
    "required": [...],
    "additionalProperties": false
  }
}
```

### 9.3 环境信息注入

System Prompt 包含丰富的环境信息：

```
# Environment
- Primary working directory: C:\Users\lc\Desktop\tst
- Is a git repository: false
- Platform: win32
- Shell: bash
- OS Version: MSYS_NT-10.0-26200
- Model: doubao-seed-2-0-lite-260215
```

这些信息帮助 AI 生成平台特定的命令。

### 9.4 流式响应机制（SSE）
以下是抓到的LLM模型的HTTP响应：

![llm_http](https://noonafter.cn/assets/images/posts/2026-03-17-claude-code-mechanism/llm_http_response.png)

可以发现，Claude Code 使用 Server-Sent Events (SSE) 实现流式响应：

#### **响应头**
```
Content-Type: text/event-stream
Cache-Control: no-cache
Transfer-Encoding: chunked
```

#### **事件类型**

1. **message_start**: 消息开始
```json
{
  "type": "message_start",
  "message": {
    "id": "021773569788217ba1bdc7661816f1fcacaaa7f52b55edac1c9a0",
    "role": "assistant",
    "model": "doubao-seed-2-0-lite-260215",
    "usage": {
      "input_tokens": 20172,
      "output_tokens": 2
    }
  }
}
```

2. **content_block_start**: 内容块开始
```json
{"type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": ""}}
```

3. **content_block_delta**: 增量内容（逐字流式输出）
```json
{"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": "我"}}
{"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": "是"}}
```

4. **content_block_stop**: 内容块结束
5. **message_delta**: 消息元数据更新
6. **message_stop**: 消息结束

#### **流式响应的优势**
- **即时反馈**：用户立即看到输出开始
- **更好的体验**：避免长时间等待
- **可中断**：用户可随时停止生成

#### **实际响应示例**

从抓包数据中提取的完整响应内容：

> 我是由字节跳动开发的 **Doubao Seed 2.0 Lite** 大模型，正在 Claude Code CLI 环境中为你提供帮助。我专注于软件工程任务，可以帮你编写代码、调试bug、重构项目、解答技术问题等。
>
> 有什么我可以帮你的吗？

**关键观察**：
- 模型正确识别了自己的身份（Doubao 而非 Claude）
- 遵循了 System Prompt 中的角色定位
- 展示了软件工程任务的专注性
- Token 使用：输入 20,172 tokens，输出 65 tokens

个人吐槽：一个简单的“你是谁”，用掉了2w+ Tokens。

## 十、核心发现与总结

### 10.1 Claude Code 的核心创新

#### **1. 分层提示词架构**
- **静态层**（System）：核心原则和规范
- **动态层**（System Reminder）：上下文相关提示
- **交互层**（User Message）：用户输入

#### **2. 工具优先的设计哲学**
- 专用工具优于通用命令
- 组合简单工具实现复杂功能
- 明确的工具使用优先级

#### **3. 子代理系统**
- 专业化分工（Explore、Plan、Guide）
- 后台执行和可恢复
- 隔离执行环境

#### **4. 渐进式披露**
- 动态注入相关上下文
- 减少认知负担
- 提高 Token 效率

### 10.2 对 AI Agent 开发的启示

#### **提示词设计**
1. 使用具体规则而非模糊指导
2. 提供正反示例
3. 分层组织提示词内容

#### **工具设计**
1. 单一职责原则
2. 明确前置条件
3. 支持并行执行

#### **用户体验**
1. 透明的操作说明
2. 危险操作需确认
3. 可追溯的操作历史

#### **性能优化**
1. 缓存静态内容
2. 并行执行独立任务
3. 后台处理长任务

### 10.3 可借鉴的技术模式

```
┌──────────────────────────────────────────┐
│  渐进式披露 + 分层提示词                  │
│  ↓                                        │
│  专用工具 + 并行执行                      │
│  ↓                                        │
│  子代理系统 + 状态管理                    │
│  ↓                                        │
│  权限控制 + 安全审计                      │
└──────────────────────────────────────────┘
```

## 十一、结语

通过对 Claude Code 的抓包分析，我们揭示了一个成熟的 AI Agent 系统的设计精髓：

1. **清晰的架构**：分层的提示词、模块化的工具、专业化的子代理
2. **用户至上**：渐进式披露、透明操作、权限控制
3. **性能优化**：缓存机制、并行执行、后台任务
4. **安全可靠**：最小权限、可逆优先、审计追溯

这些设计理念不仅适用于代码辅助工具，也为构建其他领域的 AI Agent 系统提供了参考。



