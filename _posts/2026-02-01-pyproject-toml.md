---
layout: article
title: pyproject.toml：现代 Python 项目的声明式配置标准
date: 2026-02-01 09:00:00 +0800
tags:
  - python
  - pyproject
  - packaging
excerpt: pyproject.toml 作为 PEP 518 与 PEP 621 引入的现代 Python 项目配置标准，解析其核心配置段、与旧配置方式的对比及实用扩展。
---

## 一、pyproject.toml 是什么

`pyproject.toml` 是 Python 项目的核心配置文件，采用 TOML 格式（Tom's Obvious, Minimal Language）。它是 **PEP 518** 与 **PEP 621** 引入的现代 Python 项目配置标准，用于统一替代以往分散的配置文件：`setup.py`、`setup.cfg`、`requirements.txt`、`MANIFEST.in` 等。

配置文件由多个配置段组成，每段以 `[段名]` 开头。下文以黄金市场数据采集项目（`gold-system`）为例逐段解析。

## 二、核心配置段解析

### 1、[build-system] 构建系统配置

```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"
```

该段指定构建项目所需的工具和后端：

- `requires`：构建时依赖的包，此处要求 `setuptools` 版本不低于 68
- `build-backend`：指定构建后端为 `setuptools` 的构建元模块

执行 `pip install .` 或 `python -m build` 时，`pip` 读取此配置，准备隔离的构建环境，并在其中安装 `requires` 声明的包。

### 2、[project] 项目元数据与依赖

该段遵循 **PEP 621** 标准，声明项目的核心信息：

```toml
[project]
name = "gold-system"                              # 项目名称
version = "0.1.0"                                 # 版本号
description = "本地黄金市场数据采集与研究系统"       # 项目简述
requires-python = ">=3.11"                        # Python 版本要求
dependencies = [                                  # 运行时依赖
  "requests>=2.31",
  "akshare>=1.16",
]
```

字段说明：

- `name` / `version` / `description`：项目名称、版本号、简介
- `requires-python`：Python 版本下限要求
- `dependencies`：运行时依赖列表，替代传统的 `requirements.txt`

这些字段是标准化的，所有现代 Python 工具（`pip`、`pytest`、`mypy` 等）均可识别。安装项目时，`dependencies` 中的依赖会被自动安装。

### 3、[tool.setuptools.packages.find] 包发现配置

```toml
[tool.setuptools.packages.find]
include = ["gold_system*"]
```

该段告知 `setuptools` 如何自动发现项目中的包。`include` 限定只包含以 `gold_system` 开头的包（如 `gold_system`、`gold_system.utils` 等）。

默认情况下 `setuptools` 会尝试自动发现所有 Python 包，显式指定可避免将无关目录纳入打包范围。

## 三、与旧配置方式的对比

| 旧方式 | 现代方式 (`pyproject.toml`) |
|:-------|:---------------------------|
| `setup.py`（命令式脚本） | `[project]` 声明式配置 |
| `requirements.txt` | `dependencies` 字段 |
| `setup.cfg` | `[tool.*]` 各工具配置段 |
| `MANIFEST.in` | `[tool.setuptools]` 配置 |

核心理念是从命令式脚本转向声明式配置文件，使项目配置更清晰、更易维护、工具兼容性更好。

## 四、实用扩展配置

针对具体项目可补充以下配置段：

```toml
[project.optional-dependencies]  # 开发依赖
dev = [
  "pytest>=8.0",
  "black>=24.0",
  "ruff>=0.5.0",
  "mypy>=1.0",
]

[project.urls]  # 项目链接
Homepage = "https://github.com/yourname/gold-system"
Repository = "https://github.com/yourname/gold-system.git"

[tool.ruff]  # 代码检查工具配置（替代 flake8）
line-length = 120
target-version = "py311"

[tool.pytest.ini_options]  # pytest 配置
testpaths = ["tests"]
python_files = "test_*.py"
```

各段作用：

- `[project.optional-dependencies]`：声明可选依赖分组，`dev` 组用于安装开发工具
- `[project.urls]`：声明项目主页与仓库地址
- `[tool.ruff]`：`ruff` 的配置，替代 `flake8`
- `[tool.pytest.ini_options]`：`pytest` 的配置

`[tool.*]` 段是统一的工具配置入口，`black`、`isort`、`mypy` 等工具的配置均可写入对应子段。

## 五、常用安装与构建命令

```bash
# 安装项目（开发模式）
pip install -e .

# 构建分发包
python -m build

# 安装开发依赖
pip install -e ".[dev]"
```

## 总结

`pyproject.toml` 的核心作用：

- **项目元数据**：名称、版本、描述、作者、许可证等
- **依赖管理**：运行时依赖（`dependencies`）与开发依赖（`optional-dependencies`）
- **构建配置**：指定构建后端与构建工具
- **工具配置**：统一配置 `pytest`、`black`、`ruff`、`mypy` 等工具
- **打包发布**：配置如何将项目打包为 wheel 或源码分发包

## 延伸阅读

- [Python 环境与依赖管理的工具谱系](./2026-02-01-python-env-tooling.md)
- [Python 环境选型与工程实践](./2026-02-01-python-env-selection.md)
