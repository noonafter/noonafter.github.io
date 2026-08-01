---
layout: article
title: Python 环境与依赖管理的工具谱系
date: 2026-02-01 10:00:00 +0800
tags:
  - python
  - uv
  - packaging
excerpt: Python 环境与依赖管理的工具谱系：从 venv/pip 到 uv、Poetry、Conda 与 Pixi 的定位对比，以及 uv 作为新一代默认工具的详解。
---

## 一、环境、包与项目：三个层次的概念模型

### 1、环境管理器与包管理器

**环境管理器**负责创建、删除、切换隔离环境，关注不同项目之间如何互不干扰。**包管理器**负责从软件源下载、卸载、升级软件包，关注安装哪些库、版本号与下载来源。

Conda 将两个角色合二为一：`conda create` 建环境，`conda install` 装包。Python 原生生态中两者分离：`venv` 只隔离环境，`pip` 只装卸包。

### 2、现代工具的分层模型

2026 年的 Python 工具链可抽象为三个层次：

| 层次 | 作用 | 代表工具 |
|:-----|:-----|:---------|
| 环境层 | 提供隔离的运行时目录 | `venv`、Conda 环境、uv 管理的 `.venv`、Pixi 的 `.pixi` |
| 包源层 | 提供软件包仓库 | PyPI（wheel/sdist）、conda-forge 与 defaults（二进制包） |
| 项目配置层 | 声明项目元数据与依赖 | `pyproject.toml` + 锁文件 |

不同工具在各层次上的覆盖范围不同，这决定了它们的定位差异。关于 `pyproject.toml` 各配置段的解析，参见[《pyproject.toml：现代 Python 项目的声明式配置标准》](./2026-02-01-pyproject-toml.md)。

## 二、主流工具全景

### 1、venv + pip：Python 原生基线

`venv` 与 `pip` 随 Python 自带，是最低门槛的组合：

```bash
python -m venv .venv
source .venv/bin/activate
pip install requests
```

该组合没有锁文件（`pip freeze` 只能固定直接依赖，无法锁定完整解析树）、没有 Python 版本管理、没有项目级管理能力。适合简单脚本、教学场景与需要最小化依赖的 CI 任务。

### 2、venv + pip-tools：传统锁定方案

`pip-tools` 补上 pip 缺失的锁定能力：`pip-compile` 将顶层依赖解析为带精确版本的 `requirements.txt`，`pip-sync` 按锁定版本安装：

```bash
pip-compile requirements.in   # 生成锁定 requirements.txt
pip-sync                      # 按锁定版本安装
```

`requirements.txt` 锁文件按平台生成，跨平台团队需各自生成。pip 26.x 起提供实验性的 `pip lock` 命令（PEP 751，生成 `pylock.toml`），但同样平台相关。该方案是不引入第三方管理器时的企业最简选项，功能完整但手动、较慢。

### 3、Poetry：项目级管理器

Poetry 于 2018 年发布，采用 Cargo 风格的项目管理：`pyproject.toml` 声明依赖，`poetry.lock` 固定精确版本，自动创建虚拟环境，并内置发布流程：

```bash
poetry add requests
poetry install
poetry run python -m gold_system.main
poetry publish
```

Poetry 的局限：依赖解析器较慢，不管理 Python 版本（需搭配 pyenv），不支持 workspace。它仍是发布 PyPI 库的主流选择，既有 Poetry 项目也无需迁移。

### 4、uv：新一代默认工具

uv 由 Astral 开发（Ruff 的创造者），2024 年初发布，2025 年 2 月达到 1.0。2026 年 3 月 19 日，OpenAI 宣布收购 Astral，uv 团队并入 Codex 部门，工具保持开源。uv 月下载量已超过 1.26 亿。

uv 用单个 Rust 二进制替代 pip、pip-tools、pipx、pyenv、twine、virtualenv 等多个工具，详情见第三章。

### 5、Conda / Mamba / Micromamba：跨语言二进制包

Conda 是环境与包管理二合一的跨语言工具，通过 `conda-forge` 等频道提供预编译二进制包，可管理 Python、R、C++ 以及 CUDA、MKL、HDF5 等系统库：

```bash
conda create -n gold python=3.12 numpy
conda activate gold
```

`environment.yml` 是依赖规格而非锁文件，版本会在重新解析时漂移；真正的可复现需借助第三方 `conda-lock`。Conda 解析慢、环境创建耗时长。`mamba` 是 C++ 重写的加速版本，`micromamba` 是无需 base 安装的单二进制版本。

