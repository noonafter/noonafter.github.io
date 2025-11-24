---
title: BLOG折腾笔记之一：快速开始
tags: blog
---


## 关于GitHub Pages和Jekyll
[GitHub Pages](https://docs.github.com/zh/pages/getting-started-with-github-pages/about-github-pages)是GitHub提供的静态网站托管服务，支持从GitHub仓库直接获取HTML，CSS，Javascript等网站文件，并内置支持jekyll项目构建并发布网站。有三种类型的 GitHub Pages 站点：项目、用户和组织。每个帐户只能为创建一个用户或组织站点，项目站点则没有限制。

[Jekyll](https://docs.github.com/zh/pages/setting-up-a-github-pages-site-with-jekyll/about-github-pages-and-jekyll)是使用ruby语言写的一个静态网站生成器，可以用ruby语言下的gem包管理器进行安装，还提供本地实时服务器进行随时查看。

借助以上两个工具，可以快速搭建个人blog或者是为项目搭建介绍网站。[点击这里](https://noonafter.cn/archive.html)可以预览使用GitHub Pages和Jekyll搭建个人网站的效果。

<!--more-->

## 快速开始
**Step1**：为了快速上手，可以直接fork现有的Jekyll主题仓库作为模版，这条路径适合与我一样对HTML，CSS，Javascript，Liquid等了解较少的前端小白，先快速上手获得正反馈，再慢慢研究。这里推荐几个star比较多的主题，比如[TeXt Theme](https://github.com/kitian616/jekyll-TeXt-theme)，[Lanyon Jekyll theme](https://jekyllthemes.io/theme/lanyon)，[Chirpy Jekyll theme](https://github.com/cotes2020/jekyll-theme-chirpy)，当然还有很多主题可供选择，可以到以下jekyll主题网站自行挑选：

[jekyllthemes.org](http://jekyllthemes.org/)

[jekyllthemes.io](https://jekyllthemes.io/free)

**Step2**：在fork完后，由于仓库的Pages功能默认是关闭的，需要手动打开。到自己仓库中找到刚fork的仓库，选择**Settings->Pages**，选择一个分支（一般是main）然后save，这里选择main分支之后，还会出现一个文件夹，这是让你选择pages网页存放的位置，一般默认pages页面是在根目录下，但是如果是为项目所搭建的pages网站，也可能选择/docs目录，因为根目录下还有很多与pages无关的项目文件。

值得注意的是，GitHub Pages支持两种发布方式，一种是从分支发布（默认情况），另一种是GitHub Actions方式发布。如果不需要对站点的生成过程进行任何控制，则建议保持默认的从分支发布。从分支发布任然需要打开GitHub Actions功能，因为从分支发布底层任然是使用GitHub Actions来完成Jekyll项目的构建和发布过程，可以到仓库的**Settings->Actions->General**中查看GitHub Actions是否打开（默认是打开的）。

**Step3**：打开pages功能后，如果是创建个人用户或者是组织的站点（一个账号只能有一个），还需要在Settings->General中修改仓库的名字为username.github.io，username必须是自己的用户名，否则无法创建成功。改名成功后，就可以在浏览器地址栏输入username.github.io来访问自己的blog了。



当然也可以跟随[GitHub Pages官方教程](https://docs.github.com/zh/pages/quickstart)，一步步从头开始搭建自己的网站，但官方教程篇幅比较长，可能跟着研究了很久还是不能搭出自己想要的效果。


## 搭建本地开发环境（可选）
GitHub对Jekyll项目提供了从构建到部署的完整支持，在改动push到远端服务器之后，GitHub Actions会自动完成build and deployment。但是为了**更方便地对网站进行预览和测试**，依然有必要在本地搭建完整的开发环境。

Jekyll官方不推荐在Windows下使用Jekyll，因此，需要在linux下进行开发环境的搭建。如果对linux不熟悉，可以参考[Windows平台下类linux环境搭建](https://noonafter.cn/2024/12/31/linux-environment.html)进行操作。以下操作步骤均在linux环境下进行。

### 安装Ryby和Bundle
**Step1**：安装Ruby。在bash中运行：
```bash
sudo apt install ruby-full
```
ruby-full会同时安装gem。gem是ruby的包管理器，类似于python的pip。


**Step2**：安装bundler。运行：
```bash
gem install bundler
```
建议使用 Bundler 安装和运行 Jekyll。 Bundler 可管理 Ruby gem 依赖项，减少 Jekyll 构建错误和阻止环境相关的漏洞。这里注意安装的是**bundler**，而不是bundle（后续使用bundler，执行的是bundle命令）

### 搭建本地Jekyll服务器
**Step3**：进入本地仓库文件夹中（需要先clone仓库到本地），运行：
```bash
sudo bundle install
```
注意step2中已经安装过bundler了，这里的install并不是安装bundle。而是根据项目中的 Gemfile 文件来安装所有依赖的 Ruby gem 包，生成Gemfile.lock。

当然可能会报错，没有报错的直接跳到step4。报错信息如下：
```
Gem::Ext::BuildError: ERROR: Failed to build gem native extension.

An error occurred while installing bigdecimal (3.1.9), and Bundler cannot continue.

In Gemfile:
  jekyll-text-theme was resolved to 2.2.6, which depends on
    jemoji was resolved to 0.13.0, which depends on
      html-pipeline was resolved to 2.14.3, which depends on
        activesupport was resolved to 8.0.1, which depends on
          bigdecimal

make failedNo such file or directory - make

checking for -lcrypto... no checking for openssl/ssl.h... no
 ```

报错显示 make failedNo such file or directory - make，表示缺少构建工具，并且OpenSSL 相关依赖未找到。则需要安装对应依赖项：
```bash
sudo apt install build-essential libssl-dev zlib1g-dev ruby-dev make
```

依赖的包如下：
- build-essential：包含 make、gcc 等工具。
- libssl-dev：提供 OpenSSL 开发库。
- zlib1g-dev：处理压缩相关的库。
- ruby-dev：Ruby 的开发头文件。

这样所有依赖包都装好了，重新执行命令
```bash
sudo bundle install
```
值得注意的是：gem会弹出警告：不要以root权限运行bundler。这里直接忽略，因为如果直接bundle install会提示权限不够，不能删除或者创建。

**Step4**：创建本地jekyll服务器，以便实时预览
```bash
bundle exec jekyll serve
```
这里便已经搭好本地jekyll服务器了，浏览器输入 127.0.0.1:4000 可以查看当前构建好的网页。

值得注意的是，如果修改了_config.yml文件中的配置项，需要重启jekyll服务器才能生效。而如果仅是修改了其他文件，可以重新打开一个bash运行：
```bash
bundle exec jekyll build
```
对项目进行重新构建，当然也可以加上--watch来自动监视改动进行构建。

后续文章介绍如何自定义域名、_config.yml文件的用途及修改、如何添加专栏/文章、如何修改logo、添加评论系统、页面访问统计、用户行为分析等功能。


## 参考文章
官方搭建教程：
<https://docs.github.com/zh/pages/quickstart>

TeXt主题教程：
<https://kitian616.github.io/jekyll-TeXt-theme/docs/en/quick-start>


