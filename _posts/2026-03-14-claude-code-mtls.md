---
layout: article
title: Claude Code 的双向 TLS 认证机制与抓包调试
date: 2026-03-14 10:00:00 +0800
tags:
  - llm
  - agents
  - https
  - encryption
  - web
---


## 一、TLS 认证模式

### 1、单向 TLS 认证

单向 TLS 是 HTTPS 通信的标准模式。客户端验证服务器身份，服务器通过 API Key 等凭证识别客户端。

**验证流程**：
1. 客户端发起连接请求
2. 服务器返回证书
3. 客户端验证证书有效性
4. 建立加密通道

客户端验证服务器证书时，依赖操作系统的受信任根证书列表。证书由权威 CA 机构签发，客户端通过信任链验证证书合法性。

### 2、双向 TLS 认证（mTLS）

双向 TLS 在单向认证基础上增加了服务器对客户端的验证。

**验证流程**：
1. 客户端发起连接并发送客户端证书
2. 服务器验证客户端证书
3. 服务器返回服务器证书
4. 客户端验证服务器证书
5. 双向验证通过后建立加密通道

**关键特征**：
- 客户端内置特定证书和私钥
- 服务器存储客户端证书的 CA 根证书
- 双方必须互相认证才能建立连接

### 3、mTLS 的成立条件

双向 TLS 认证需要客户端和服务器同时满足条件。

**客户端要求**：
- 内置客户端证书和私钥
- 主动在握手阶段发送证书
- 验证服务器证书的合法性

**服务器要求**：
- 配置客户端证书验证（`ssl_verify_client on`）
- 存储客户端证书的 CA 根证书
- 验证客户端证书的合法性

**核心原则**：客户端和服务器任意一端不满足条件，连接自动降级为单向 TLS。

双方必须互相信任对方的 CA 根证书。如果客户端不是官方客户端，或服务器不是官方服务器，双向认证无法建立。

## 二、Claude Code 的安全设计

### 1、专属通道机制

Claude Code 使用双向 TLS 连接 Anthropic 官方服务器。这种设计限制了只有官方客户端能访问特定的高权限接口。

**客户端实现**：
```typescript
const options = {
    hostname: 'api.anthropic.com',
    port: 443,
    cert: fs.readFileSync('./built-in-client.crt'), 
    key: fs.readFileSync('./built-in-client.key'),
    ca: fs.readFileSync('./anthropic-root-ca.crt')
};
```

客户端代码中硬编码了：
- 内置的客户端证书和私钥
- Anthropic 官方根证书
- 证书锁定（Certificate Pinning）逻辑

**服务器配置**：

服务器端启用客户端证书验证（`ssl_verify_client on`），存储官方 CA 根证书。验证通过的连接获得 `[Verified Agent]` 标签，可访问内部接口。

### 2、证书锁定机制

Claude Code 不依赖操作系统的证书信任列表，而是在代码中指定信任的证书。这种机制称为证书锁定。

**与普通应用的区别**：

| 应用类型 | 证书验证 | 信任来源 | 抓包难度 |
|---------|---------|---------|---------|
| 普通应用 | 启用 | 操作系统 | 低 |
| Claude Code | 启用 | 代码硬编码 | 高 |
| 不规范应用 | 禁用 | 无 | 无 |

普通应用询问操作系统证书是否可信，Claude Code 绕过操作系统直接验证证书指纹。

## 三、Charles 抓包原理

### 1、中间人攻击（MITM）

Charles 通过中间人攻击解密 HTTPS 流量。

**工作流程**：

1. **一次性准备**：将 Charles 根证书安装到操作系统受信任列表
2. **动态伪造**：为每个目标域名动态生成证书

**具体过程**：
1. 应用请求 `https://api.example.com`
2. Charles 拦截请求
3. Charles 动态生成 `api.example.com` 证书
4. Charles 用自己的根证书签名该证书
5. 应用验证证书，操作系统确认 Charles 根证书可信
6. 应用接受证书，建立加密通道
7. Charles 解密流量并显示明文

### 2、证书伪造机制

Charles 不绑定 IP 地址，而是绑定域名。每次访问不同域名时，Charles 动态生成对应的证书。

**信任链**：
- Charles 根证书（安装在操作系统）
- 动态生成的域名证书（由 Charles 根证书签名）

操作系统信任 Charles 根证书后，自动信任其签名的所有子证书。

### 3、为何无法抓取 Claude Code

Claude Code 使用证书锁定，不信任操作系统的证书列表。当 Charles 提供自签名证书时：

1. Charles 拦截请求并返回自签名证书
2. Claude Code 验证证书
3. 发现证书不是 Anthropic 官方签发
4. 触发 `Self-signed certificate detected` 错误
5. 主动断开连接

连接在 TLS 握手阶段失败，数据未传输。

## 四、证书验证的底层机制

### 1、权威证书的颁发流程

权威 CA 机构颁发证书时执行严格的域名所有权验证。

**颁发条件**：
1. 申请者证明拥有目标域名
2. CA 机构验证域名所有权
3. CA 签发绑定该域名的证书

