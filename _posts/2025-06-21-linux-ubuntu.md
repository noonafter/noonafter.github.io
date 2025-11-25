---
title: Ubuntu双系统安装与使用
tags: linux, ubuntu
---

## Windows平台下Ubuntu双系统的安装

经过一段时间的尝试，我发现使用WSL2、MSYS2、Docker和虚拟机等环境搭建Linux开发环境各有其局限性。要获得完整的Linux开发体验，最直接有效的方法还是安装原生的Linux操作系统。因此，我最终选择了在Windows平台上安装Ubuntu双系统。

### 安装步骤参考

详细安装步骤可参考：[Ubuntu双系统安装指南](https://blog.csdn.net/2401_84064328/article/details/137232169)
注意安装完成之后，需要更新镜像源，否则apt install可能无法正常工作，具体方法参考[WSL安装与使用](https://blog.csdn.net/wangtcCSDN/article/details/137950545)

另外，建议先安装clash verge rev和chrome。可以利用github镜像下载lash verge rev的deb安装包，例如：
https://bgithub.xyz/clash-verge-rev/clash-verge-rev/releases/download/autobuild/Clash.Verge_2.4.4+autobuild.1125.d3dc40e_amd64.deb

随后，到[Chrome官网](https://www.google.com/intl/zh-CN/chrome/)下载chrome的deb安装包。

### 注意事项

*   **U盘启动问题**：如果U盘启动失败，可能是电脑与安装盘启动方式不兼容，建议更换制作工具重试
*   **安装选项**：进入Ubuntu安装界面后，建议选择"其他选项"进行手动安装，以便更好地控制分区布局

## Ubuntu软件的安装

Ubuntu提供多种软件安装方式，主要包括：

### 安装方式分类

#### 1. 命令行安装

*   系统级软件管理
    ```bash
    # 安装gnuradio
    sudo apt install gnuradio

    # 安装git
    sudo apt install git
    ```

#### 2. 安装包方式

*   **deb包安装**：下载后使用`apt install`或`dpkg -i`安装
    *   Chrome浏览器
    *   GitKraken

#### 3. 免安装方式

*   解压即可使用的可执行文件
    *   CLion
    *   PyCharm
    *   Audacity.AppImage

### 跨平台软件管理对比

| 类别        | Linux/Ubuntu 示例                     | Windows 示例                     | 核心特点                     |
| --------- | ----------------------------------- | ------------------------------ | ------------------------ |
| 系统级管理     | apt, dpkg, Snap                     | winget, choco, Microsoft Store | 管理操作系统层面的应用，处理系统依赖       |
| 语言级管理     | pip(Python), gem(Ruby), cargo(Rust) | pip, npm, vcpkg, NuGet         | 管理特定编程语言的库和工具，处理语言生态内的依赖 |
| 可执行文件/安装包 | .deb文件, AppImage, 二进制tar.gz         | .exe, .msi安装程序, 便携版应用          | 用户友好，图形化或解压即用，但更新需手动     |
| 源码编译      | ./configure && make && make install | Visual Studio, CMake, MinGW    | 最大控制权，可定制优化，但复杂耗时        |

### 技术要点说明

*   **语言级包管理器**（如pip、npm、vcpkg）本质上是跨平台的，它们工作在各自语言的运行时之上，与底层操作系统相对解耦
*   **Windows发展趋势**：传统上严重依赖可执行文件安装方式，但正在积极拥抱系统级包管理和现代化分发模式

### 开发者的软件管理策略

作为开发者，建议在不同平台上采用相似的策略：

*   **管理开发环境**：优先使用语言级包管理器
    *   C++：vcpkg
    *   Python：pip
    *   JavaScript：npm

*   **安装日常工具**：优先使用系统级包管理器
    *   Windows：winget/choco
    *   Ubuntu：apt

*   **使用特定专业软件**：可能需要下载官方安装程序或便携版

### APT安装流程详解

`apt install`的大致工作流程：

1.  **依赖分析**：从软件源下载元数据，与本地目录比较，分析依赖关系和冲突，提示用户确认
2.  **下载验证**：从镜像服务器下载deb包，验证数字签名和哈希值
3.  **安装执行**：按顺序调用dpkg -i
    *   解压.deb文件（本质是ar归档格式）
    *   运行pre-installation脚本（如果存在）
    *   将文件复制到正确位置
    *   运行post-installation脚本（如果存在）
    *   更新dpkg数据库（/var/lib/dpkg/status）
4.  **清理缓存**：可选清理操作

## 软件的卸载

Ubuntu在大多数情况下的软件卸载比Windows更简单彻底，前提是知道软件是通过什么方式安装的。

### Ubuntu vs Windows 卸载复杂度对比

| 方面    | Ubuntu/Linux                                                                                 | Windows                       |
| ----- | -------------------------------------------------------------------------------------------- | ----------------------------- |
| 注册表   | 无注册表概念，配置通常以纯文本文件形式存储在用户目录                                                                   | 有注册表，软件会在注册表中留下大量条目，容易产生残留    |
| 文件分布  | 文件按功能分布在标准目录中：<br>- /usr/bin（可执行文件）<br>- /usr/lib（库文件）<br>- /etc（配置文件）<br>- /usr/share（共享数据） | 文件通常集中在程序安装目录，但也会在系统目录、用户目录散布 |
| 依赖管理  | 包管理器自动跟踪依赖关系，卸载时自动清理不再需要的依赖                                                                  | 依赖管理混乱，DLL文件经常共享，卸载时不敢轻易删除    |
| 卸载彻底性 | 通过包管理器安装的软件可以完全清除，包括配置文件                                                                     | 即使用官方卸载程序，也经常留下残留文件、注册表项      |
| 跨用户清理 | 一个命令即可为所有用户卸载软件                                                                              | 可能需要为每个用户账户分别清理               |

## 设置交换空间

如果需要打开大量内存占用高的程序，Ubuntu可能会出现卡死或崩溃的情况。设置交换空间不仅能防止系统崩溃，还能优化内存使用效率。

### 创建交换文件（推荐方案）

#### 详细步骤

1.  **创建交换文件**（建议大小为物理内存的1-2倍，这里以8GB为例）
    ```bash
    sudo fallocate -l 8G /swapfile
    ```
    如果提示`fallocate failed: Operation not supported`，使用dd命令：
    ```bash
    sudo dd if=/dev/zero of=/swapfile bs=1M count=8192
    ```

2.  **设置正确的权限**
    ```bash
    sudo chmod 600 /swapfile
    ```

3.  **格式化为交换空间**
    ```bash
    sudo mkswap /swapfile
    ```

4.  **启用交换文件**
    ```bash
    sudo swapon /swapfile
    ```

5.  **验证是否启用成功**
    ```bash
    sudo swapon --show
    free -h
    ```
    应该能看到类似这样的输出：
        NAME      SIZE  USED PRIO
        /swapfile   8G   0B   -2

6.  **让交换文件开机自动启用**
    ```bash
    sudo nano /etc/fstab
    ```
    在文件末尾添加：
        /swapfile none swap sw 0 0

7.  **优化交换文件设置**（可选但推荐）
    *   调整swappiness（控制系统使用交换空间的倾向，默认60）：
        ```bash
        echo 'vm.swappiness=10' | sudo tee -a /etc/sysctl.conf
        ```
        这会让系统更倾向于使用物理内存，减少不必要的交换。
    *   调整缓存压力：
        ```bash
        echo 'vm.vfs_cache_pressure=50' | sudo tee -a /etc/sysctl.conf
        ```

#### 验证最终结果

完成所有步骤后，重启系统并验证：

```bash
sudo reboot
```

重启后检查：

```bash
sudo swapon --show
free -h
```

应该能看到交换文件正常工作。

### 为什么选择交换文件而不是交换分区？

*   **更灵活**：可以随时调整大小，无需重新分区
*   **更安全**：避免分区表操作的风险
*   **Ubuntu推荐**：新版本Ubuntu默认使用交换文件
*   **双系统友好**：不会影响Windows分区

## Ubuntu系统的卸载/删除
卸载ubuntu，保留Windows，具体步骤参考文章: https://blog.csdn.net/ZChen1996/article/details/115436436