### 6、Pixi：Conda 生态的现代实现

Pixi 由 prefix.dev 开发，基于 Rust 的 rattler 库重建 conda 生态。它以 workspace 为核心：`pixi.toml` 声明依赖，`pixi.lock` 固定版本，同时支持 conda-forge 与 PyPI（PyPI 部分复用 uv 的解析器）：

```bash
pixi init gold && cd gold
pixi add python=3.12 numpy
pixi run python -m gold_system.main
```

Pixi 没有 base 环境，环境存放在项目内 `.pixi` 目录，内置跨平台 tasks，环境创建比 conda 快 5-8 倍。它是 conda 生态用户获得锁文件与 PyPI 集成的新选择。

### 7、工具对比总表

| 维度 | venv + pip | pip-tools | Poetry | uv | Conda/Mamba | Pixi |
|:-----|:-----------|:----------|:-------|:---|:------------|:-----|
| 锁文件 | 无 | `requirements.txt`（平台相关） | `poetry.lock` | `uv.lock`（通用） | `conda-lock`（第三方） | `pixi.lock` |
| Python 版本管理 | 无 | 无 | 无（需 pyenv） | 内置 | 内置 | 内置 |
| 非 Python 依赖 | 否 | 否 | 否 | 否（仅 PyPI） | 是 | 是 |
| 安装速度 | 基线 | 慢 | 慢 | 快 10-100 倍 | 慢 | 较快 |
| 发布到 PyPI | twine | twine | `poetry publish` | `uv publish` | 否 | 否 |
| workspace 支持 | 否 | 否 | 否 | 是 | 否 | 是 |

## 三、uv 详解

### 1、uv 是什么

uv 是 Astral 用 Rust 编写的 Python 包与项目管理器，用单个工具替代 `pip`、`pip-tools`、`pipx`、`poetry`、`pyenv`、`twine`、`virtualenv`。安装速度比 pip 快 10-100 倍，是单静态二进制，运行时无需预装 Python。

### 2、核心能力

| 能力 | 命令 |
|:-----|:-----|
| 项目初始化 | `uv init` |
| 添加 / 移除依赖 | `uv add` / `uv remove` |
| 创建锁文件 | `uv lock` |
| 同步环境 | `uv sync`（精确同步，移除锁文件外多余包） |
| 运行命令 | `uv run`（自动创建并更新环境） |
| 查看依赖树 | `uv tree` |
| 构建与发布 | `uv build` / `uv publish` |
| Python 版本管理 | `uv python install` / `uv python pin` |
| pip 兼容接口 | `uv pip install` / `uv pip compile` / `uv pip sync` |

**通用锁文件**：`uv.lock` 是跨平台锁文件，uv 的可复现保证，应提交到版本库。

**自动同步**：`uv run` 每次执行前检查 `pyproject.toml`、`uv.lock` 与环境三者是否一致，不一致则自动更新。`uv sync` 执行精确同步，移除锁文件之外的包。

**workspace**：Cargo 风格的多包工作区，多个包共享单一 `uv.lock`，`uv run --package` 可在任意成员中运行命令。

**内联脚本依赖**：`uv run script.py` 支持脚本头部内联依赖元数据，在临时环境执行单文件脚本。

### 3、pyproject.toml 与锁文件的分工

`pyproject.toml` 声明的是**宽泛约束**：`dependencies = ["requests>=2.31"]` 表示项目接受 2.31 及以上任意版本，属于依赖的规格。锁文件记录的则是**精确解析结果**：当前安装的 `requests` 具体是哪个版本、它的全部传递依赖分别是哪个版本。两者对应"声明"与"解析"两个阶段。

缺少锁文件时的典型问题：假设今天解析 `requests>=2.31` 得到 2.32.1，半年后另一名开发者或 CI 再次解析，解析器会选择当时最新的 2.33.0。同一个 `pyproject.toml` 因此产生不同的依赖树，出现"本机能跑、其他机器跑不了"的不可复现问题。锁文件通过固定整个解析树消除这一不确定性。

另一个原因：`pyproject.toml` 只声明直接依赖，而传递依赖（依赖的依赖）由解析器决定，数量可能远超直接依赖。只有锁文件能完整固定它们。

"规格 + 锁文件"的配对是所有现代语言包管理器的通用模式：Node.js 的 `package.json` 与 `package-lock.json`、Rust 的 `Cargo.toml` 与 `Cargo.lock`、Ruby 的 `Gemfile` 与 `Gemfile.lock` 同理。

