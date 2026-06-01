---
layout: article
title: Clash Verge 使用指南与配置经验总结
date: 2025-05-31 14:30:00 +0800
tags:
  - proxy
  - diy
  - net
---

> 本文档基于 Clash Verge Rev（现已更名为 Clash Verge）的实际配置经验整理

## 一、Clash Verge 基础介绍

### 1.1 版本说明
- **当前版本**：Clash Verge（原 Clash Verge Rev）
- **核心**：verge-mihomo（基于 Clash Meta）
- **配置目录**：`C:\Users\<用户名>\AppData\Roaming\io.github.clash-verge-rev.clash-verge-rev`

### 1.2 基本功能
- 支持多订阅管理和快速切换
- 提供可视化的连接监控和规则匹配查看
- 支持全局配置覆写（Merge）和脚本扩展（Script）
- 内置规则集管理和自动更新



## 二、订阅管理

### 2.1 导入订阅
**方式一：订阅链接**
1. 点击"订阅" → "新建"
2. 输入订阅名称和订阅地址
3. 点击确认

**方式二：扫描二维码**
- 直接扫描机场提供的二维码即可导入

### 2.2 订阅操作
- **切换订阅**：在订阅列表中点击不同订阅即可切换
- **更新订阅**：右键订阅 → 更新
- **查看订阅配置**：右键订阅 → 打开文件
- **查看生效配置**: 订阅界面右上角 -> 查看运行时订阅
- **扩展配置**：右键订阅 → 扩展覆写配置 / 扩展脚本

### 2.3 订阅配置技巧
在 `profiles.yaml` 中为订阅添加主页链接：
```yaml
- uid: RgX44aglehKe
  type: remote
  name: mojie
  home: https://mojie.app  # 添加此行
```
这样右键订阅时会显示"打开主页"选项。



## 三、目录结构和关键文件

### 3.1 核心目录结构
```
C:\Users\lc\AppData\Roaming\io.github.clash-verge-rev.clash-verge-rev\
├── profiles/              # 订阅配置文件目录
│   ├── Merge.yaml        # 全局覆写配置
│   ├── Script.js         # 全局脚本
│   ├── RGkyhAYQT1Z0.yaml # 订阅1配置
│   ├── RgX44aglehKe.yaml # 订阅2配置
│   └── ...
├── ruleset/              # 规则集缓存目录
│   ├── reject.yaml
│   ├── direct.yaml
│   └── ...
├── profiles.yaml         # 订阅列表和关联配置
├── verge.yaml           # Clash Verge UI配置
├── config.yaml          # Clash核心配置
├── Country.mmdb         # GeoIP数据库
└── geosite.dat          # GeoSite数据库
```

### 3.2 关键文件说明

#### profiles.yaml
管理所有订阅及其关联的配置文件：
```yaml
current: RGkyhAYQT1Z0  # 当前激活的订阅
items:
  - uid: Merge
    type: merge          # 全局覆写配置
    file: Merge.yaml
  - uid: Script
    type: script         # 全局脚本
    file: Script.js
  - uid: RGkyhAYQT1Z0
    type: remote         # 远程订阅
    name: hongxingyun
    file: RGkyhAYQT1Z0.yaml
    option:
      merge: Merge       # 关联的merge配置
      script: Script     # 关联的script
```

#### verge.yaml
Clash Verge 的UI和系统设置，包括：
- 语言、主题设置
- 代理端口配置
- 系统代理设置
- 启动选项等

#### config.yaml
Clash 核心的基础配置：
- 端口设置（mixed-port、socks-port等）
- 日志级别
- 外部控制器配置
- TUN模式配置



## 四、订阅配置文件详解

### 4.1 订阅YAML的关键字段

打开任意订阅配置文件（如 `RGkyhAYQT1Z0.yaml`），可以看到以下关键字段：

#### proxies（代理节点列表）
定义所有可用的代理服务器节点：
```yaml
proxies:
  - name: 🇭🇰 香港1
    type: vless
    server: example.com
    port: 443
    # ... 其他配置
```

