---
title: Windows平台下类linux环境搭建
tags: linux
---

## 概述
在Windows平台上搭建类Linux环境，通常有以下几种方法，每种方法都有其独特的设计思想和适用场景：

- WSL2 - 微软官方的“轻量级虚拟化”方案

- 虚拟机 - 传统的“完整系统模拟”方案

- Cygwin/MSYS2 - “API转换层”方案

- Docker - “应用容器化”方案

- 双系统 - “硬件直通”方案


<!--more-->
楼主将上述所有的方法都试了一遍，个人觉得，对于轻量化的开发需求，wsl的使用最方便，最简单，而为了获得完整的linux体验，推荐使用安装双系统，下面详细分析每种工具的优缺点。


## WSL介绍
WSL基于微软自己的Hiper V虚拟机技术，其使用的是微软构建的官方Linux内核，支持完整的linux系统调用，启动迅速，并且实现了Windows与Linux文件系统的高效互通，并共享网络栈。

优点：

- 性能接近原生：文件系统、网络性能相比WSL1大幅提升

- 深度集成：可与Windows终端、VS Code、Clion等工具无缝协作

- 资源高效：动态内存管理，闲置时自动释放资源


缺点：

- 虚拟化开销：仍有轻量级虚拟化层，性能略低于裸机

- 硬件访问限制：难以直接访问USB设备、GPU（虽有改进但仍有限制）



## WSL安装
1 打开windows功能，勾选以下两个选项：**适用于Linux的Windows子系统**，**虚拟机平台**

2 重启后，命令行输入wsl --install查看帮助，选择适合发行版，比如：

```cmd
wsl --install -d Ubuntu

```
如果报错：WslRegisterDistribution failed with error: 0x800701bc,则需要进行手动安装，参考[Win11安装Ubuntu子系统报错](https://blog.csdn.net/qq_51908382/article/details/140606794)

3 安装完之后，命令行中输入wsl进入，使用下列命令更换镜像源
```bash
 vim /etc/apt/sources.list.d/ubuntu.sources 
 ```
国内源的地址可以参考[WSL最新安装教程](https://blog.csdn.net/wangtcCSDN/article/details/137950545)


4 更换之后记得对源进行更新:
```bash
sudo apt update
```

否则会报错Unable to Locate Package



## 虚拟机
当然现在VMware Workstation Pro 对个人用户已经完全免费，也可以尝试使用虚拟机来获得完整且独立的linux环境。

核心思想：通过硬件虚拟化技术，在宿主机上模拟完整的计算机硬件，运行独立的客户操作系统。

优点：

- 完全隔离：独立的系统环境，互不干扰

- 功能完整：支持所有Linux特性和应用

- 快照管理：可以保存和恢复系统状态

- 跨平台兼容：不依赖特定Windows版本

缺点：

- 资源消耗大：需要分配固定内存和存储空间

- 性能开销：存在虚拟化层性能损失

- 启动较慢：需要启动完整操作系统

- 文件共享：需要额外配置共享文件夹

不过值得注意的是，为了兼容Hiper V的虚拟机，vmware可能会在安装的时候提示打开WHP服务，这虽然能够使得Hiper V和vmware虚拟机能够共存，但也会降低部分性能，并且后续可能会遇到安装了vmware tools还是不能文件互通的bug，因此方法1和2最好只选一个,使用虚拟机的时候关闭微软的Hiper V服务以获得最好的性能。
具体原理参考[Hyper-V 和 VMWare 终于可以无缝共存、同时运行了](https://zhuanlan.zhihu.com/p/161578626)

另外，在联网情况下VMwares安装vmware tools只需要一句命令：

```bash
sudo apt install open-vm-tools
````


## Cygwin / MSYS2
核心思想：

Cygwin：提供POSIX API的兼容层，让Linux程序在Windows上重新编译运行

MSYS2：基于MinGW-w64，将GCC工具链移植到Windows，编译生成Windows原生应用

优点：

- 原生性能：编译出的程序是Windows原生应用

- 开发友好：提供完整的Linux开发工具链

- 轻量级：不需要虚拟化或容器技术

缺点：

- 移植限制：涉及Linux内核特性或设备驱动的程序无法移植

- 环境差异：与真实Linux环境仍有区别

- 依赖管理：需要处理Windows下的依赖关系

## Docker Desktop
核心思想：利用WSL2作为后端，在Windows上提供Linux容器运行环境。

优点：

- 环境一致：确保开发、测试、生产环境一致性

- 快速部署：镜像秒级启动，资源利用率高

- 隔离性好：应用级别隔离，互不影响

- 生态丰富：庞大的镜像仓库支持

缺点：

- 学习曲线：需要理解Docker概念和命令

- 资源需求：Docker Desktop本身有一定资源消耗

- 网络配置：容器网络配置相对复杂

##  双系统
核心思想：在同一台计算机的不同磁盘分区安装两个独立的操作系统，通过引导程序选择启动。

优点：

- 性能最佳：直接使用硬件资源，无性能损失

- 功能完整：获得100%的Linux系统功能

- 完全独立：两个系统完全隔离，互不影响

- 硬件直通：直接访问GPU、USB等硬件设备

缺点：

- 切换不便：需要重启才能切换系统

- 磁盘分区：需要合理规划磁盘空间

- 数据隔离：文件系统不互通，数据共享困难（目前ubuntu已经可以查看windows的文件了）

方案选择建议
| 使用场景 | 推荐方案 | 理由|
|---------------|---------------------|---------------------|
|日常开发学习|WSL2| 平衡了便利性和功能性，最适合大多数开发者|
| 专业Linux开发| 双系统|	获得完整的Linux体验，性能最佳|
|测试多环境	|虚拟机	|可以同时运行多个不同版本的Linux|
|应用部署测试	|Docker|	容器化部署，环境一致性最好|
|编译Linux程序	|MSYS2	|在Windows上获得Linux开发工具链|

## 重点推荐
基于个人体验，对于不同需求的用户，我重点推荐：

🚀 轻度到中度开发用户：选择 WSL2
WSL2提供了最佳的开发体验，特别是：

真实的Linux内核，支持完整的系统调用

与VS Code、Clion等IDE深度集成，远程开发体验优秀

文件系统无缝互通，性能优秀

微软官方持续优化，生态完善

💻 专业Linux开发用户：选择 双系统
如果你需要：

直接的硬件访问（GPU计算、设备驱动开发）

最佳的硬件性能

涉及内核开发或系统级编程

最纯粹的Linux体验

双系统仍然是最佳选择，虽然切换需要重启，但提供了最完整的Linux体验。

## 参考文章

详细WSL安装方法，参考[WSL2小白安装教程](https://blog.csdn.net/x777777x/article/details/141092913)


WSL官方帮助，参考[适用于 Linux 的 Windows 子系统文档](https://learn.microsoft.com/zh-cn/windows/wsl/)

虚拟机具体安装方法，参考[VMware Workstation Pro 个人免费版下载及安装指南](https://www.cnblogs.com/EthanS/p/18211302)