uv 在此基础上增加了跨平台通用性：`uv.lock` 在解析时同时考虑所有操作系统、架构与 Python 版本组合，单个文件即可保证各平台安装结果一致，因此应提交到版本库。

### 4、锁文件的生命周期与工程管理

**锁文件由工具自动生成，不应手动编辑**。项目中三个文件的编辑权限不同：`pyproject.toml` 是手写文件，声明依赖意图；锁文件是自动生成的只读文件，记录解析结果；`.venv` 是纯生成物，随时可删除重建。

修改依赖的标准流程是"改规格、再生成"：

| 场景 | uv 操作 |
|:-----|:--------|
| 新增 / 移除依赖 | `uv add requests` / `uv remove requests`，自动更新 pyproject.toml、uv.lock 与环境 |
| 升级单个依赖 | `uv lock --upgrade-package requests` |
| 升级全部依赖 | `uv lock --upgrade` |
| 从锁文件安装 | `uv sync`，不改变锁文件 |

手动编辑锁文件没有意义：下一次重新解析会覆盖改动，且手工改动容易造成锁文件与规格不一致。

工程中常用的管理方式：

**提交锁文件到版本库**。`uv.lock`、`poetry.lock` 纳入 git，作为团队与 CI 安装的一致基准。pyproject.toml 记录意图，锁文件记录事实。

**CI 中校验一致性**。`uv run --locked` 在锁文件与 pyproject.toml 不一致时直接报错，防止 CI 静默安装未经评审的依赖。`--frozen` 则完全不更新锁文件，只按锁文件安装。

**依赖升级作为独立改动**。升级单个依赖用 `--upgrade-package`，全部升级用 `--upgrade`。升级结果以锁文件 diff 形式随代码评审审阅，可追溯某个依赖何时升级到什么版本。

**锁文件 diff 纳入评审**。锁文件不手写，但它的变更需要人工审阅：新增依赖、传递依赖升级、版本约束收紧都体现在锁文件 diff 中。

其他工具的管理方式对照：

| 工具 | 修改入口 | 生成锁文件 | 从锁安装 | 单包升级 |
|:-----|:---------|:-----------|:---------|:---------|
| uv | `uv add` 或编辑 pyproject.toml | `uv lock` | `uv sync` | `uv lock --upgrade-package` |
| pip-tools | 编辑 requirements.in | `pip-compile` | `pip-sync` | `pip-compile --upgrade-package` |
| Poetry | `poetry add` 或编辑 pyproject.toml | `poetry lock` | `poetry install` | `poetry update <package>` |
| Conda | 编辑 environment.yml | conda-lock | `conda-lock install` | 修改 environment.yml 后重新生成锁文件 |

### 5、优点

- **速度快**：Rust 实现、并行下载与全局缓存，冷安装与依赖解析比 pip 快 10-100 倍，CI 中差距更大
- **一体化**：一个二进制替代 pyenv、virtualenv、pip、pip-tools、poetry 的主要功能
- **可复现**：`uv.lock` 通用锁文件，跨平台确定性安装
- **低迁移成本**：`uv pip` 接口与 pip 兼容，现有工作流可直接替换
- **无需预装 Python**：单二进制可自行安装 Python 并创建环境

### 6、缺点与局限

- **仅支持 PyPI**：无法安装 conda-forge 的 CUDA 工具链、MKL 优化库等非 Python 二进制包
- **无插件系统**：Poetry 的插件生态（如 poetry-dynamic-versioning）没有 uv 等价物
- **锁文件格式专属**：`uv.lock` 只能由 uv 读取（可导出 `requirements.txt`、`pylock.toml`、CycloneDX SBOM）

## 四、2026 年生态现状

Python 打包生态已从 2020-2023 年 pipenv / poetry / flit / hatch 并存的混乱期，收敛出明确分工：

- **新项目默认 uv**：社区共识是新建项目直接使用 uv
- **Poetry** 保留给既有项目与 PyPI 库发布
- **Conda / Mamba / Pixi** 守住科学计算与非 Python 依赖领域
- **pip** 仍是兜底基线，不会消失

## 总结

现代 Python 环境管理工具围绕"环境层、包源层、项目配置层"展开。uv 以单二进制统一了环境与依赖管理，成为新项目默认；Poetry 服务库发布；Conda / Pixi 管理跨语言二进制依赖。选型应先判断是否需要非 Python 依赖，再决定工具归属。

## 延伸阅读

- [pyproject.toml：现代 Python 项目的声明式配置标准](./2026-02-01-pyproject-toml.md)
- [Python 环境选型与工程实践](./2026-02-01-python-env-selection.md)
