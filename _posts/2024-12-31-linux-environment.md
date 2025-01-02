---
title: Windows平台下类linux环境搭建
tags: linux
---

## 概述
在Windows平台上搭建类Linux环境，通常有以下几种方法：


1. WSL（Windows Subsystem for Linux）：WSL是微软推出的一种在 Windows操作系统上运行Linux环境的解决方案。
2. 虚拟机：适合需要完整Linux系统和资源隔离的场景。
3. Cygwin/MSYS2：适合开发时使用的类Linux环境，特别是对编译工具链的需求较大时。
4. Docker：适合容器化开发，能够快速部署和测试Linux应用。
5. 双系统：在同一台计算机上安装两个操作系统


<!--more-->
楼主将上述所有的方法都试了一遍，个人觉得，对于轻量化的开发需求，wsl的使用最方便，最简单。以下重点介绍wsl和虚拟机。


## WSL介绍
WSL基于微软自己的Hiper V虚拟机技术，并完全集成到 Windows 系统中，使用起来像原生工具一样，具体来说，有以下几个好处：

- 在Windows终端/PowerShell中调用 wsl 命令能够直接进入linux环境，快速且方便。

- 文件系统可互操作，在windows下可以直接操作linux下的各种文件，并且整个windows的文件系统也挂载在/mnt下，linux也可以方便操作windows下的各种文件

值得注意的是，wsl只能在windows10及之后的系统上使用。


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

不过值得注意的是，为了兼容Hiper V的虚拟机，vmware可能会在安装的时候提示打开WHP服务，这虽然能够使得Hiper V和vmware虚拟机能够共存，但也会降低部分性能，并且后续可能会遇到安装了vmware tools还是不能文件互通的bug，因此方法1和2最好只选一个,使用虚拟机的时候关闭微软的Hiper V服务以获得最好的性能。
具体原理参考[Hyper-V 和 VMWare 终于可以无缝共存、同时运行了](https://zhuanlan.zhihu.com/p/161578626)

另外，在联网情况下VMwares安装vmware tools只需要一句命令：

```bash
sudo apt install open-vm-tools

````

## 参考文章

详细WSL安装方法，参考[WSL2小白安装教程](https://blog.csdn.net/x777777x/article/details/141092913)


WSL官方帮助，参考[适用于 Linux 的 Windows 子系统文档](https://learn.microsoft.com/zh-cn/windows/wsl/)

虚拟机具体安装方法，参考[VMware Workstation Pro 个人免费版下载及安装指南](https://www.cnblogs.com/EthanS/p/18211302)