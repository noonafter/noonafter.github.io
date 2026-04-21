---
layout: article
title: BLOG搭建笔记之六：评论系统与Pageview迁移
date: 2025-04-21 10:50:56 +0800
tags:
  - blog
---


## 一、背景与选型

原博客使用 Valine 评论系统，依赖 LeanCloud 作为数据存储，同时使用 busuanzi 统计文章阅读量。LeanCloud 宣布于 2027 年停止对外服务，busuanzi 不支持在首页列表中显示各文章的阅读量，因此决定将两者统一迁移至 Waline。

**Waline 的核心优势**：

- 从 Valine 衍生，配置逻辑相近，迁移成本低
- 引入服务端（部署在 Vercel），数据库凭据不暴露在前端
- 同时支持评论和 Pageview 统计，两个功能共用一套服务端
- 支持匿名评论，内置垃圾评论过滤

**整体架构**：

| 组件 | 职责 |
|------|------|
| Vercel（Serverless） | 运行 Waline 服务端，处理评论读写和 PV 统计 |
| Neon（Serverless PostgreSQL） | 持久化存储评论和阅读量数据 |
| 博客前端（GitHub Pages） | 调用 Waline API 展示评论区和阅读量 |

Vercel 采用 Serverless 架构：无请求时不占用资源，有请求时在毫秒级内启动容器执行代码后销毁。对个人博客而言，免费额度完全够用。



## 二、服务端部署

### 1. Vercel 一键部署

访问 Waline 官方提供的 Vercel 部署模板链接，登录 Vercel 后 fork 仓库并部署。部署时：

- **Repository Name**：建议改为 `waline-server`，比默认的 `my-repository` 更清晰
- **Vercel Team**：选择个人账号
- **Private**：保持私有即可

### 2. Neon 数据库创建

在 Vercel Dashboard 的 **Storage** 标签中，选择 **Neon（Serverless Postgres）**，配置如下：

- **Region**：选择亚太区域（Singapore 或 Tokyo），延迟更低；若无亚太选项，美国东部也可接受
- **Auth**：关闭，Waline 有自己的管理员认证
- **Plan**：Free，0.5 GB 存储对个人博客绰绰有余

创建完成后，在 Neon 数据库页面点击 **Connect to Project**，将数据库关联到 `waline-server` 项目，勾选全部三个环境（Development、Preview、Production）。

### 3. 环境变量配置

Neon 关联项目后会自动注入一批 `POSTGRES_*` 和 `PG*` 格式的环境变量，但 **Waline 识别的是 `PG_*` 格式**，两者不完全对应，需手动添加以下变量：

| 变量名 | 值来源 |
|--------|--------|
| `PG_HOST` | 从 `PGHOST` 复制 |
| `PG_DB` | 从 `POSTGRES_DATABASE` 复制 |
| `PG_USER` | 从 `PGUSER` 复制 |
| `PG_PASSWORD` | 从 `PGPASSWORD` 复制 |
| `PG_SSL` | 直接填 `true`（Neon 强制 SSL） |

也可以直接添加 `DATABASE_URL`，值为完整的 PostgreSQL 连接字符串：

```
postgresql://neondb_owner:<password>@<host>/neondb?sslmode=require
```

添加完成后，在 **Deployments** 页面触发 **Redeploy**，使环境变量生效。

### 4. 数据库表初始化

首次部署后，Waline 会尝试自动建表。若自动建表失败（注册时报 `relation "wl_users" does not exist`），需在 Neon 的 SQL Editor 中手动执行建表语句：