**证书类型**：
- **叶子证书**：终端证书，只能证明身份，无颁发权限
- **中间证书**：可签发下级证书，需要根证书授权
- **根证书**：信任链顶端，操作系统预装

Charles 使用的自签名证书不经过 CA 机构验证，因此不被默认信任。

### 2、证书与私钥的关系

证书包含公钥和域名信息，私钥由证书持有者保管。

**加密握手过程**：
1. 服务器发送证书（包含公钥）
2. 客户端用公钥加密随机数
3. 服务器用私钥解密
4. 双方生成会话密钥

私钥泄露意味着攻击者可以解密所有通信。DeepSeek 等第三方服务的私钥存储在其机房，外部无法获取。

### 3、为何购买权威证书无法用于 Charles

即使购买权威证书，也无法用于 Charles 抓包。

**原因一：域名绑定**

权威证书绑定特定域名。Charles 需要伪造任意域名的证书，但权威证书只能证明购买者拥有的域名。

示例：
- 购买 `myproxy.com` 的证书
- Claude Code 请求 `api.anthropic.com`
- Charles 提供 `myproxy.com` 证书
- 域名不匹配，验证失败

**原因二：证书类型限制**

购买的叶子证书无颁发权限。Charles 需要中间 CA 证书才能动态签发子证书。

中间 CA 证书的获取条件：
- 费用：数十万至数百万美元/年
- 审计：硬件安全模块（HSM）存储私钥
- 监管：签发非授权域名会被全球吊销

### 4、Node.js 证书验证流程

Node.js 在建立 HTTPS 连接时执行证书验证。

**正常流程**：
1. 检查证书域名与请求域名是否匹配
2. 验证证书签名链
3. 检查证书是否在信任列表中
4. 验证失败则抛出错误并断开连接

**错误类型**：
- `SELF_SIGNED_CERT_IN_CHAIN`：证书链中存在自签名证书
- `UNABLE_TO_VERIFY_LEAF_SIGNATURE`：无法验证叶子证书签名
- `CERT_HAS_EXPIRED`：证书已过期

## 五、绕过证书验证的方法

### 1、NODE_TLS_REJECT_UNAUTHORIZED 环境变量

该环境变量控制 Node.js 是否拒绝未验证的证书。

**设置方法**：
```bash
export NODE_TLS_REJECT_UNAUTHORIZED="0"
```

**作用机制**：

设置为 `"0"` 后，Node.js 仍然执行证书验证，但在验证失败时不抛出错误，继续建立连接。

**修改后的流程**：
1. 检查证书域名：匹配
2. 验证证书签名链：失败（Charles 自签名）
3. 检查环境变量：`NODE_TLS_REJECT_UNAUTHORIZED="0"`
4. 忽略验证失败，继续连接

### 2、安全风险

禁用证书验证会接受所有证书，包括恶意证书。

**风险场景**：
- 网络中存在攻击者
- 攻击者伪造证书拦截流量
- 应用接受伪造证书
- 敏感数据（API Key、代码）泄露

**使用原则**：
- 仅在本地调试环境使用
- 使用后关闭终端，环境变量自动失效
- 禁止在生产环境设置

### 3、使用 HTTP 协议

将 API 地址改为 HTTP 协议可完全绕过 TLS 验证。

```bash
export ANTHROPIC_BASE_URL="http://127.0.0.1:8080/v1"
```

HTTP 协议不加密，Charles 可直接查看明文内容。

**适用场景**：
- 本地代理服务
- 开发环境调试
- 不涉及敏感数据的测试

## 六、mTLS 降级场景

### 1、四种客户端-服务器组合

双向 TLS 认证只在特定组合下成立。任意一端不满足条件，连接自动降级为单向 TLS。

| 客户端 | 服务器 | 认证模式 | 原因 |
|--------|--------|---------|------|
| Claude Code | Claude 官方 | 双向 TLS | 双方都支持并要求 mTLS |
| Claude Code | 第三方服务 | 单向 TLS | 第三方服务不验证客户端证书 |
| 第三方客户端 | Claude 官方 | 单向 TLS | 第三方客户端无 Claude 证书 |
| 第三方客户端 | 第三方服务 | 单向 TLS | 双方都不要求 mTLS |

### 2、场景一：Claude Code 连接第三方服务

将 Claude Code 的 API 地址改为 DeepSeek、豆包等第三方服务时，双向 TLS 机制失效。

**降级原因**：
- 第三方服务不存储 Anthropic 客户端证书的 CA 根证书
- 第三方服务无法验证 Claude Code 的客户端证书
- 第三方服务不要求客户端证书

**通信流程**：
1. Claude Code 发送客户端证书
2. 第三方服务忽略客户端证书
3. 使用单向 TLS 建立连接
4. 通过 API Key 鉴权

**抓包方法**：
```bash
export ANTHROPIC_BASE_URL="https://api.deepseek.com/anthropic"
export NODE_TLS_REJECT_UNAUTHORIZED="0"
```

配合 Charles 代理，可查看完整的请求和响应内容。

### 3、场景二：第三方客户端连接 Claude 官方服务

