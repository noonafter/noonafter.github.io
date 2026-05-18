---
layout: article
title: 博客性能优化实践：从 20 秒到 3 秒的加载优化
date: 2026-02-26 10:00:00 +0800
tags:
  - web
  - https
  - blog
---


## 一、架构概述

博客采用静态站点与动态评论服务分离的架构：

**主站（noonafter.cn）**
- 托管平台：GitHub Pages
- CDN 加速：Cloudflare（已开启代理）
- 站点生成：Jekyll 静态博客

**评论服务（comment.noonafter.cn）**
- 托管平台：Vercel Serverless
- 数据库：Neon PostgreSQL（免费版）
- 功能模块：Waline 评论系统 + Pageview 统计
- CDN 加速：Cloudflare（已开启代理）

完整链路如下：

```
用户浏览器│▼
Cloudflare（DNS + CDN）
    │
    ├─── noonafter.cn → GitHub Pages（静态站点）
    │
    └─── comment.noonafter.cn → Vercel（Waline 服务端）
                                    └─── Neon PostgreSQL（数据库）
```

## 二、访问流程分析

用户访问 noonafter.cn 的完整流程包含以下阶段：

**1. DNS 解析与静态资源加载**

Cloudflare 将域名解析到 GitHub Pages IP，流量经过 CDN 节点。Cloudflare 检查缓存（TTL: 1 小时），缓存命中时直接返回（< 200ms），未命中时回源 GitHub Pages获取 HTML/CSS/JS。

**2. 页面渲染**

浏览器解析 HTML 并加载外部资源（CSS/JS 从 unpkg.com CDN获取）。

**3. Pageview 统计请求**

主页与文章页的行为存在差异：

| 页面类型 | 请求方式 | 缓存策略 | 响应时间 |
|---------|---------|---------|---------|
| 主页 | `GET /api/article?path=...` | Cloudflare 缓存 1 小时 | 缓存命中 < 200ms，未命中 2-3s |
| 文章页 | `POST /api/article` | 不缓存，每次回源 | 2-3s（含冷启动） |

**4. 评论区加载**

```
GET /api/comment?path=/&pageSize=10&page=1
→ 不缓存（保证实时性）
→ 每次回源 Vercel（2-3s）
```

## 三、性能问题诊断

在性能优化之前，访问博客url的时间可能长达20s以上，用户体验很差，配合Chrome的开发者模式，对HTTP请求响应流程进行分析，发现主要问题如下：

### 问题 1：Waline API 延迟（5-6 秒）

**现象**：`/api/article` 和 `/api/comment` 请求耗时 5-6 秒，Waiting for server response 时间过长。

**根本原因**：
- **Vercel 冷启动**：Serverless Function 无流量时休眠，首次请求需要 2-3 秒启动
- **Neon 数据库冷启动**：免费版有自动暂停机制，唤醒需要 1-2 秒
- **无缓存机制**：每次请求都回源，无法利用 CDN 加速

### 问题 2：Mermaid.js 加载慢（6.39 秒）

**现象**：`https://cdn.bootcss.com/mermaid/8.0.0-rc.8/mermaid.min.js` 加载耗时 6.39 秒。

**根本原因**：
- **BootCDN 不稳定**：服务质量下降，经常出现加载慢或无法访问
- **版本过旧**：使用 2018 年的 RC 版本（8.0.0-rc.8）

### 问题 3：Google Analytics 超时（10-30 秒）

**现象**：`https://www.googletagmanager.com/gtag/js` 加载耗时 10-30 秒，有时无响应。

**根本原因**：Google Analytics 在中国大陆被屏蔽，导致长时间等待后超时。

## 四、优化方案实施

### 方案 1：启用 Cloudflare 缓存

将 `comment.noonafter.cn` 改为橙色云朵（Proxied），创建 3 条 Cache Rules：

