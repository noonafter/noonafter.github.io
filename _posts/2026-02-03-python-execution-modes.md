---
layout: article
title: Python 解释器的三种运行模式
date: 2026-02-03 14:30:00 +0800
tags:
  - python
---


## 一、模块与文件的关系

Python 中的 `.py` 文件是模块的源代码载体，但模块是运行时加载后的对象。这两个概念有重叠但不等同。

模块的来源包括：

- **`.py` 文件**：最常见的源代码形式
- **内置模块**：例如 `sys`、`os`，编译在解释器中
- **C 扩展模块**：例如 `.pyd` 文件（Windows）或 `.so` 文件（Unix）
- **包目录**：包含 `__init__.py` 的目录
- **其他导入器**：例如从 zip 文件或自定义加载器导入

同一个 `.py` 文件可以以不同的模块身份运行，这取决于执行方式。

## 二、同一文件的三种运行情况

以 `apps/sync_history.py` 为例，说明同一文件在不同执行方式下的内部状态。

### 1、脚本模式：直接执行

执行命令：

```bash
python apps/sync_history.py
```

此时 Python 按文件路径查找并执行，文件的内部状态为：

```python
__name__ == "__main__"
__package__ is None
__spec__ is None
```

`sys.path[0]` 通常是文件所在目录：

```
/path/to/project/apps
```

Python 的执行逻辑是：找到文件，直接执行，不关心包结构。

### 2、模块模式：-m 执行

执行命令：

```bash
python -m apps.sync_history
```

此时 Python 按模块名查找并执行，内部状态为：

```python
__name__ == "__main__"
__package__ == "apps"
__spec__ is not None
```

`sys.path[0]` 通常是当前工作目录：

```
/path/to/project
```

Python 的执行逻辑是：按模块名 `apps.sync_history` 定位文件，在包上下文中执行。

`__package__` 的值取决于模块在包层次中的位置：
- 如果模块属于包 `apps`，则 `__package__ == "apps"`
- 如果模块是顶层模块（不在任何包内），则 `__package__ == ""`（空字符串，不是 `None`）

例如执行 `python -m sync_history`（模块在项目根目录），则 `__package__ == ""`。

### 3、导入模式：被其他代码导入

在其他代码中导入：

```python
import apps.sync_history
```

此时文件不作为主程序运行，内部状态为：

```python
__name__ == "apps.sync_history"
__package__ == "apps"
__spec__ is not None
```

模块中的以下代码不会执行：

```python
if __name__ == "__main__":
    run()
```

导入后的模块对象会缓存在 `sys.modules` 中，再次导入时直接返回缓存对象，不会重复执行模块代码。

`sys.path[0]` 的值取决于启动程序的方式，不由被导入模块决定。

## 三、三种模式的核心差异

| 项目 | 脚本模式 | -m 模式 | 导入模式 |
|------|---------|---------|---------|
| 查找方式 | 按文件路径 | 按模块名 | 按模块名 |
| `__name__` | `"__main__"` | `"__main__"` | `"apps.sync_history"` |
| `__package__` | `None` | `"apps"` | `"apps"` |
| `__spec__` | `None` | 存在 | 存在 |
| 相对导入 | 失败 | 可用 | 可用 |
| `__main__` 判断 | 成立 | 成立 | 不成立 |
| `sys.path[0]` | 脚本所在目录 | 当前工作目录 | 取决于启动者 |

`__spec__` 是 `ModuleSpec` 对象，包含模块的元信息：

```python
__spec__.name       # 模块全名
__spec__.loader     # 加载器对象
__spec__.origin     # 文件路径
__spec__.parent     # 父包名称
```

脚本模式下 `__spec__` 为 `None`，因为直接执行的文件不被视为模块系统的一部分。

## 四、相对导入的影响

相对导入是三种模式差异最明显的体现。

假设 `apps/sync_history.py` 中使用相对导入：

```python
from .collector import fetch_data
```

### 1、脚本模式下的失败