#### proxy-groups（代理组）
将代理节点组织成不同的策略组：
```yaml
proxy-groups:
  - name: 红杏云              # 主策略组（通常是第一个）
    type: select             # 手动选择
    proxies:
      - 自动选择
      - 🇭🇰 香港1
      - 🇸🇬 新加坡1
      # ...
  
  - name: 自动选择
    type: url-test           # 自动测速选择
    proxies:
      - 🇭🇰 香港1
      - 🇸🇬 新加坡1
    url: 'http://www.gstatic.com/generate_204'
    interval: 300
```

**代理组类型说明**：
- `select`：手动选择模式
- `url-test`：自动测速选择最快节点
- `fallback`：故障转移，按顺序测试可用性
- `load-balance`：负载均衡

#### rules（路由规则）
定义流量的路由策略：
```yaml
rules:
  - DOMAIN,google.com,红杏云        # 域名匹配
  - DOMAIN-SUFFIX,github.com,红杏云  # 域名后缀匹配
  - DOMAIN-KEYWORD,google,红杏云     # 域名关键字匹配
  - IP-CIDR,192.168.0.0/16,DIRECT   # IP段匹配
  - GEOIP,CN,DIRECT                 # 地理位置匹配
  - RULE-SET,gfw,红杏云              # 规则集匹配
  - MATCH,红杏云                     # 兜底规则
```

#### rule-providers（规则集提供者）
引用外部规则集文件：
```yaml
rule-providers:
  gfw:
    type: http
    behavior: domain
    url: "https://cdn.jsdelivr.net/gh/Loyalsoldier/clash-rules@release/gfw.txt"
    path: ./ruleset/gfw.yaml
    interval: 86400  # 更新间隔（秒）
```
PS:每个代理组中会有一个选中的节点（代理/子代理组），这个结点会作为rules配置路由到该代理组时，默认选择的代理节点。

### 4.2 配置修改建议

**❌ 不建议**：直接修改订阅配置文件
- 订阅更新时会覆盖手动修改
- 难以在多个订阅间同步配置

**✅ 推荐**：使用全局配置（Merge + Script）
- 配置独立于订阅，不会被覆盖
- 可以应用到所有订阅
- 便于维护和版本控制



## 五、全局配置方案：Merge + Script

### 5.1 配置目标

**问题**：多个订阅的主策略组名称不同
- 红杏云订阅：主策略组名为"红杏云"
- mojie订阅：主策略组名为"节点选择"
- yueto订阅：主策略组名为其他名称

**目标**：使用统一的规则配置，自动适配不同订阅的主策略组

### 5.2 解决方案

采用 **Merge.yaml（定义规则）+ Script.js（动态替换）** 的组合方案：

1. 在 `Merge.yaml` 中使用占位符 `PROXY` 定义规则
2. 在 `Script.js` 中动态将 `PROXY` 替换为当前订阅的主策略组名称

### 5.3 Merge.yaml 配置

创建 `profiles/Merge.yaml` 文件：

