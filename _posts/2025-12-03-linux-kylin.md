---
title: 银河麒麟v10本地源搭建
tags: linux kylin
---


##  背景
为了在国产化桌面级平台（FT-D2000+银河麒麟v10）下进行c/c++程序的开发工作，需要先进行本地开发环境的配置。而公司内网无法连接互联网，只能采用本地源的方式进行操作，

## 开发环境验证
由于事先并不清楚目标主机的开发环境情况，这里可以先进行查看，确定系统包管理器属于dpkg还是rpm系列，开发环境是否完整，缺少哪些工具和库。

使用以下命令测试包管理器系统是debian系还是red hat系，一般来说，两种包管理器是互相不能同时使用的。后续所有安装管理工作都基于包管理器系统。
```shell
which dpkg
which rpm
```
这里经过验证，桌面版银河麒麟v10操作系统使用的是dpkg系列包管理器，也就是可以使用dpkg或apt进行后续的包管理，后面镜像系统中也应该能够看到大量的deb包。因此以下以本地apt源为例，关于本地yum源配置方法类似，具体可以参考[银河麒麟v10本地yum源、网络yum源和搭建基于http的内网yum服务器保姆级教程](https://blog.csdn.net/weixin_68809115/article/details/148254345)。

使用以下命令测试目标主机是否已经安装了全部或部分的开发环境，以下前三者（gcc, g++, make）属于开发基础工具包中的一部分，即build-essential的一部分。后两者作为中大型程序开发和调试也必不可少。
```
gcc --version
g++ --version
make --version
cmake --version
gdb --version
```
当然也可以写一个简单的helloworld程序，使用gcc和g++进行编译，来确定开发基础工具包是否已经安装。
```
gcc hello.c -o hello
g++ hello.cpp -o hello_cpp
```
关于gcc和g++等工具，以及编译过程的介绍，请参考另一篇文章。

## 获取系统镜像
首先确定目标主机上的系统版本，这里以银河麒麟v10为例，右键计算机查看属性，可以发现系统版本号为**2303**。随后可以在一台能够联网的windows主机上，进入[银河麒麟下载页面](https://www.kylinos.cn/support/trial/download/)，选择对应版本进行下载，这里下载的是**Kylin-Desktop-V10-SP1-General-Release-2303-ARM64**

下载之后，可以通过samba实现局域网下文件传输。值得注意的是，如果linux主机下只有samba而没有cifs-utils，则只能采用“linux共享，windows访问”的方法。具体步骤可以参考文章[在 Ubuntu 22.04 和 Windows 10 之间通过 Samba 共享文件夹](https://blog.51cto.com/zhangxueliang/14156959)，银河麒麟与ubuntu下samba的操作方法完全一样。

## 挂载ISO镜像

在终端中，创建一个用于挂载的目录（如果已存在可跳过）：
```bash
sudo mkdir -p /mnt/kylin-iso
```
将ISO文件挂载到该目录：
```bash
sudo mount -o loop /path/to/your/kylin.iso /mnt/kylin-iso
```
请将 /path/to/your/kylin.iso 替换为你ISO文件的实际路径。

在下载完成之后，可以使用如下命令进行卸载
```bash
sudo umount /mnt/kylin-iso
```

## 配置APT源，指向本地ISO
这是最关键的一步，告诉系统包管理器去本地ISO里找软件。首先，备份你原有的软件源列表，以防万一：
```bash
sudo cp /etc/apt/sources.list /etc/apt/sources.list.bak
```
清空或注释掉原有sources.list文件中的所有在线源（因为它们离线状态下无效并可能导致报错）。在sources.list文件末尾，添加以下行：

```bash
deb [trusted=yes] file:///mnt/kylin-iso/ v101 main restricted universe multiverse
```
注意：这里的 "v101" 是发行代号，需要根ISO中实际目录结构调整，比如dists文件夹下有一个bionic，其下面有main restricted universe multiverse，那么v101需要改为bionic
重要提示：ISO内的目录结构可能因版本而异。挂载后，请先检查 /mnt/kylin-iso/ 目录下是否存在 dists 和 pool 这两个关键文件夹。如果路径不同，例如实际路径是 /mnt/kylin-iso/repo/，则上述源地址应改为 file:///mnt/kylin-iso/repo/。

## 更新源并安装开发环境

让APT更新软件包列表，使其识别本地源：

```bash
sudo apt update
```
如果成功，你会看到它从你刚配置的 file:// 源读取了软件包列表。

如果镜像中的安装包完整的话，就可以像在线一样，一次性安装所有C++开发基础包了：

```bash
sudo apt install g++ cmake gdb build-essential
```

如果提示下面的信息，可能表面镜像中没有相关deb包，需要更换镜像。

```bash
FTD2000@FTD2000-pc:-$ sudo apt install cmake gdb g++
正在读取软件包列表...完成正在分析软件包的依赖关系树正在读取状态信息...完成
没有可用的软件包 gdb，但是它被其它的软件包引用了。这可能意味着这个缺失的软件包可能已被废弃，或者只能在其他发布源中找到
没有可用的软件包 cmake，但是它被其它的软件包引用了。这可能意味着这个缺失的软件包可能已被废弃，或者只能在其他发布源中找到
E:软件包 cmake 没有可安装候选 E:软件包 gdb 没有可安装候选 
```