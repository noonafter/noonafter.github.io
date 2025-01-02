---
title: BLOG折腾笔记之二：自定义域名
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

## 参考文章

自定义域名教程参考：
<https://blog.csdn.net/qq_34902437/article/details/140298754>