```yaml
# Profile Enhancement Merge Template for Clash Verge

profile:
  store-selected: true

# 1. 声明并下载全局共享规则集
rule-providers:
  reject:
    type: http
    behavior: domain
    url: "https://cdn.jsdelivr.net/gh/Loyalsoldier/clash-rules@release/reject.txt"
    path: ./ruleset/reject.yaml
    interval: 86400
  
  icloud:
    type: http
    behavior: domain
    url: "https://cdn.jsdelivr.net/gh/Loyalsoldier/clash-rules@release/icloud.txt"
    path: ./ruleset/icloud.yaml
    interval: 86400
  
  apple:
    type: http
    behavior: domain
    url: "https://cdn.jsdelivr.net/gh/Loyalsoldier/clash-rules@release/apple.txt"
    path: ./ruleset/apple.yaml
    interval: 86400
  
  google:
    type: http
    behavior: domain
    url: "https://cdn.jsdelivr.net/gh/Loyalsoldier/clash-rules@release/google.txt"
    path: ./ruleset/google.yaml
    interval: 86400
  
  proxy:
    type: http
    behavior: domain
    url: "https://cdn.jsdelivr.net/gh/Loyalsoldier/clash-rules@release/proxy.txt"
    path: ./ruleset/proxy.yaml
    interval: 86400
  
  direct:
    type: http
    behavior: domain
    url: "https://cdn.jsdelivr.net/gh/Loyalsoldier/clash-rules@release/direct.txt"
    path: ./ruleset/direct.yaml
    interval: 86400
  
  private:
    type: http
    behavior: domain
    url: "https://cdn.jsdelivr.net/gh/Loyalsoldier/clash-rules@release/private.txt"
    path: ./ruleset/private.yaml
    interval: 86400
  
  gfw:
    type: http
    behavior: domain
    url: "https://cdn.jsdelivr.net/gh/Loyalsoldier/clash-rules@release/gfw.txt"
    path: ./ruleset/gfw.yaml
    interval: 86400
  
  tld-not-cn:
    type: http
    behavior: domain
    url: "https://cdn.jsdelivr.net/gh/Loyalsoldier/clash-rules@release/tld-not-cn.txt"
    path: ./ruleset/tld-not-cn.yaml
    interval: 86400
  
  telegramcidr:
    type: http
    behavior: ipcidr
    url: "https://cdn.jsdelivr.net/gh/Loyalsoldier/clash-rules@release/telegramcidr.txt"
    path: ./ruleset/telegramcidr.yaml
    interval: 86400
  
  cncidr:
    type: http
    behavior: ipcidr
    url: "https://cdn.jsdelivr.net/gh/Loyalsoldier/clash-rules@release/cncidr.txt"
    path: ./ruleset/cncidr.yaml
    interval: 86400
  
  lancidr:
    type: http
    behavior: ipcidr
    url: "https://cdn.jsdelivr.net/gh/Loyalsoldier/clash-rules@release/lancidr.txt"
    path: ./ruleset/lancidr.yaml
    interval: 86400
  
  applications:
    type: http
    behavior: classical
    url: "https://cdn.jsdelivr.net/gh/Loyalsoldier/clash-rules@release/applications.txt"
    path: ./ruleset/applications.yaml
    interval: 86400

# 2. 全局覆写规则列表（PROXY 由 Script 动态替换）
rules:
  # === 【用户自定义规则】 ===
  - DOMAIN,zread.ai,DIRECT

  # === 【局域网及本地底层规则】 ===
  - RULE-SET,applications,DIRECT
  - DOMAIN,clash.razord.top,DIRECT
  - DOMAIN,yacd.haishan.me,DIRECT
  - RULE-SET,private,DIRECT
  - RULE-SET,lancidr,DIRECT
  - GEOIP,LAN,DIRECT

  # === 【隐私与广告拦截】 ===
  - RULE-SET,reject,REJECT

  # === 【白名单直连服务】 ===
  - RULE-SET,direct,DIRECT
  - RULE-SET,icloud,DIRECT
  - RULE-SET,apple,DIRECT

  # === 【海外核心服务指向统一策略组】 ===
  - RULE-SET,google,PROXY
  - RULE-SET,proxy,PROXY
  - RULE-SET,gfw,PROXY
  - RULE-SET,tld-not-cn,PROXY
  - RULE-SET,telegramcidr,PROXY

  # === 【国内 IP 保底防线】 ===
  - RULE-SET,cncidr,DIRECT
  - GEOIP,CN,DIRECT

  # === 【白名单模式终极兜底】 ===
  - MATCH,PROXY
```

### 5.4 Script.js 配置

创建 `profiles/Script.js` 文件：

```javascript
// 动态将规则中的 PROXY 替换为订阅的主代理组

function main(config, profileName) {
  const proxyGroups = config["proxy-groups"] || [];
  const rules = config["rules"] || [];

  // 获取第一个代理组（主选择组）
  if (proxyGroups.length === 0) {
    return config;
  }

  const mainGroupName = proxyGroups[0].name;

  // 替换规则中的 PROXY 为主代理组名称
  config["rules"] = rules.map(rule => {
    if (typeof rule === "string") {
      return rule.replace(/,PROXY$/, `,${mainGroupName}`);
    }
    return rule;
  });

  return config;
}
```

