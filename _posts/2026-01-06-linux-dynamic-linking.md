---
layout: article
title: Linux 动态库链接机制：编译期与运行期的分离
date: 2026-01-06 10:00:00 +0800
tags:
  - linux
  - link
  - cmake
  - cpp/dev
---


## 问题现象

```bash
./fpga_sdk_demo
# error while loading shared libraries: libHyFFTd.so: cannot open shared object file
```

编译通过，运行时报错找不到 `.so`。这是 Linux 动态库链接中最常见的问题。

## 动态链接的两种模式

根据链接发生的时间，链接分为静态链接（构建期）和动态链接（加载期或运行期）。动态链接又分为两种模式（详见[链接与库](2025-02-02-c-cpp-link.md)）：

| 模式 | 发生时机 | 机制 |
|:---|:---|:---|
| **加载时链接** | 程序启动时（`main` 执行前） | 动态链接器读取可执行文件的依赖列表，加载所需的 `.so` 并解析符号地址 |
| **运行时链接** | 程序运行过程中 | 程序通过 `dlopen()` 等 API 主动加载库，获取符号地址并调用 |

本文的问题属于**加载时链接**——错误信息 `error while loading shared libraries` 明确指出了这一点。

### 编译期 vs 加载期：路径配置的分离

加载时链接涉及两个独立阶段：编译期声明依赖、加载期查找库文件。

**编译期**通过 `-L` 和 `-l` 参数声明依赖：

```cmake
target_link_directories(my_app PRIVATE /path/to/lib)
target_link_libraries(my_app my_library)
```

编译器在指定目录中查找 `libmy_library.so`，将库名和所需符号记录到可执行文件的 `.dynamic` 段中。此阶段**只验证符号存在性**，不检查库是否能被加载期找到。编译成功仅表示符号定义存在，不代表程序能运行。

**加载期**由动态链接器 `ld.so` 搜索 `.so` 文件，顺序如下：

1. **RPATH**（已弃用，优先级高于 `LD_LIBRARY_PATH`）
2. **LD_LIBRARY_PATH** 环境变量
3. **RUNPATH**（现代 Linux 默认写入）
4. `/etc/ld.so.cache`（由 `ldconfig` 生成）
5. `/lib`、`/usr/lib` 等系统默认路径

**问题根源**：编译期的 `-L` 路径不会传递到加载期，两个阶段的路径配置完全独立。

### 运行时链接示例

运行时链接由程序代码主动控制加载时机和路径，常用于插件机制：

```c
void* handle = dlopen("./plugin.so", RTLD_NOW);
void (*func)() = dlsym(handle, "plugin_init");
func();
dlclose(handle);
```

运行时链接不在本文讨论范围内。

## 解决方案

### 方案 1：LD_LIBRARY_PATH（临时方案）

```bash
export LD_LIBRARY_PATH=/path/to/lib:$LD_LIBRARY_PATH
./fpga_sdk_demo
```

CLion 远程调试中，在 Run Configuration → Environment variables 添加：

```
LD_LIBRARY_PATH=/path/to/third_party/fpga-sdk/lib
```

`LD_LIBRARY_PATH` 对所有层级的依赖均有效，是调试阶段最简单的方案。

**优点**：无需修改二进制，灵活
**缺点**：每次运行都需设置，无法打包分发

### 方案 2：RPATH / RUNPATH

在 CMakeLists.txt 中将路径嵌入 ELF 文件：

```cmake
set_target_properties(fpga_sdk_demo PROPERTIES
    BUILD_RPATH "${CMAKE_SOURCE_DIR}/third_party/fpga-sdk/lib"
    INSTALL_RPATH "${CMAKE_SOURCE_DIR}/third_party/fpga-sdk/lib"
)
```

验证是否写入：

```bash
readelf -d ./fpga_sdk_demo | grep RUNPATH
# 0x000000000000001d (RUNPATH)  Library runpath: [/path/to/lib]
```

**优点**：一次配置，永久生效
**缺点**：路径硬编码，目录变动后失效

### 方案 3：$ORIGIN（相对路径）

`$ORIGIN` 是动态链接器的特殊变量，表示可执行文件所在目录，使程序可移植：

```cmake
set_target_properties(fpga_sdk_demo PROPERTIES
    BUILD_RPATH "$ORIGIN"
    INSTALL_RPATH "$ORIGIN"
)
```