```sql
CREATE TABLE IF NOT EXISTS wl_Comment (
  id SERIAL PRIMARY KEY,
  user_id INTEGER,
  comment TEXT,
  insertedAt TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
  ip VARCHAR(100) DEFAULT '',
  link VARCHAR(255) DEFAULT '',
  mail VARCHAR(255) DEFAULT '',
  nick VARCHAR(255) DEFAULT '',
  pid INTEGER,
  rid INTEGER,
  star INTEGER,
  status VARCHAR(50) DEFAULT '',
  ua TEXT,
  url VARCHAR(255) DEFAULT '',
  referrer VARCHAR(255) DEFAULT '',
  createdAt TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
  updatedAt TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS wl_Counter (
  id SERIAL PRIMARY KEY,
  time INTEGER,
  url VARCHAR(255) NOT NULL,
  createdAt TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
  updatedAt TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS wl_Users (
  id SERIAL PRIMARY KEY,
  display_name VARCHAR(255) DEFAULT '',
  email VARCHAR(255) DEFAULT '',
  password VARCHAR(255) DEFAULT '',
  type VARCHAR(50) DEFAULT '',
  url VARCHAR(255) DEFAULT '',
  avatar VARCHAR(255) DEFAULT '',
  github VARCHAR(255) DEFAULT '',
  twitter VARCHAR(255) DEFAULT '',
  facebook VARCHAR(255) DEFAULT '',
  google VARCHAR(255) DEFAULT '',
  weibo VARCHAR(255) DEFAULT '',
  qq VARCHAR(255) DEFAULT '',
  createdAt TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
  updatedAt TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
```

### 5. 注册管理员账号

访问 `https://<your-waline-domain>/ui/register`，第一个注册的账号自动成为管理员。注册后可通过 `/ui/login` 进入后台管理评论。



## 三、评论系统前端接入

jekyll-text-theme 不原生支持 Waline，通过 `custom` provider 接入。

### _config.yml

```yaml
comments:
  provider: custom
  waline:
    server_url: https://<your-waline-domain>
```

### _includes/comments-providers/custom.html

```html
<link rel="stylesheet" href="https://unpkg.com/@waline/client@v3/dist/waline.css" />
<div id="waline"></div>
<script type="module">
  import { init } from 'https://unpkg.com/@waline/client@v3/dist/waline.js';
  init({
    el: '#waline',
    serverURL: '{{ site.comments.waline.server_url }}',
  });
</script>
```

### 开发环境评论区不渲染

`_includes/comments.html` 默认包含环境检查：

```liquid
{%- if jekyll.environment != 'development' -%}
```

该条件导致 `jekyll serve` 时评论区不渲染。删除此条件后开发环境可正常显示。



## 四、Pageview 迁移

原方案使用 busuanzi，仅支持文章页统计，首页列表无法显示各文章阅读量。Waline 的 `/api/article` 接口同时支持单页计数和批量查询。

### 1. 文章页统计

修改 `_includes/article/top/custom.html`：

```html
<!-- start custom article top snippet -->
<script>
  (function() {
    var serverURL = '{{ site.comments.waline.server_url }}';
    var path = window.location.pathname;
    fetch(serverURL + '/api/article', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path: path })
    }).then(function(r) { return r.json(); })
      .then(function(res) {
        var el = document.querySelector('.js-pageview');
        if (el && res.data && res.data[0]) el.textContent = res.data[0].time;
      });
  })();
</script>
<!-- end custom article top snippet -->
```

**关键点**：`/api/article` POST 请求必须将 `path` 放在 JSON body 中，使用 query string 传参时服务端不识别，计数不会增加。

### 2. 修正 data-page-key

`_includes/article-info.html` 中 `.js-pageview` 元素原来的 `data-page-key` 存储的是文章 `key`（如 `2025-01-19-github-pages-comment`），而 Waline 存储和查询使用的是 URL 路径（如 `/2025/01/19/github-pages-comment.html`）。需将其改为 `include.article.url`：

```diff
- <span class="js-pageview" data-page-key="{{ include.article.key }}">0</span>
+ <span class="js-pageview" data-page-key="{{ include.article.url }}">0</span>
```

### 3. 首页批量查询

修改 `_includes/pageview-providers/custom/home.html`：

```html
<!-- start custom pageview snippet (for Home layout) -->
<script>
  (function() {
    var serverURL = '{{ site.comments.waline.server_url }}';
    var els = Array.from(document.querySelectorAll('.js-pageview[data-page-key]'));
    if (!els.length) return;
    var paths = els.map(function(el) {
      return encodeURIComponent(el.getAttribute('data-page-key'));
    }).join(',');
    fetch(serverURL + '/api/article?path=' + paths)
      .then(function(r) { return r.json(); })
      .then(function(res) {
        if (!res.data) return;
        res.data.forEach(function(item, i) {
          if (els[i]) els[i].textContent = item.time;
        });
      });
  })();
</script>
<!-- end custom pageview snippet (for Home layout) -->
```

