---
title: GNURadio框架自定义C++模块开发
tags: gnuradio
---


## 概述

在GNURadio中，**module（模块）** 和 **block（块）** 
是两个不同层次的概念。一个**module**是一个完整的、可安装的软件包，它包含了一组相关的**block**以及相关的支持文件（如接口、实现、GRC配置文件、文档、示例等）。而**block**是GNURadio中信号处理的基本单元，每个block实现特定的信号处理功能（如滤波、调制等）。通常，一个module中会包含多个block，这些block共同协作完成某一类信号处理任务。简单来说，block是实现功能的最小单元，而module是block的集合。

在开发自定义功能时，我们会首先创建一个module，然后在其中添加一个或多个block。在GNU Radio Companion（GRC）中，我们使用的是一个个具体的block，而这些block来自不同的module。比如在官网教程[Your First Flowgraph](https://wiki.gnuradio.org/index.php?title=Your_First_Flowgraph)中Signal Source就是一个block，其属于Waveform Generators这个module。


## 1. 创建新模块：module

创建module和添加block均使用`gr_modtool`工具，具体可以使用如下命令创建新module，custom_module为自定义模块名：

```bash
gr_modtool newmod custom_module
```

该命令会生成一个标准化的module目录框架，整个目录对应一个完整的CMake工程：

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
* 此目录存放模块对外的**C++接口声明**，即公开类的头文件。例如`my_block.h`。这里定义的类是一个“壳”，采用**Pimpl（Pointer to Implementation）** 设计方法，将具体实现完全隐藏。
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
在添加完新block后，如果直接在clion中进行编译，会报错，例如：
```bash
/home/lc/gr-freq_hopping/python/freq_hopping/bindings/frame_recover_python.cc:28:10: fatal error: frame_recover_pydoc.h: 没有那个文件或目录
28 | #include <frame_recover_pydoc.h>
```
需要重新清理然后reload cmake project，或者按照[第6节](#构建与安装)操作手动进行操作

## 3. 修改C++实现文件

### 3.1 修改构造器

编辑`lib/block_impl.cc`和`lib/block_impl.h`，如果这一步修改了构造器的签名，需要对应地修改公开类的头文件，然后需要使用gr_modtool bind block重新绑定。如果使用clion等IDE进行构建，可能需要手动清空cmake的缓存。

```cpp
// block_impl.cc中定义输入输出类型
// 注意：无论是数据量还是向量，都直接使用sample的类型，具体长度在构造函数中设置
using input_type = gr_complex;
using output_type = gr_complex;
// 公开类的工厂方法，如果修改了构造器的签名，make方法也需要相应地修改
hop_mod::sptr hop_mod::make(double bw_hop, double ch_sep, double freq_carrier, double fsa_hop, double hop_rate, int vlen)
{
    return gnuradio::make_block_sptr<hop_mod_impl>(bw_hop, ch_sep, freq_carrier, fsa_hop, hop_rate, vlen);
}


/*
 * The private constructor
 */
hop_mod_impl::hop_mod_impl(double bw_hop, double ch_sep, double freq_carrier, double fsa_hop, double hop_rate, int vlen)
// 调用父类sync_block的构造器，这一步确定输入输出向量的长度
    : gr::sync_block("hop_mod",
                     gr::io_signature::make(1, 1, vlen*sizeof(input_type)),
                     gr::io_signature::make(1, 1, vlen*sizeof(output_type))),
    // 初始化列表...
    d_bw_hop(bw_hop),
    d_ch_sep(ch_sep)
{
    // 构造器函数体...
    initialize_frequency_table();
    initialize_hop_sequence();
}
```

### 3.2 修改work函数
work函数是自定义模块中的核心，所有的信号处理逻辑都是在该函数中完成，包括调用tag和message相关的函数。work函数中一般使用一个for循环，来依次处理每个item（可能是sample，可能是vector）。

work函数由调度器在运行时自动调用，其详细机制与调度器密切相关，包括如何理解work函数的参数，history机制等等，具体可以参考另一篇文章:[work函数与调度器]()。
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

## 4. 修改yml配置文件

GRC目录下的YAML配置文件定义了模块在图形化界面中的行为、外观和接口。这是连接C++/Python代码与图形界面的关键文件。一个典型的YAML配置文件包含以下几个主要部分：

```bash
id: freq_hopping_hop_mod      # 块在GRC中的唯一标识符，通常为`<模块名>_<块名>`
label: Frequency Hopping Modulator  # 在GRC工具栏中显示的友好名称
category: '[freq_hopping]'    # 指定块在GRC的哪个分类下出现

templates:
  imports: from gnuradio import freq_hopping  # 导入Python模块的语句
  make: freq_hopping.hop_mod(${bw_hop}, ${ch_sep}, ${freq_carrier}, ${fsa_hop}, ${hop_rate}, ${vlen})  # 如何创建该块的Python对象

parameters:  # 块的可调参数列表
  - id: hop_rate
    label: Hopping Rate (hops/s)
    dtype: float
    default: 5
  - id: vlen
    label: Vector Length
    dtype: int
    default: 1

inputs:  # 输入端口定义
  - label: in
    domain: stream
    dtype: complex
    vlen: ${vlen}  # 引用参数vlen的值

outputs: # 输出端口定义
  - label: out
    domain: stream
    dtype: complex
    vlen: ${vlen}
```
yml文件和python文件结合非常紧密，可以利用python代码来使[block的输入/输出向量支持长度可变]()





## 5. 编写测试用例

### 5.1 创建测试框架

GNU Radio使用C++单元测试框架（如Boost.Test）。添加一个块的测试用例：

```bash
# 在模块根目录下执行
gr_modtool add -t qa my_block
```

此命令会在`python/`目录下生成`qa_my_block.py`（Python测试）或在`lib/`目录下生成`qa_my_block.cc`（C++测试，如果创建时选择语言为C++）。以下主要关注C++测试。

### 5.2 测试框架的限制与应对

生成的测试框架会为每个测试文件创建一个独立的测试可执行程序。它**仅链接到公开的block类库**，这意味着测试程序只能访问公开头文件（`block.h`）中声明的接口（主要是`make`工厂函数）。如果你想在测试中直接调用实现类（`block_impl`）中的**静态辅助函数**或测试内部状态，会遇到“未定义的引用”错误，因为实现类的符号没有被导出到库的公开接口中。

**解决方案**：\
将需要测试的内部函数（如静态辅助函数）在实现类的头文件（`block_impl.h`）中定义为**内联（inline）函数**。这样，测试文件通过`#include "block_impl.h"`就可以直接使用这些函数，而无需链接。

```cpp
// lib/my_block_impl.h
class my_block_impl
{
public:
    // ... 其他成员
    // 静态辅助函数，定义为inline以便测试
    static inline int calculate_something(int x, int y) {
        return x * y;
    }
};

// lib/qa_my_block.cc
#include "my_block_impl.h" // 包含实现类头文件

BOOST_AUTO_TEST_CASE(t_calculate_something) {
    // 可以直接测试内部静态函数
    BOOST_CHECK_EQUAL(my_block_impl::calculate_something(3, 4), 12);
}

// 也可以通过公开接口创建块进行功能测试
BOOST_AUTO_TEST_CASE(t_basic_functionality) {
    auto block = my_block::make(/* 参数 */);
    // 构造测试输入数据，调用block的general_work/forecast等（通常较复杂）
    // 更常见的是使用QA工具函数，如`gr::blocks::null_source`等构建小型流图进行测试。
}
```

### 5.3 运行测试

在构建目录（通常是`build/`）下，可以使用`ctest`命令运行所有测试，或直接运行生成的测试可执行文件。

```bash
cd build
# 运行所有测试
ctest
# 运行特定测试，并输出详细信息
ctest -R qa_my_block -V
# 或者直接运行测试程序
./lib/qa_my_block_test
```

## 6. 构建与安装

官方推进使用如下命令，进行构建和安装：

```bash
# 清理构建目录
rm -rf build
# 创建构建目录并进入
mkdir build && cd build
# 运行CMake配置
cmake ..
# 编译项目
make
# 安装（需要sudo权限）
sudo make install
# 更新动态链接库缓存
sudo ldconfig
```

在修改实现文件后，每次手动执行上述命令过于繁琐，可以创建自动化脚本`rebuild_install.sh`，来简化操作。关于对安装命令的解释可以参考另一篇文章[安装流程与install命令]()


## 7 卸载与删除

### 7.1 卸载已安装的模块

卸载是安装的逆过程，从系统目录中移除模块文件，但**不影响你的开发源代码**。

```bash
# 进入你的模块构建目录
cd build

# 通用方法（推荐）
sudo cmake --build . --target uninstall

# 或者根据你的构建系统
sudo make uninstall      # Makefile
sudo ninja uninstall    # Ninja
```

### 7.2 从开发目录中删除块

如果你想从**源代码树**中永久移除一个块（不可逆操作），使用`gr_modtool`：

```bash
# 在模块根目录下执行
gr_modtool rm my_block
```

此命令会：

*   删除`grc/`、`include/`、`lib/`、`python/`目录下与该块相关的文件。
*   更新`CMakeLists.txt`，将该块从构建列表中移除。
*   **注意：此操作会删除文件，请务必确认或已备份。**




