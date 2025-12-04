---
title: BLOG搭建笔记之五：添加评论系统
tags: blog
---

## 关于
jekyll内置了对许多评论系统的支持，包括disqus, gitalk, valine。这里只推荐valine，这是一款基于LeanCloud的快速、简洁且高效的无后端评论系统。

## 配置步骤

配置步骤非常简单，在leancloud官网申请一个账户，并创建应用获取app id和key，然后填入_config.yml文件即可。详细配置步骤，参考[Valine快速开始](https://valine.js.org/quickstart.html)。

这里注意，超过30天没有请求被应用会被归档，会显示
```
Code 504: The app is archived, please restore in console before use. [400 GET]
```
因此需要定期访问博客，要恢复的话需要实名认证。之前LeanCloud就貌似因为敏感问题被封过一段时间，国内节点关闭注册了，之后开放了就需要实名认证才能创建项目。
​ 由于之前注册的是国际服，所以无需认证也可以创建项目，不过数据是要不回来了。
目前的方法就只能是删除原来的项目，重新创建一个项目来接收Comments。
可以到控制台-设置-基本信息-删除应用中进行删除，然后重新创建一个。

## 关于Pageview文章点击量

_config.yml中也内置有Pageview页面访问统计的功能，试了很久但是都没有成功，有地方说需要将个人blog备案之后，才能使用页面访问统计，因此这里直接跳过。

## 关于用户行为分析

建议使用Google Analytics，注册账号后，将生成的跟踪id填入_config.yml文件的tracking_id栏中即可。