**工作原理**：
1. 获取当前订阅的第一个代理组（通常是主选择组）
2. 遍历所有规则，将规则末尾的 `,PROXY` 替换为 `,主代理组名称`
3. 返回修改后的配置

**效果**：
- 红杏云订阅：`PROXY` → `红杏云`
- mojie订阅：`PROXY` → `节点选择`
- yueto订阅：`PROXY` → 其主代理组名称

### 5.5 关联配置到订阅

在 `profiles.yaml` 中将 Merge 和 Script 关联到所有订阅：

```yaml
- uid: RGkyhAYQT1Z0
  type: remote
  name: hongxingyun
  option:
    merge: Merge      # 关联 Merge.yaml
    script: Script    # 关联 Script.js
```

对每个订阅重复此配置，或在 Clash Verge UI 中：
1. 右键订阅 → 编辑信息
2. 在"扩展覆写配置"中选择 Merge
3. 在"扩展脚本"中选择 Script

### 5.6 配置优势

✅ **统一管理**：一套规则应用到所有订阅

✅ **自动适配**：自动识别不同订阅的主策略组

✅ **易于维护**：修改 Merge.yaml 即可更新所有订阅的规则

✅ **保留原配置**：不覆盖订阅原有的代理组和节点



## 六、性能优化说明

### 6.1 规则匹配性能

**常见误解**：增加大量规则会导致代理变慢

**实际情况**：Clash Meta/Mihomo 内核使用高效的数据结构

#### 底层优化机制

1. **哈希表与前缀树（Trie）**
   - 域名规则使用前缀树存储
   - 时间复杂度：O(1) 或 O(log n)
   - 几万条域名规则的匹配耗时：微秒级

2. **IP路由基数树（Radix Tree）**
   - IP段规则使用基数树
   - 高效的IP段匹配算法
   - 对现代CPU来说计算量微不足道

3. **分层过滤**
   - 优先匹配域名规则
   - 域名未命中才匹配IP规则
   - 避免不必要的计算

### 6.2 实际性能收益

#### 收益A：减少不必要的连接重试
- **国内流量**：直连国内服务器，避免绕道国外
- **国外流量**：直接走代理，避免墙内超时重试
- **结果**：连接建立速度显著提升

#### 收益B：广告拦截（REJECT规则）
- 本地直接拦截广告请求
- 节省带宽和等待时间
- 网页渲染速度提升

### 6.3 唯一的"变慢"场景

**启动时下载规则集**：
- 首次启动或更新订阅时需要下载规则集文件
- 下载完成后缓存到本地 `ruleset/` 目录
- 后续运行完全是内存检索，极速响应

**结论**：规则集带来的性能提升远大于规则匹配的计算开销



## 七、常见技巧和最佳实践

### 7.1 连接监控

在 Clash Verge 的"连接"标签页可以查看：
- 当前所有活动连接
- 每个连接使用的代理节点或DIRECT
- 规则匹配情况
- 实时流量统计

**用途**：
- 验证规则是否正确生效
- 排查特定网站的连接问题
- 监控流量使用情况

### 7.2 代理端口配置

Clash Verge 默认代理端口：
- **Mixed Port**：7897（HTTP + SOCKS5混合端口）
- **SOCKS Port**：7898
- **HTTP Port**：7899

**手动配置代理的应用**：
```
代理地址：127.0.0.1
端口：7897
```

**常见需要手动配置的应用**：
- Git：`git config --global http.proxy http://127.0.0.1:7897`
- npm：`npm config set proxy http://127.0.0.1:7897`
- Docker：在Docker Desktop设置中配置代理
- 终端工具：设置环境变量 `HTTP_PROXY` 和 `HTTPS_PROXY`