**规则 1 - Cache Waline Pageview**
```yaml
匹配条件：
  hostname = comment.noonafter.cn
  AND path starts with /api/article
边缘 TTL：忽略缓存控制标头，使用此TTL: 3600 秒（1 小时）
浏览器 TTL：替代源服务器，使用此 TTL: 60 秒
```

**规则 2 - Cache Waline Comment**
```yaml
匹配条件：
  hostname = comment.noonafter.cn
  AND path starts with /api/comment
边缘 TTL：遵守源服务器（不缓存，保证实时性）
```

**规则 3 - Cache Blog Pages**
```yaml
匹配条件：
  hostname = noonafter.cn
边缘 TTL：遵守源服务器，回退 TTL: 600 秒（10 分钟）
```

**效果**：
- 主页 pageview：从 5.6s 降低到 < 200ms（缓存命中）
- 文章页 pageview：仍然 2-3s（POST 请求不缓存）
- 评论：保持实时性

### 方案 2：优化 CDN 配置

修改 `_data/variables.yml`：
- 将 `sources: bootcdn` 改为 `sources: unpkg`
- 修复 valine URL 语法错误
- 升级 Mermaid 从 `8.0.0-rc.8` 到 `@11`（最新版）

**效果**：Mermaid.js 加载时间从 6.39s 降低到 < 1s。

### 方案 3：禁用 Google Analytics

修改 `_config.yml`：
- 将 `analytics.provider: google` 改为 `analytics.provider: false`

**效果**：消除 10-30 秒的超时延迟，页面加载速度显著提升。

## 五、GET vs POST 的权衡

### 1、技术背景

- **GET 请求**：语义上是只读，可以被 Cloudflare 缓存
- **POST 请求**：语义上可以修改数据，Cloudflare 默认不缓存

Waline 的 `/api/article` 行为是读取浏览量 + 增加浏览量（读+写操作），从 REST 语义来说应该用 POST。但主页使用 GET 请求（查询多篇文章），可以缓存；文章页使用 POST 请求（查询单篇文章），不能缓存。

### 2、最终决策

| 场景 | 请求方式 | 缓存策略 | 理由 |
|-----|---------|---------|------|
| 主页 pageview | GET | 1 小时 | 提升主页加载速度 |
| 文章页 pageview | POST | 不缓存 | 保持语义正确性 |
| 评论 | GET/POST | 不缓存 | 保证实时性 |

**优点**：
- 主页加载速度大幅提升（< 200ms）
- 减少 Vercel 冷启动频率
- 降低 Neon 数据库压力
- 评论实时性得到保证

**缺点**：
- 主页和文章页的 pageview 数据可能不一致（最多 1 小时延迟）
- 文章页首次访问仍然较慢（2-3s）

**权衡理由**：对于个人技术博客，主页的用户体验更重要。Pageview 的绝对准确性不是最高优先级，1 小时的缓存时间可以兼顾速度和实时性。

## 六、优化效果验证

| 指标 | 优化前 | 优化后 | 提升幅度 |
|-----|-------|-------|---------|
| 主页加载| 20+ 秒 | < 3 秒 | 85% |
| 文章页加载 | 20+ 秒 | 5-8 秒 | 60% |
| Waline API（主页） | 5.6s | < 200ms | 96% |
| Mermaid.js 加载 | 6.39s | < 1s | 84% |
| Google Analytics | 10-30s | 0s（已禁用） | 100% |

**关键配置文件**：
- `_data/variables.yml` - CDN 配置
- `_config.yml` - Analytics 配置
- Cloudflare Cache Rules - 3 条缓存规则

## 七、后续优化建议

1. **升级 Vercel Pro**：减少冷启动频率
2. **升级 Neon 付费版**：禁用自动暂停
3. **使用 GitHub Actions 定时 ping**：保持 Vercel 热启动
4. **本地化静态资源**：将 Mermaid.js 下载到本地，随博客一起部署

通过上述优化，页面加载时间从 20+ 秒降低到 3-8 秒，用户体验得到显著提升。