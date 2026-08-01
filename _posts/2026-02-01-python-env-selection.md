---
layout: article
title: Python 环境选型与工程实践
date: 2026-02-01 11:00:00 +0800
tags:
  - python
excerpt: Python 环境选型与工程实践：二进制依赖与 Conda 的边界、uv 主环境方案、依赖分组与交易环境隔离。
---

## 一、选型框架

### 1、三个关键问题

判断项目使用哪套工具，先回答三个问题：

1. **是否需要非 Python 依赖**：CUDA、系统库（TA-Lib）、特殊 PyTorch 版本、跨语言工具链。需要 → Conda / Mamba 或 Pixi
2. **新项目还是既有项目**：新项目 → uv；既有项目 → 保持现状，除非遇到性能或可复现痛点
3. **是否发布库到 PyPI**：发布 → Poetry 或 `uv publish`

### 2、决策表

| 项目类型 | 推荐方案 |
|:---------|:---------|
| 新应用 / 脚本项目（纯 PyPI 依赖） | uv |
| 库发布到 PyPI | `uv publish` 或 Poetry |
| 既有 Poetry 项目 | 保持 Poetry，有痛时迁移 uv |
| 数据科学 / ML（GPU、CUDA） | Conda/Mamba 建环境，剩余包用 uv/pip |
| conda 生态且需现代体验 | Pixi |
| 教学 / 简单脚本 / CI 最小化 | venv + pip |

## 二、二进制依赖与 Conda 的边界

### 1、二进制依赖不等于需要 Conda

研究阶段常用的 NumPy、pandas、SciPy、scikit-learn、statsmodels、PyArrow、DuckDB、Numba 内部都包含 C/C++、Fortran 或 Rust 代码，但它们在 Windows、Linux、macOS 上均有预编译 wheel。使用 pip / uv 安装时不会本地编译，安装体验与普通 Python 包一致。

因此，**"依赖包含二进制代码"本身不是使用 Conda 的充分理由**。

### 2、真正需要 Conda 的场景

- CUDA / GPU 计算
- 特殊版本的 PyTorch
- TA-Lib 等系统库安装困难
- 大型科学计算库缺少对应平台的 wheel
- 同时管理 Python、R、C++、Fortran 工具链
- 操作系统级库必须统一解析版本

需要注意：即使在这些场景，Conda 也不一定能直接解决——期货公司提供的 DLL 与交易接口通常不在 Conda 仓库中。

## 三、uv 的层次结构与操作原理

### 1、uv 在三个层次上的角色

uv 同时覆盖环境层与包源层，配置层复用 `pyproject.toml`，对应[《Python 环境与依赖管理的工具谱系》](./2026-02-01-python-env-tooling.md)提出的"环境、包、项目"三层次模型：

| 层次 | uv 的对应物 | 说明 |
|:-----|:------------|:-----|
| 环境层 | `.venv`（由 `uv venv` 创建） | 位于项目目录内，与 `pyproject.toml` 同级 |
| 包源层 | PyPI（由 `uv add` / `uv pip install` 访问） | 只从 PyPI 安装，不支持 conda-forge 二进制包 |
| 项目配置层 | `pyproject.toml` + `uv.lock` | `pyproject.toml` 手写声明，`uv.lock` 自动生成 |

环境层与包源层由 uv 自动管理：首次运行 `uv run` 或 `uv sync` 时自动创建 `.venv` 并安装依赖，无需先手动激活环境。这体现了两者合一的设计——uv 既是环境管理器，也是包管理器。

### 2、项目配置层的两种修改方式

`pyproject.toml` 是规格文件，**既可以手动编辑，也可以用 uv 命令修改**，两种方式等价。

**手动编辑**：直接修改 `pyproject.toml` 中的 `dependencies` 字段。uv 在下次 `uv sync` 或 `uv run` 时检测到规格变化，自动重新解析并更新 `uv.lock` 与环境：

```toml
[project]
dependencies = [
  "requests>=2.31",
  "akshare>=1.16",
]
```