使用 Cherry Studio、Chatbox 等第三方客户端连接 Claude 官方 API 时，同样降级为单向 TLS。

**降级原因**：
- 第三方客户端不包含 Anthropic 官方客户端证书
- 第三方客户端无法通过 mTLS 验证
- Claude 官方 API 接口（`https://api.anthropic.com`）支持单向 TLS

**通信流程**：
1. 第三方客户端发起连接
2. Claude 服务器返回服务器证书
3. 客户端验证服务器证书
4. 使用单向 TLS 建立连接
5. 通过 API Key 鉴权

**抓包方法**：

第三方客户端通常不使用证书锁定，安装 Charles 根证书后即可抓包。无需设置 `NODE_TLS_REJECT_UNAUTHORIZED`。

### 4、场景三：第三方客户端连接第三方服务

使用第三方客户端连接第三方 LLM 服务时，双方都不要求 mTLS。

**通信特点**：
- 标准的单向 TLS 认证
- 通过 API Key 鉴权
- 无证书锁定限制

**抓包方法**：

安装 Charles 根证书后直接抓包，无需额外配置。

### 5、中转代理的作用

中转代理（如 One-API、LiteLLM）转换不同 LLM 服务的 API 格式。

**工作流程**：
```
Claude Code → HTTP/单向TLS → 中转代理 → 单向TLS → 第三方服务
```

**功能**：
1. 接收 Claude 格式请求
2. 转换为目标服务格式
3. 转发到第三方服务
4. 转换响应格式返回

中转代理使用单向 TLS 或 HTTP，避免双向认证限制。

## 七、实践配置

### 1、PowerShell 环境变量配置

```powershell
$env:HTTP_PROXY = "http://127.0.0.1:8888"
$env:HTTPS_PROXY = "http://127.0.0.1:8888"
$env:ANTHROPIC_BASE_URL = "https://api.deepseek.com/anthropic"
$env:ANTHROPIC_AUTH_TOKEN = "sk-xxxxx"
$env:NODE_TLS_REJECT_UNAUTHORIZED = "0"
```

**配置说明**：
- `HTTP_PROXY`/`HTTPS_PROXY`：Charles 代理地址
- `ANTHROPIC_BASE_URL`：第三方 API 地址
- `ANTHROPIC_AUTH_TOKEN`：API 密钥
- `NODE_TLS_REJECT_UNAUTHORIZED`：禁用证书验证

### 2、Bash 环境变量配置

```bash
export HTTP_PROXY="http://127.0.0.1:8888"
export HTTPS_PROXY="http://127.0.0.1:8888"
export ANTHROPIC_BASE_URL="https://api.deepseek.com/anthropic"
export ANTHROPIC_AUTH_TOKEN="sk-xxxxx"
export NODE_TLS_REJECT_UNAUTHORIZED="0"
```

### 3、抓包流程

**方法一：Claude Code + 第三方服务**
1. 启动 Charles，配置代理端口 8888
2. 设置环境变量（包括 `NODE_TLS_REJECT_UNAUTHORIZED="0"`）
3. 启动 Claude Code
4. Charles 显示明文请求和响应

**方法二：Claude Code + HTTP 服务**
1. 启动本地 HTTP 代理服务
2. 设置 `ANTHROPIC_BASE_URL="http://127.0.0.1:8080/v1"`
3. 启动 Claude Code
4. Charles 直接查看明文内容

**方法三：第三方客户端 + 任意服务**
1. 安装 Charles 根证书到操作系统
2. 启动 Charles
3. 使用第三方客户端（Cherry Studio、Chatbox 等）
4. Charles 显示明文请求和响应

### 4、验证成功标志

- Claude Code 或第三方客户端正常连接
- Charles 显示目标 API 的请求
- 可查看完整的 Prompt 和响应内容
- 无 `Self-signed certificate detected` 错误

## 八、总结

### 1、核心原则

双向 TLS 认证需要客户端和服务器同时满足条件。**任意一端不是 Claude 官方，连接自动降级为单向 TLS**。

### 2、四种组合

| 客户端 | 服务器 | 认证模式 | 抓包难度 |
|--------|--------|---------|---------|
| Claude Code | Claude 官方 | 双向 TLS | 高（需绕过证书锁定） |
| Claude Code | 第三方服务 | 单向 TLS | 中（需禁用证书验证） |
| 第三方客户端 | Claude 官方 | 单向 TLS | 低（安装根证书即可） |
| 第三方客户端 | 第三方服务 | 单向 TLS | 低（安装根证书即可） |

### 3、抓包方法

**Claude Code 场景**：
- 连接第三方服务 + 设置 `NODE_TLS_REJECT_UNAUTHORIZED="0"`
- 连接 HTTP 服务（完全绕过 TLS）

**第三方客户端场景**：
- 安装 Charles 根证书到操作系统
- 无需额外配置

### 4、安全提醒

- 禁用证书验证仅用于本地调试
- 使用后关闭终端，环境变量自动失效
- 禁止在生产环境设置
- 抓包可能泄露 API Key 和敏感数据
