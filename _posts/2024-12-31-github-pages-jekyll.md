---
title: 使用Github pages和Jekyll搭建个人blog之一：快速开始
tags: jekyll
---


## 关于GitHub Pages和Jekyll
[GitHub Pages](https://docs.github.com/zh/pages/getting-started-with-github-pages/about-github-pages)是GitHub提供的静态网站托管服务，支持从GitHub仓库直接获取HTML，CSS，Javascript等网站文件，并内置支持jekyll项目构建并发布网站。有三种类型的 GitHub Pages 站点：项目、用户和组织。每个帐户只能为创建一个用户或组织站点，项目站点则没有限制。

[Jekyll](https://docs.github.com/zh/pages/setting-up-a-github-pages-site-with-jekyll/about-github-pages-and-jekyll)是使用ruby语言写的一个静态网站生成器，可以用ruby语言下的gem包管理器进行安装，还提供本地实时服务器进行随时查看。

借助以上两个工具，可以快速搭建个人blog或者是为项目搭建介绍网站。[点击这里](noonafter.cn)可以预览使用GitHub Pages和Jekyll搭建个人网站的效果。

## 快速开始

**Step1**：为了快速搭建器自己的blog，我选择了直接fork现有的GitHub Pages模版仓库，这条路径适合与我一样对HTML，CSS，Javascript，Liquid等了解较少的前端小白，先快速上手获得正反馈，再慢慢研究。这里推荐几个自己喜欢的模版，比如[TeXt Theme](https://github.com/kitian616/jekyll-TeXt-theme)，[Lanyon Jekyll theme](https://jekyllthemes.io/theme/lanyon)，当然还有很多主题可供选择，可以到以下jekyll主题网站自行挑选：

[jekyllthemes.org](http://jekyllthemes.org/)

[jekyllthemes.io](https://jekyllthemes.io/free)

**Step2**：在fork完后，由于仓库的Pages功能默认是关闭的，需要手动打开。到自己仓库中找到刚fork的仓库，选择**Settings->Pages**，选择一个分支（一般是main）然后save，这里选择main分支之后，还会出现一个文件夹，这是让你选择pages网页存放的位置，一般默认pages页面是在根目录下，但是如果是为项目所搭建的pages网站，也可能选择/docs目录，因为根目录下还有很多与pages无关的项目文件。

值得注意的是，GitHub Pages支持两种发布方式，一种是从分支发布（默认情况），另一种是GitHub Actions方式发布。如果不需要对站点的生成过程进行任何控制，则建议保持默认的从分支发布。从分支发布任然需要打开GitHub Actions功能，因为从分支发布底层任然是使用GitHub Actions来完成Jekyll项目的构建和发布过程，可以到仓库的**Settings->Actions->General**中查看GitHub Actions是否打开（默认是打开的）。

**Step3**：打开pages功能后，如果是创建个人用户或者是组织的站点（一个账号只能有一个），还需要在Settings->General中修改仓库的名字为username.github.io，username必须是自己的用户名，否则无法创建成功。改名成功后，就可以在浏览器地址栏输入username.github.io来访问自己的blog了。



当然也可以跟随[GitHub Pages官方教程](https://docs.github.com/zh/pages/quickstart)，一步步从头开始搭建自己的网站，但官方教程篇幅比较长，可能跟着研究了很久还是不能搭出自己想要的效果。


## 搭建本地开发环境（可选）
虽然GitHub对Jekyll项目提供了从构建到部署的完整支持，但是为了更方便地对网站的改动进行预览和测试，依然有必要在本地搭建完整的开发环境。毕竟在改动push到GitHub之后，GitHub依然需要几分钟的时间完成构建和部署，并且有一些改动只是为了查看效果并不需要commit到仓库。

### linux环境
Jekyll官方不推荐在Windows下使用Jekyll，因此，第一步是搭建一个类linux的环境，对linux环境很熟的小伙伴可以跳过。具体方法可以参考[Windows平台下类linux环境搭建](https://noonafter.cn/2024/12/31/linux-environment.html)