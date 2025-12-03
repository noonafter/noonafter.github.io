---
title: BLOG搭建笔记之五：添加评论系统
tags: blog
---

## 关于
jekyll内置了对许多评论系统的支持，包括disqus, gitalk, valine。这里只推荐valine，这是一款基于LeanCloud的快速、简洁且高效的无后端评论系统。

## 配置步骤

配置步骤非常简单，在leancloud官网申请一个账户，并创建应用获取app id和key，然后填入_config.yml文件即可。详细配置步骤，参考[Valine快速开始](https://valine.js.org/quickstart.html)

## 关于Pageview文章点击量

_config.yml中也内置有Pageview页面访问统计的功能，试了很久但是都没有成功，有地方说需要将个人blog备案之后，才能使用页面访问统计，因此这里直接跳过。

## 关于用户行为分析

建议使用Google Analytics，注册账号后，将生成的跟踪id填入_config.yml文件的tracking_id栏中即可。