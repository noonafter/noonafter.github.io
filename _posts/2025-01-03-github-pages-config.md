---
title: BLOG搭建笔记之四：jekyll项目结构
tags: blog
---


## jekyll项目结构

- _config.yml：全局配置文件，用于定义站点的基本设置。

- _data/：存放静态数据，可以在模板中调用。
- _includes/：存放可重用的 HTML 片段（如头部、页脚）。
- _layouts/：存放布局模板，定义页面的结构。
- _posts/：存放博客文章，Jekyll 会生成静态页面。
- _sass/：存放 Sass 样式文件，编译成 CSS。
- _site/：生成的静态网站文件目录。
- .jekyll-cache 和 .jekyll-metadata：缓存和元数据文件，帮助优化构建过程。

以下对其中比较重要的文件/文件夹进行进一步解释。

## _config.yml文件
该文件是 Jekyll 项目的全局配置文件，配置项包括站点的标题、描述、URL、markdown增强配置、评论系统功能等。
关于_config.yml文件详细说明参考[TeXt主题配置](https://kitian616.github.io/jekyll-TeXt-theme/docs/zh/configuration)

## _post文件夹
该文件夹存放自己博客的文章，格式为.md或.html。每篇文章都必须命名为 yyyy-MM-dd-title.md（或 .html），每篇文章包括一个yaml信息头和主体。这些文件通过 jekyll serve/build 被解析和渲染，最终生成静态的 HTML 页面。

一个简单的的yaml信息头如下，前后均使用三横线---对头信息进行标记：
```
---
layout: article
date: 2025-01-03 10:29:30
title: BLOG折腾笔记之四：jekyll项目结构
tags: blog
---
```
三横线之间的内容为jekyll预定义的变量，可以使用jekyll预定义的变量，也可以自定义变量。jekyll会对yaml头中的变量进行解析，并控制html文件的生成过程，更多预定义变量参考[Jekyll文档front-matter](https://jekyllrb.com/docs/front-matter/)。

## _sass文件夹
该文件夹包含 Sass 样式文件。Sass 是一种 CSS 预处理器，它让你可以使用变量、嵌套等功能来编写更高效和可维护的 CSS。Jekyll 会自动将这些 .scss 文件编译成标准的 CSS 文件。也可以通过修改scss文件中的配置项来修改不同元素的样式

例如，在 _sass/common/_reset.scss文件中定义了关于标题、代码、图片等各种实体的样式，这些样式的值可能依赖于_variables.scss文件中的定义。

假设我觉得_reset.scss文件中关于code的字体太小了，我就可以将code元素相关的配置：
```
code {
  font-size: map-get($base, font-size);
  line-height: map-get($base, line-height-sm);
}
```
修改为
```
code {
  font-size: map-get($base, font-size-sm);
  line-height: map-get($base, line-height-sm);
}
```

## _includes 文件夹
该文件夹用于存放可重用的 HTML 片段（包括头部、页脚、导航栏等）。在布局文件或页面中，可以使用 \{ \% include \%\} 标签引用这些片段。

例如，footer.html 和 header.html
这两个文件分别存放页面的页脚和头部内容。通过 \{\% include header.html %\} 和 \{\% include footer.html %\} 可以在其他模板文件中调用它们。

这里的\{\% ... %\}是Liquid语言的语法，Jekyll使用Liquid作为模板引擎，来处理模板文件中的动态内容生成。Jekyll 将 Liquid 与 Markdown、HTML 等其他文件一起使用，帮助你生成最终的静态网页，参考[Jekyll文档Liquid](https://jekyllrb.com/docs/liquid/)。


## _layouts 文件夹
该文件夹存放 Jekyll 项目的布局模板。布局模板决定了页面的整体结构，通常包括头部、主体内容、页脚等。通过布局，你可以统一站点的外观和结构。

更多关于_layout的说明参考[TeXt布局](https://kitian616.github.io/jekyll-TeXt-theme/docs/zh/layouts)。


## 参考文章

Jekyll官方文档：<https://jekyllrb.com/docs/>

Jekyll全面介绍：<https://zhuanlan.zhihu.com/p/51240503>