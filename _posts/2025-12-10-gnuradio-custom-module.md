---
title: GNURadio框架自定义C++模块开发
tags: gnuradio
---


## 概述

在GNURadio中，**module（模块）** 和 **block（块）** 
是两个不同层次的概念。一个**module**是一个完整的、可安装的软件包，它包含了一组相关的**block**以及相关的支持文件（如接口、实现、GRC配置文件、文档、示例等）。而**block**是GNURadio中信号处理的基本单元，每个block实现特定的信号处理功能（如滤波、调制等）。通常，一个module中会包含多个block，这些block共同协作完成某一类信号处理任务。简单来说，block是功能的实现最小单元，而module是block的集合。在开发自定义功能时，我们会首先创建一个module，然后在其中添加一个或多个block。在GNU Radio Companion（GRC）中，我们使用的是一个个具体的block，而这些block来自不同的module。比如在官网教程[Your First Flowgraph](https://wiki.gnuradio.org/index.php?title=Your_First_Flowgraph)中Signal Source就是一个block，其属于Waveform Generators这个module。


## 1. 创建新模块：module

创建module和添加block均使用`gr_modtool`工具，具体可以使用如下命令创建新module，custom_module为自定义模块名：

```bash
gr_modtool newmod custom_module
```

该命令会生成一个标准化的module目录框架，整个目录对应一个完整的cmake工程：

```bash
apps/          # 应用程序目录
cmake/         # CMake配置文件
docs/          # 文档
examples/      # 示例代码
grc/           # GRC模块配置文件（.yml）
include/       # 公开类头文件
lib/           # C++实现类文件，包括impl.h和impl.cpp
python/        # Python绑定和包装
CMakeLists.txt # 主构建文件
MANIFEST.md    # 模块清单
```
### 核心目录详解

**`grc/` - GNU Radio Companion配置目录**：
* 此目录存放模块在图形化界面（GRC）的配置文件。其中包含YAML（.yml）格式的配置文件，如`custom_module_my_block.yml`。该文件是图形化模块的**声明性描述**。

**`include/<module_name>/` - 公开类的头文件目录**：
* 此目录存放模块对外的**C++接口声明**，即用户在其他C++项目中通过`#include`来使用的头文件。例如`my_block.h`。这里定义的类是一个“壳”，采用**Pimpl（Pointer to Implementation）** 设计模式，将具体实现完全隐藏。
* GNU Radio的绑定系统会对这些头文件进行哈希校验。若你修改了此目录下的头文件（如增删公共成员函数），**必须**执行`gr_modtool bind my_block`命令来更新绑定，否则后续构建会失败。

**`lib/` - 实现类的文件目录**：
*   `block_impl.h` / `block_impl.cc`：是**实现类（Impl class）** 的头文件和源文件。所有信号处理算法（尤其是关键的`work`函数）都在这里实现。这个类对用户是隐藏的，确保了ABI（应用程序二进制接口）的稳定性。

*   查看lib/CMakelists.txt可以发现，该目录下的所有实现文件最终会被编译成一个**动态链接库（如`libgnuradio-<module_name>.so`）**。同一个模块内的不同block实现之间可以相互访问（例如共用辅助函数），因为它们位于同一个子目录下，预处理时，include会优先搜索当前目录，链接时，每个block源文件block_impl.cc都会形成一个独立的编译单元，作为库的source。

**`python/` - Python绑定与封装目录**：
* 此目录负责将C++模块的功能暴露给Python和GRC，是**胶水层**。

*  `__init__.py`：定义Python包的导入逻辑。
*   `my_block.py`：通常包含一个Python包装类，它继承自`gr.sync_block`等基类，并负责实例化底层的C++对象。**GRC图形界面实际调用的是这个Python类**。
*   `bindings/` 子目录（由工具自动生成）：存放将C++类导出给Python的胶水代码（通常为`.cc`文件），由`pybind11`工具处理。开发者通常无需直接修改此目录下的文件。


## 2. 添加新块：block

进入模块目录后，添加新的处理块：

```bash
cd custom_module
gr_modtool add block
```

该命令会交互式询问，确定block type，language，arguement。

## 3. 修改C++实现文件

### 3.1 修改实现类文件

编辑`lib/block_impl.cc`和`lib/block_impl.h`，如果这一步修改了构造器的签名，需要对应的修改公开类的头文件，然后需要使用gr_modtool bind block重新绑定。如果使用clion等ide进行构建，可能需要手动清空cmake的缓存。

```cpp
// block_impl.cc中定义输入输出类型
// 注意：无论是数据量还是向量，都直接使用样本类型，长度在构造函数中设置
typedef gr_complex input_type;
typedef gr_complex output_type;
```

### 3.2 实现work函数

```cpp
int hop_interp_impl::work(int noutput_items,
                          gr_vector_const_void_star& input_items,
                          gr_vector_void_star& output_items)
{
    auto in = static_cast<const input_type*>(input_items[0]);
    auto out = static_cast<output_type*>(output_items[0]);
    
    int idx_item = 0;
    for (; idx_item < noutput_items; ++idx_item) {
        auto frame_in = const_cast<input_type*>(in + idx_item * d_vlen_in);
        auto frame_out = out + idx_item * d_vlen_in * d_interp_fac;
        
        // 调用信号处理函数
        rresamp_crcf_execute_block(resampler, frame_in, d_vlen_in, frame_out);
        rresamp_crcf_reset(resampler);
    }
    
    return idx_item;
}
```



## 4. 配置GRC YML文件

GRC配置文件定义模块在图形界面中的行为。

### 4.1 处理变长（vlen）参数

**方案1：使用Python辅助函数（推荐）**

在`python/custom_module/__init__.py`中添加辅助函数：

```python
def calc_vlen(param1, param2):
    """计算向量长度"""
    return param1 * param2
```

在YML配置文件中导入并使用：

```bash
id: freq_hopping_slot_frame
label: slot_frame
category: '[freq_hopping]'

templates:
  imports: |
    from gnuradio import custom_module
    from gnuradio.custom_module import calc_vlen
  make: custom_module.slot_frame(${hop_rate}, ${M_order}, ${info_seed})
```

**方案2：直接嵌入Python表达式（受限）**

*   仅支持单行表达式
*   不支持多行代码、赋值、import等复杂操作

**方案3：调用C++函数（复杂，不推荐）**

1.  在公开类中声明静态函数并实现
2.  修改Python绑定文件暴露函数
3.  需要处理哈希校验问题

## 5. 编写测试用例

### 5.1 创建测试文件

```bash
gr_modtool add -t qa block_name
```

### 5.2 测试框架限制

GNU Radio测试框架：

*   为每个测试文件生成独立可执行文件
*   仅链接到公开的block类（只有`make`方法）
*   无法直接访问`impl`类的内部函数

### 5.3 解决方案

如需测试`impl`类的静态函数：

*   将函数实现放在头文件中（内联）
*   测试文件直接包含`block_impl.h`

```cpp
// 在block_impl.h中定义内联函数
class block_impl
{
public:
    static inline int helper_function(int x) {
        return x * 2;
    }
    // ... 其他成员
};

// 在qa_block.cc中
#include "block_impl.h"

TEST_CASE("Test helper function") {
    REQUIRE(block_impl::helper_function(2) == 4);
}
```

## 6. 构建与安装

### 6.1 命令行构建流程

```bash
# 清理构建目录
rm -rf build

# 创建构建目录并配置
mkdir build && cd build
# 根据cmakelist生成对应构建系统的文件，如makefile
cmake ..  # 对应CLion的Reload按钮
# 编译
make      # 对应CLion的Build按钮
# 安装
sudo make install
sudo ldconfig  # 更新共享库缓存
```

### 6.2 自动化脚本

创建`build_install.sh`：

```bash
#!/bin/bash
set -e

echo "清理构建目录..."
rm -rf build

echo "配置项目..."
mkdir build
cd build
cmake ..

echo "编译模块..."
make -j$(nproc)

echo "安装模块..."
sudo make install
sudo ldconfig

echo "构建完成！"
```

### 6.3 CLion开发流程

在CLion中：

1.  **Reload Project**：执行CMake配置
2.  **Build**：调用Ninja/Make编译
3.  **手动安装**（在终端中）：

```bash
cd cmake-build-debug
sudo cmake --build . --target install
sudo ldconfig
```

CLion的CMake配置包含：

*   构建类型（Debug/Release）
*   生成器（Ninja/Make）
*   Python虚拟环境路径
*   源码和构建目录

### 6.4 Install命令详解

```bash
sudo cmake --build . --target install
```

| 组件       | 安装路径                                                      | 作用                 |
| :------- | :-------------------------------------------------------- | :----------------- |
| C++共享库   | `/usr/local/lib/x86_64-linux-gnu/`                        | 运行时库，包含核心功能        |
| C++头文件   | `/usr/local/include/gnuradio/module/`                     | 开发接口               |
| CMake配置  | `/usr/local/lib/cmake/gnuradio-module/`                   | 支持`find_package()` |
| Python扩展 | `/usr/local/lib/python3.x/site-packages/gnuradio/module/` | Python绑定           |
| Python模块 | 同上                                                        | Python包结构          |
| Python工具 | `/usr/local/bin/`                                         | 命令行工具              |
| GRC块定义   | `/usr/local/share/gnuradio/grc/blocks/`                   | 图形界面模块             |

### 6.5 卸载模块

```bash
# Ninja构建系统
sudo ninja uninstall

# Make构建系统  
sudo make uninstall

# 通用方法
sudo cmake --build . --target uninstall
```

**注意**：卸载仅从安装目录删除文件，不影响开发目录。

## 7. 删除块

从开发目录中删除块（谨慎操作）：

```bash
gr_modtool rm block
```

此操作会：

*   删除块相关的所有文件
*   更新CMake配置
*   **不可恢复**，请确保已备份