执行：

```bash
python apps/sync_history.py
```

会抛出错误：

```
ImportError: attempted relative import with no known parent package
```

原因是 `__package__` 为 `None`，Python 无法解析相对路径 `.collector`。

### 2、模块模式下的成功

执行：

```bash
python -m apps.sync_history
```

相对导入正常工作。Python 通过 `__package__ == "apps"` 将 `.collector` 解析为 `apps.collector`。

### 3、相对导入的解析规则

相对导入的语法：

- `.module`：当前包内的模块
- `..module`：上一级包内的模块
- `...module`：上两级包内的模块

解析依赖 `__package__` 和 `__name__`：

- 如果 `__package__` 不为 `None` 或空，Python 从 `__package__` 开始解析
- 否则，从 `__name__` 中移除最后一段作为包名

脚本模式下 `__package__` 为 `None`，解析失败。

## 五、重复加载问题

同一个文件可能在不同模块名下被加载多次，导致模块对象不同。

### 1、问题场景

先执行脚本：

```bash
python apps/sync_history.py
```

此时模块名为 `"__main__"`，加载到 `sys.modules["__main__"]`。

在脚本运行过程中，某处代码导入：

```python
import apps.sync_history
```

Python 发现 `sys.modules` 中没有 `"apps.sync_history"`，会再次加载文件，生成新的模块对象，存储在 `sys.modules["apps.sync_history"]`。

### 2、后果

同一个文件的两个模块对象不相等：

```python
import sys
sys.modules["__main__"] is not sys.modules["apps.sync_history"]  # True
```

如果文件中定义了类，会出现：

```python
class MyClass:
    pass

# 在 __main__ 中创建实例
obj = MyClass()

# 在其他模块中导入并判断
from apps.sync_history import MyClass as ImportedClass
isinstance(obj, ImportedClass)  # False
```

原因是两个 `MyClass` 来自不同的模块对象。

### 3、避免方法

使用 `-m` 模式执行包内文件：

```bash
python -m apps.sync_history
```

此时模块名统一为 `"apps.sync_history"`，不会重复加载。

## 六、实践建议

### 1、推荐执行方式

对于包内部的文件，推荐使用 `-m` 模式：

```bash
python -m apps.sync_history
```

或通过入口点工具（如 `uv`、`poetry`）执行：

```bash
uv run app-command
```

这些方式保证模块在正确的包上下文中运行。

### 2、兼容脚本模式的修复代码

如果必须支持脚本模式执行，可以在文件开头添加路径修复：

```python
from pathlib import Path
import sys

if __package__ in {None, ""}:
    # 将项目根目录添加到 sys.path
    project_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(project_root))
```

这段代码的逻辑：

- 检查 `__package__` 是否为 `None` 或空字符串
- 如果是，说明文件以脚本模式执行
- 将项目根目录插入 `sys.path[0]`，使导入路径正确

使用 `-m` 模式时，`__package__` 有值，此代码不执行，不影响正常行为。

### 3、避免直接执行包内文件

包内文件通常包含相对导入，直接执行会失败。应通过以下方式执行：

- 使用 `-m` 模式
- 在项目根目录下创建入口脚本（不在包内）
- 配置 `pyproject.toml` 的 `[project.scripts]` 入口点

### 4、文件与模块身份的总结

文件是代码的存储形式，模块是 Python 加载后的运行时身份。脚本模式按路径执行文件，模块模式按模块名定位并在包上下文中执行。

三种模式的区别不仅是 `sys.path[0]`，还包括：

- **模块名称**：`__name__` 的值
- **包上下文**：`__package__` 是否存在
- **相对导入**：能否解析
- **模块规格**：`__spec__` 对象
- **缓存行为**：`sys.modules` 的键名
- **主程序判断**：`if __name__ == "__main__"` 是否成立
- **重复加载风险**：同一文件是否可能生成多个模块对象

理解这些差异，有助于正确组织 Python 项目结构和执行方式。