**关键点**：`/api/article` GET 响应中每条数据格式为 `{time: N}`，不含 `url` 字段，因此必须按索引顺序匹配元素，而非按 URL 匹配。

### 4. 移除环境检查

`_includes/pageview.html` 默认包含 `jekyll.environment != 'development'` 条件，导致开发环境下 pageview 脚本不加载。删除该条件后开发环境可正常调试。



## 五、自定义域名（解决国内访问）

Vercel 默认域名（`*.vercel.app`）在国内被封锁，导致评论区和阅读量无法加载。解决方案是为 Waline 服务端绑定一个国内可访问的自定义域名。

### 操作步骤

**1. Cloudflare DNS 配置**

在 Cloudflare （需要先去域名购买商处配置DNS为Cloudflare）中为域名添加 CNAME 记录：

| 类型 | 名称 | 目标 | 代理状态 |
|------|------|------|----------|
| CNAME | `comment` | `cname-china.vercel-dns.com` | 仅 DNS（灰色云朵） |

**2. Vercel 绑定域名**

进入 Waline 项目 → **Settings** → **Domains**，添加 `comment.<your-domain>`，等待 Vercel 自动签发 SSL 证书。

**3. 更新配置**

`_config.yml` 中将 `server_url` 改为新域名：

```yaml
comments:
  waline:
    server_url: https://comment.<your-domain>
```

### 注意事项

- CNAME 必须指向 `cname-china.vercel-dns.com`（Vercel 国内专用节点），而非 `cname.vercel-dns.com`
- Cloudflare 代理必须关闭（灰色云朵），否则 Cloudflare 与 Vercel 之间 SSL 握手失败（Error 525）
- 必须先在 Vercel 添加域名，Vercel 才会签发证书；DNS 配置正确但未在 Vercel 添加域名时访问会报错



## 六、数据库表结构补全

若数据库表由旧版 schema 初始化，`wl_comment` 和 `wl_users` 表会缺少新版字段，导致以下报错：

- 提交评论时：`column "sticky" does not exist`
- 访问后台管理时：`column "2fa" does not exist`

在 Neon SQL Editor 中执行以下语句补全缺失字段：

```sql
-- 补全 wl_comment 缺失列
ALTER TABLE wl_comment ADD COLUMN IF NOT EXISTS sticky numeric DEFAULT NULL;
ALTER TABLE wl_comment ADD COLUMN IF NOT EXISTS "like" int DEFAULT NULL;
ALTER TABLE wl_comment ADD COLUMN IF NOT EXISTS ua text;

-- 补全 wl_users 缺失列
ALTER TABLE wl_users ADD COLUMN IF NOT EXISTS label varchar(255) DEFAULT NULL;
ALTER TABLE wl_users ADD COLUMN IF NOT EXISTS url varchar(255) DEFAULT NULL;
ALTER TABLE wl_users ADD COLUMN IF NOT EXISTS avatar varchar(255) DEFAULT NULL;
ALTER TABLE wl_users ADD COLUMN IF NOT EXISTS github varchar(255) DEFAULT NULL;
ALTER TABLE wl_users ADD COLUMN IF NOT EXISTS twitter varchar(255) DEFAULT NULL;
ALTER TABLE wl_users ADD COLUMN IF NOT EXISTS facebook varchar(255) DEFAULT NULL;
ALTER TABLE wl_users ADD COLUMN IF NOT EXISTS google varchar(255) DEFAULT NULL;
ALTER TABLE wl_users ADD COLUMN IF NOT EXISTS weibo varchar(255) DEFAULT NULL;
ALTER TABLE wl_users ADD COLUMN IF NOT EXISTS qq varchar(255) DEFAULT NULL;
ALTER TABLE wl_users ADD COLUMN IF NOT EXISTS oidc varchar(255) DEFAULT NULL;
ALTER TABLE wl_users ADD COLUMN IF NOT EXISTS huawei varchar(255) DEFAULT NULL;
ALTER TABLE wl_users ADD COLUMN IF NOT EXISTS "2fa" varchar(32) DEFAULT NULL;
```



## 七、数据管理

- **评论**：访问 `https://<your-waline-domain>/ui/login`，使用管理员账号登录后可查看、审核、删除评论
- **阅读量**：阅读量数据存储在 Neon 的 `wl_counter` 表中，可在 Waline 后台的"文章"页面查看各页面统计