### 7.3 自定义规则

在 `Merge.yaml` 的 `rules` 部分添加自定义规则：

```yaml
rules:
  # 自定义直连域名
  - DOMAIN,example.com,DIRECT
  - DOMAIN-SUFFIX,mysite.com,DIRECT
  
  # 自定义代理域名
  - DOMAIN,blocked-site.com,PROXY
  
  # 其他规则...
```

### 7.4 规则优先级

规则按**从上到下**的顺序匹配，**第一条匹配的规则生效**。

**建议顺序**：
1. 用户自定义规则（最高优先级）
2. 局域网和本地规则
3. 广告拦截规则
4. 白名单直连规则
5. 代理规则
6. 国内IP规则
7. 兜底规则（MATCH）

### 7.5 规则集更新

规则集会根据 `interval` 设置自动更新（默认86400秒 = 24小时）。

**手动更新**：
1. 右键订阅 → 更新
2. 或重启 Clash Verge

**规则集缓存位置**：
`C:\Users\<用户名>\AppData\Roaming\io.github.clash-verge-rev.clash-verge-rev\ruleset\`



## 八、常见问题排查

### 8.1 规则不生效

**检查步骤**：
1. 确认 Merge 和 Script 已关联到订阅（在 `profiles.yaml` 中检查）
2. 重新加载配置或重启 Clash Verge
3. 在"连接"标签页查看规则匹配情况
4. 检查规则集文件是否下载成功（查看 `ruleset/` 目录）

### 8.2 配置文件语法错误

**症状**：Clash Verge 启动失败或订阅加载失败

**解决方法**：
1. 检查 YAML 语法（缩进必须使用空格，不能使用Tab）
2. 使用在线 YAML 验证工具检查语法
3. 查看 Clash Verge 日志文件（`logs/` 目录）

### 8.3 Script 不生效

**可能原因**：
1. Script 文件语法错误
2. Script 未正确关联到订阅
3. Script 逻辑错误

**调试方法**：
1. 在 Script 中添加 `console.log()` 输出调试信息
2. 查看 Clash Verge 控制台输出
3. 简化 Script 逻辑，逐步测试

### 8.4 代理速度慢

**排查方向**：
1. 测试节点延迟（在代理组中点击测速）
2. 切换到其他节点
3. 检查是否有大量广告请求（查看连接列表）
4. 确认规则是否正确（国内流量是否误走代理）



## 九、参考资源

### 9.1 官方文档
- **Clash Verge 文档**：https://tangwenlongno1.github.io/clash-verge-rev.github.io/
- **Clash Meta 文档**：https://wiki.metacubex.one/

### 9.2 规则集资源
- **Loyalsoldier/clash-rules**：https://github.com/Loyalsoldier/clash-rules
  - 高质量的分流规则集
  - 定期更新维护
  - 支持白名单和黑名单模式

### 9.3 配置示例
- 本文档中的 Merge.yaml 和 Script.js 配置
- Clash Verge 官方示例配置



## 十、总结

### 10.1 核心要点

1. **多订阅管理**：支持多个机场订阅，灵活切换
2. **全局配置**：使用 Merge + Script 实现统一规则管理
3. **规则集优化**：采用 Loyalsoldier 规则集，实现精准分流
4. **性能优化**：现代内核的高效匹配算法，规则越多越精准

### 10.2 最佳实践

✅ 使用全局 Merge 配置，避免直接修改订阅文件

✅ 使用 Script 动态适配不同订阅的代理组

✅ 采用白名单模式，默认代理，国内直连

✅ 定期更新订阅和规则集

✅ 监控连接情况，验证规则效果

### 10.3 配置文件位置速查

```
C:\Users\<用户名>\AppData\Roaming\io.github.clash-verge-rev.clash-verge-rev\
├── profiles/
│   ├── Merge.yaml          # 全局规则配置
│   └── Script.js           # 动态脚本
├── profiles.yaml           # 订阅管理
├── ruleset/                # 规则集缓存
└── logs/                   # 日志文件
```