配合将 `.so` 复制到可执行文件同目录：

```cmake
file(GLOB LIBS "${CMAKE_SOURCE_DIR}/third_party/lib/*.so")
add_custom_command(TARGET fpga_sdk_demo POST_BUILD
    COMMAND ${CMAKE_COMMAND} -E copy_if_different ${LIBS} $<TARGET_FILE_DIR:fpga_sdk_demo>
)
```

**优点**：整个目录可打包分发
**缺点**：需要复制 `.so` 文件

## 间接依赖问题

假设依赖链为：

```
fpga_sdk_demo → libserver_core_interfaced.so → libHyFFTd.so
```

即使 `fpga_sdk_demo` 的 RPATH 正确，`libserver_core_interfaced.so` 自身没有 RPATH，`libHyFFTd.so` 仍然找不到。

验证：

```bash
ldd ./fpga_sdk_demo
# libserver_core_interfaced.so => /path/to/lib/libserver_core_interfaced.so  ✓
# libHyFFTd.so => not found                                                   ✗
```

### 解决方法 1：LD_LIBRARY_PATH

`LD_LIBRARY_PATH` 对所有层级的依赖有效，是最直接的解决方案。

### 解决方法 2：patchelf 修改第三方库的 RPATH

直接在 `add_custom_command` 中调用 `patchelf` 时，`$ORIGIN` 的 shell 转义问题复杂且易出错。推荐将 patchelf 调用提取到独立的 CMake 脚本中，由 CMake 的 `execute_process` 执行，完全绕过 shell 展开问题。

**CMakeLists.txt**：

```cmake
# 目标文件运行时在当前目录搜索依赖
set_target_properties(fpga_sdk_demo PROPERTIES BUILD_RPATH "$ORIGIN")

# 复制所有库文件到目标文件目录
file(GLOB FPGA_SDK_LIBS "${CMAKE_SOURCE_DIR}/third_party/fpga-sdk/lib/*.so")
add_custom_command(TARGET fpga_sdk_demo POST_BUILD
    COMMAND ${CMAKE_COMMAND} -E copy_if_different ${FPGA_SDK_LIBS} $<TARGET_FILE_DIR:fpga_sdk_demo>
)

# 为每个 .so 调用 patchelf 脚本，处理间接依赖（要求已安装 patchelf）
foreach(LIB ${FPGA_SDK_LIBS})
    get_filename_component(LIB_NAME ${LIB} NAME)
    add_custom_command(TARGET fpga_sdk_demo POST_BUILD
        COMMAND ${CMAKE_COMMAND}
                -DLIB=$<TARGET_FILE_DIR:fpga_sdk_demo>/${LIB_NAME}
                -P ${CMAKE_SOURCE_DIR}/cmake/patchelf_rpath.cmake
    )
endforeach()
```

**cmake/patchelf_rpath.cmake**：

```cmake
# cmake/patchelf_rpath.cmake
execute_process(COMMAND patchelf --set-rpath $ORIGIN ${LIB})
```

`execute_process` 直接将参数列表传给进程，`$ORIGIN` 不经过 shell，不存在转义问题。

安装 patchelf：

```bash
sudo apt install patchelf
```

构建后验证：

```bash
readelf -d ./libserver_core_interfaced.so | grep RUNPATH
# 0x000000000000001d (RUNPATH)  Library runpath: [$ORIGIN]

ldd ./fpga_sdk_demo
# 所有库均应显示找到的路径
```

## Linux vs Windows 动态库搜索机制

| 平台 | 默认搜索当前目录 | 嵌入路径机制 | 环境变量 |
|---|---|---|---|
| **Linux** | ❌ 不搜索 | RPATH / RUNPATH / `$ORIGIN` | `LD_LIBRARY_PATH` |
| **Windows** | ✅ 搜索 exe 同目录 | 无（依赖 PATH） | `PATH` |

Windows 下将 `.dll` 放在 `.exe` 同目录即可运行，Linux 必须显式配置搜索路径。

## 推荐实践

1. **开发调试**：使用 `LD_LIBRARY_PATH`，灵活快速
2. **本地部署**：使用 `$ORIGIN` + patchelf 处理间接依赖，可移植性强
3. **系统级安装**：使用绝对路径 RPATH + `ldconfig`，符合 FHS 标准

CLion 远程开发场景下，**优先使用 `LD_LIBRARY_PATH`**，避免路径同步问题。
