---
title: BLOG搭建笔记之二：自定义域名
tags: blog
---


个人Pages站点建立之后，默认域名是username.github.io，项目Pages站点默认域名是username.github.io/repository。GitHub Pages支持使用自定义域名，以下介绍如何使用自定义域名来访问Pages站点

<!--more-->

## 购买域名
域名可以从各种域名服务提供商处进行购买，国内的域名提供商有阿里云、腾讯云、华为云等，国外域名提供商有GoDaddy，Dynadot，Porkbun等，购买细节不再赘述。

## 验证自定义域名
Github 提供了验证自定义域名的功能，该功能可以防止恶意对手发起域名劫持一类的攻击。

点击个人头像->Settings->Pages，点击Add a domain。跟随GItHub提示，到自己的云服务控制台中进行操作。这里说是要最长24小时完成DNS验证，其实一般几分钟就验证完了。

在完成TXT记录添加之后，可以在终端中输入下列命令来，根据返回值来判断TXT记录是否添加成功：
```bash
nslookup -q=txt _github-pages-challenge-username.xxxx.cn
```


这里补充一点关于域名的知识，记录类型包括：

- A记录（Address Record）：将域名映射到一个IPv4地址。
例如：noonafter.cn A 185.199.108.153

- AAAA记录（IPv6 Address Record）：将域名映射到一个IPv6地址。
例如：noonafter.cn AAAA 2001:db8::1

- CNAME记录（Canonical Name Record）：将一个域名指向另一个域名，即别名记录。
例如：www.noonafter.cn CNAME noonafter.github.io

- MX记录（Mail Exchange Record）：指定处理邮件的邮件服务器,数字代表优先级，较小的值优先级较高。
例如：example.com MX 10 mail.example.com

- TXT记录（Text Record）
功能：存储文本信息，通常用于域名验证、SPF、DKIM等邮件认证机制，可以用于邮件反垃圾机制、域名验证等。
例如：example.com TXT "v=spf1 include:_spf.example.com ~all"

## 映射自定义域名

**Step1**：DNS配置。在域名服务提供商的控制台中，配置 A 记录类型，将自定义域名指向 IP 地址。

记录名为@，类型为A，，记录值填为 Github 提供的 IP 地址（这四个 IP 地址大家都一样），如下所示。其他值保持默认，配置完成后保存。
```
185.199.108.153
185.199.109.153
185.199.110.153
185.199.111.153
```

这里注意，有的服务提供商，是一条记录下填写多个记录值。而有的服务商是添加多条记录，每个记录值填写一个ip地址，并且有的服务商默认一个域名@记录有上限（关系到负载均衡），比如，腾讯云免费版同一个域名的负载均衡只支持2个ip，大家根据自己域名服务提供商规则进行填写。

也可以添加CNAME记录，将子域名指向apex域名（即顶级域名，就是服务商处买的域名，比如noonafter.cn）。

**Step2**：GitHub仓库配置。进入仓库，点击Settings->Pages，找到Custom domain，输入自己购买的域名，点击Save。几分钟后，GitHub会在仓库中自动添加CNAME文件，这时便可以通过自定义的域名来访问pages站点了。

## Cloudflare CDN 加速
由于国内访问github服务器不是很稳定，所以可以使用Cloudflare对静态网站进行缓存和加速。Cloudflare 是全球领先的 CDN 服务提供商，通过分布在全球的数据中心节点缓存你的网站内容，让用户从最近的节点获取数据，大幅提升访问速度和稳定性。

第一步：注册和添加网站

注册 Cloudflare 账户，访问 cloudflare.com，使用邮箱注册，选择免费套餐即可。添加网站，控制台点击 "Add a Site"，输入你的域名（如 example.com），选择免费计划。

第二步：更改域名服务器

这是最关键的一步！Cloudflare 会提供两个域名服务器：

lara.ns.cloudflare.com

paul.ns.cloudflare.com

具体操作步骤：

登录你的域名注册商（如腾讯云），进入控制台，选择修改DNS服务器。

替换为 Cloudflare 提供的域名服务器

等待生效（通常需要几分钟到几小时）

第三步：配置 DNS 记录

在 Cloudflare 的 DNS 设置中，添加你的网站记录，可以添加多条记录，包括A，AAAA和CNAME记录等。

第四步：开启 CDN 缓存
进入 Caching → Configuration：

推荐缓存设置

缓存级别：标准

浏览器缓存 TTL：1个月

总是在线(always onlion)：开启

第五步：SSL/TLS 配置

在 SSL/TLS 标签页：

加密模式：选择 "完全(严格)"

始终使用 HTTPS：开启

HSTS：建议开启加强安全






## 参考文章

自定义域名教程参考：
<https://blog.csdn.net/qq_34902437/article/details/140298754>
Cloudflare配置参考：
<https://ecomools.com/cloudflare-cdn/>
