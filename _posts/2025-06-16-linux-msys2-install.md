---
title: MSYS2安装和使用
tags: linux program
---


## 📦 安装
MSYS2的安装非常简单！到[官网](https://www.msys2.org/)下载安装包，双击运行，一路Next就能搞定。安装完成后，勾选立即运行MSYS2的选项，就能直接进入UCRT64环境终端了。


## 📂 目录结构
安装完成后，MSYS2根目录（对应msys2的安装目录C:/msys2）下文件看似繁杂，但核心只需关注这些：

| 文件/目录 | 作用说明 |
|--------------------|--------------------------------------------------------------------------|
| `etc/` | 配置文件大本营（如`pacman.d/`镜像源配置） |
| `home/` | 用户目录，类似Linux的`/home` |
| `usr/` | 核心系统文件，包含`bin/`、`lib/`等关键目录 |
| `mingw64/` | 64位MinGW工具链环境（C运行库为msvcrt，兼容win7及更早版本） |
| `ucrt64/` | UCRT运行时环境（C运行库为ucrt，支持C11/C17最新标准，兼容Win10+） |
| `clang64/` | Clang编译器环境（LLVM工具链） |
| `msys2_shell.cmd` | 快速启动不同环境的脚本 |

> 🚨 **避坑提示**：
> - 不要手动修改`proc/`、`dev/`等Linux虚拟目录！
> - `autorebase.bat`用于修复DLL冲突，非必要勿动。


## 🚪 开始菜单
安装后开始菜单会生成5个快捷方式，对应不同开发环境：
1. **MSYS2 MSYS**：纯净的POSIX环境（核心工具链如`bash`, `pacman`）
2. **MSYS2 MINGW64**：经典MinGW-w64环境（GCC编译Win64程序）
3. **MSYS2 UCRT64**：UCRT运行时环境（Win10+推荐，兼容现代C库）
4. **MSYS2 CLANG64**：Clang/LLVM环境（C/C++跨平台开发）
5. **MSYS2 CLANGARM64**：ARM64架构的Clang环境（嵌入式/跨平台）

> 💡 **日常建议**：
> - 开发Windows应用优先选`MINGW64`或`UCRT64`
> - 需要Linux工具链（如`grep`, `sed`）时用`MSYS`



## 🌐 优化镜像源顺序
最新版MSYS2的已内置国内镜像源，由于pacman会优先使用mirrorlist顶部的镜像源，所以只需调整优先级即可！打开`/etc/pacman.d/`目录，按以下步骤操作：

1. 打开镜像文件mirrorlist.msys（MSYS核心环境），其他环境打开对应mirrorlist即可。
2. 找到国内镜像块，如以下源
```conf
## 清华大学源
Server = https://mirrors.tuna.tsinghua.edu.cn/msys2/msys/$arch/
## 中科大源
Server = https://mirrors.ustc.edu.cn/msys2/msys/$arch/
## 阿里云源
Server = https://mirrors.aliyun.com/msys2/msys/$arch/
```
3. 将国内源剪切到`## Primary`区域最顶部**
4. 保存后执行刷新：`pacman -Syy`


## 🔄 更新系统 & 安装软件
```bash
# 1. 更新软件包数据库（必做！）
pacman -Syu

# 2. 安装GCC编译器（UCRT版示例）
pacman -S mingw-w64-ucrt-x86_64-gcc

# 3. 安装常用工具
pacman -S git make cmake vim
```

> ✅ **验证安装**：
> ```bash
> gcc --version # 输出版本即成功
> ```


## 🏢 局域网高效开发
### 场景1：内网机器无法连外网
**步骤**：
1. 在可联网电脑安装MSYS2并下载所需包（缓存位于`/var/cache/pacman/pkg/`）
2. 将整个`pkg/`目录复制到内网机器的相同路径
3. 内网终端执行离线安装：
```bash
pacman -U /var/cache/pacman/pkg/包名.pkg.tar.zst
```

### 场景2：搭建本地镜像源
1. 用`rsync`同步官方源到本地服务器（需定期更新）
2. 修改内网机器的镜像配置文件：
```conf
Server = http://内网IP/msys2/msys/$arch/
```


## 💎 小贴士
- **环境切换**：在任意终端输入`msys2_shell.cmd -mingw64`秒切MINGW64环境
- **代理配置**：在`~/.bashrc`添加：
```bash
export http_proxy="http://代理IP:端口"
export https_proxy="http://代理IP:端口"
```
- **卸载**：直接运行`uninstall.exe`，干净不留痕

MSYS2就像Windows上的“瑞士军刀”，搞定环境配置后，你会爱上这种丝滑的开发体验！有问题欢迎留言讨论~ ✨