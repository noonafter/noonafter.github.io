---
name: publish-post
description: Publish a prepared draft as a Jekyll post in this repository, including front matter, filename normalization, section numbering, and local image assets. Use for requests to publish,整理, or release a blog post.
metadata:
  short-description: Publish a draft to this Jekyll blog
---

# 发布博客文章

此技能仅适用于当前仓库 `D:\\alc\\blog\\noonafter.github.io`。只操作本仓库内的 `draft/`、`_posts/` 和 `assets/images/posts/`。

## 工作流程

1. **定位草稿**：用户给出路径时直接读取；否则列出 `draft/` 下的 Markdown 文件，并根据主题选择候选文件。读取目标文件及同目录图片素材。
2. **检查现状**：确认是否已有 front matter、目标文章是否已存在、正文是否以一级标题开始。已有 front matter 或同名目标文件时，先向用户说明冲突并等待决定，不覆盖已有内容。
3. **分析元数据**：从一级标题提取 `title`，根据正文生成 2-5 个英文技术标签。标签必须来自文章实际内容，不使用泛化标签。生成 1-2 句 `excerpt`（如项目配置需要）。
4. **生成 front matter**：正式文章使用以下字段；日期使用当前时间和 `+0800` 时区：

   ```yaml
   ---
   layout: article
   title: Article title
   date: 2026-03-27 15:30:00 +0800
   tags:
     - topic
     - technology
   ---
   ```

   删除正文中作为标题的首个 `#` 行，再将 front matter 放在文件开头。保留正文内容和 `<!--more-->`。
5. **添加章节编号**：若文章需要编号，先预览再执行 `python scripts/add_section_numbers.py <path> -i`。二级标题使用中文数字（`一、`、`二、`），三级标题在每个二级章节下从 `1、` 重新编号；已有编号应跳过。脚本不存在或不适用时不要手工批量改写。
6. **规范文件名**：目标文件格式为 `YYYY-MM-DD-title.md`。日期使用当前日期，标题转为简短的小写英文 slug（1-4 个单词，使用连字符）。不要凭空翻译专有名词；无法可靠生成 slug 时保留用户指定名称并说明。
7. **处理图片**：为文章创建 `assets/images/posts/YYYY-MM-DD-title/`，复制草稿中实际引用的图片，并将链接更新为 `/assets/images/posts/YYYY-MM-DD-title/<filename>`。先确认源文件存在，不复制未引用素材。
8. **处理系列引用**：仅在存在明确关联文章且目标文件名已确认时添加 Markdown 相对链接，例如 `[标题](./2026-03-27-topic.md)`。不要创建指向不存在文件的链接。
9. **发布到 `_posts/`**：将处理结果写入 `_posts/YYYY-MM-DD-title.md`，保留草稿原文件，除非用户明确要求移动或删除。检查 diff，确认 front matter、链接和资源路径正确。

## 交付检查

- 文章从 front matter 后的正文开始，不残留对话元信息。
- `title`、日期、文件名一致；代码块语言标识和 Markdown 链接语法正确。
- 所有图片源文件存在，引用路径与实际复制位置一致。
- 未覆盖已有文章，未写入凭据或外部配置。
- 视改动范围运行 `bundle exec jekyll build`，并报告命令结果。

完成后报告目标文件、生成的标签、图片数量和验证结果。除非用户明确要求，不执行 Git 提交、推送或发布操作。