**uv 命令**：`uv add` / `uv remove` 一步完成"修改 pyproject.toml + 更新 uv.lock + 同步环境"：

```bash
uv add requests akshare     # 等价于手动编辑后执行 uv sync
uv remove requests
```

选择依据：手动编辑适合批量调整依赖文本（如统一版本约束），`uv add` 适合单个依赖的增删，避免手写出错。

### 3、核心操作流程

```bash
uv init                              # 生成 pyproject.toml 骨架
uv add requests akshare              # 添加依赖（自动锁定并同步）
uv lock                              # 显式重新解析，生成/更新 uv.lock
uv sync                              # 从 uv.lock 精确安装到 .venv
uv run python -m gold_system.main    # 运行前自动检查并同步环境
```

`uv lock` 与 `uv sync` 的职责分离，对应[《Python 环境与依赖管理的工具谱系》](./2026-02-01-python-env-tooling.md)的"声明与解析"概念：`uv lock` 把 `pyproject.toml` 的宽泛约束解析为精确版本写入 `uv.lock`；`uv sync` 只读锁文件，把其中的版本安装到环境，不再参与解析。

## 四、黄金项目推荐方案

### 1、主环境：uv + pyproject.toml + uv.lock

对黄金数据采集与研究系统，主环境推荐：

```
gold/
├── pyproject.toml
├── uv.lock
├── .venv/
└── gold_system/
```

搭建步骤：

```bash
uv venv --python 3.12    # 创建环境并指定 Python 版本
uv sync                  # 读取 pyproject.toml 解析依赖并生成 uv.lock
```

日常使用：

```bash
uv run python -m gold_system.main   # 运行，自动保证环境最新
uv run pytest                        # 运行测试
uv add requests akshare              # 添加依赖并更新锁文件
```

### 2、uv 相比传统 venv + pip 的好处

**一个工具替代多个**：传统方案需要 pyenv 管理 Python 版本、venv 建环境、pip 装包、pip-tools 管理锁文件。uv 一个二进制覆盖全部，且无需预先安装 Python。

**速度快 10-100 倍**：依赖解析与安装由 Rust 并行完成，配合全局缓存，冷环境搭建从数分钟降至数秒，CI 中差距更大。

**可复现的锁文件**：`uv.lock` 是跨平台通用锁文件，覆盖所有目标平台与 Python 版本。传统 `pip freeze` 只固定直接依赖，`requirements.txt` 又按平台生成；uv 一个文件即可保证团队成员与 CI 安装完全一致的版本。

**自动同步**：`uv run` 每次执行前自动检查并更新环境，无需手动 `pip install -e .` 或先激活环境；`uv sync` 做精确同步，移除多余包。

**内置 Python 版本管理**：`uv python install 3.12` 直接下载对应版本，无需 pyenv。

**依赖分组**：`uv add --group research numpy` 声明分组依赖，安装时按需选择。

### 3、传统替代方案

暂不引入 uv 时，venv + pip 完全可行：

```bash
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e .
```

uv 与此流程兼容：`uv pip install -e .` 可直接替换 `pip install`，迁移成本低。

## 五、PyCharm 中的环境管理

### 1、选择与添加解释器

PyCharm 通过 Settings → Project → Python Interpreter 管理解释器。点击右上角 **Add Interpreter → Add Local Interpreter**，在环境类型列表中选择对应工具，底层执行的即是对应的命令行：

| PyCharm 环境类型 | 对应的命令 |
|:-----------------|:-----------|
| Virtualenv Environment（新建） | `python -m venv <路径>` |
| Virtualenv Environment（已有） | 直接选择已有 venv 路径 |
| Conda Environment（新建） | `conda create -n <环境名> python=<版本>` |
| Conda Environment（已有） | 绑定已有环境，等价于 `conda activate <环境名>` |
| UV Environment（新建 / 已有） | `uv venv` + `uv sync` |
| System Interpreter | 直接使用系统 Python |

PyCharm 2024.3.2 起将 **uv** 列为环境类型，自动检测 PATH 中的 uv 可执行文件；2025.3 起支持 `uv run` 运行配置。选择 uv 已有环境前，需先在终端执行 `uv sync` 生成 `.venv`，PyCharm 才能绑定该目录。

### 2、安装包按钮与命令的对应

Interpreter 页面或 Python Packages 工具窗口中的 **"+" 按钮**，按所选解释器关联的包管理器执行安装：

- pip 环境 → `pip install <包>`
- conda 环境 → `conda install <包>`
- uv 环境 → 通过 uv 管理

**使用 uv 环境的注意点**：`uv sync` 是精确同步，会移除锁文件中不存在的包。因此 uv 项目应通过 `pyproject.toml` 或 `uv add` 声明依赖后再同步，不要在 PyCharm 中临时用 pip 手动安装包——下一次 `uv sync` 会将其清除。PyCharm 会检测 `pyproject.toml` 与环境的差异，对未同步的依赖给出快速修复提示。

## 六、依赖分组

将依赖按用途分组，采集服务不必安装完整研究环境，交易网关不必加载全部回测组件：

| 分组 | 依赖 |
|:-----|:-----|
| 基础依赖 | requests、akshare |
| 研究依赖 | numpy、pandas、scipy、statsmodels、scikit-learn |
| 开发依赖 | pytest、black、ruff、mypy |
| 交易依赖 | CTP 或其他交易接口 |

uv 分组写法：

```bash
uv add requests akshare
uv add --group research numpy pandas scipy
uv add --group dev pytest ruff mypy
uv sync --group dev     # 只同步到开发分组
```

## 七、特殊交易环境的隔离

CTP 官方动态库、期货公司专用交易 SDK、特定版本 Windows DLL、对 Python ABI 与 Visual C++ Runtime 有要求的扩展，通常不在 Conda 或 PyPI 仓库中。将整个项目绑定到这种环境，会拖累研究、采集与回测模块。

合理的做法是把交易接口隔离为独立环境：

```
gold-core    核心系统    Python + venv/uv（研究、采集、回测）
gold-ctp     交易网关    CTP SDK + 厂商 DLL + 特定 Python 版本
```

两个环境通过稳定接口、本地 API、消息或数据库事件交互，不互相导入内部代码。即使 CTP 适配器只能在 Python 3.10 或某个特殊环境运行，其他模块也不受限制。

## 八、混用 Conda 与 pip 的注意事项

### 1、双解析器问题

Conda 与 pip 是两个互不感知的解析器。Conda 先解析并安装 conda 包，再将 pip 作为子进程处理剩余包；两个解析器不交换信息。Conda 4.6+ 提供的 `pip_interop_enabled` 标志默认关闭。

在同一环境随意交替执行 `conda install` 与 `pip install`，两个包管理器都不知道对方修改了哪些底层依赖，容易产生版本漂移与难以复现的问题。

### 2、混用原则

确需混用时，遵循以下边界：

- 编译类依赖（CUDA 相关、系统库）用 conda 安装
- 纯 Python 依赖用 pip 安装
- 先 conda 后 pip，避免交替执行
- 用 conda-lock 或导出 `environment.yml` 保证可复现

若项目依赖全部来自 PyPI，直接使用 uv 即可，无需引入 Conda。

## 总结

选型的核心判断是"是否需要非 Python 依赖"。黄金项目当前依赖（requests、akshare 及未来研究库）均可由预编译 wheel 覆盖，主环境应使用 `uv + pyproject.toml + uv.lock`；CTP、CUDA 等特殊需求出现时，为交易网关单独建立 Conda 或厂商环境，通过隔离保持主环境干净可复现。

## 延伸阅读

- [pyproject.toml：现代 Python 项目的声明式配置标准](./2026-02-01-pyproject-toml.md)
- [Python 环境与依赖管理的工具谱系](./2026-02-01-python-env-tooling.md)
