---
layout: article
title: 离线 ARM Linux 主机上的 Qt 5.14.2 环境搭建
date: 2026-01-04 10:00:00 +0800
tags:
  - qt
  - kylin
  - cpp/dev
---

目标：在无法访问互联网的 ARM64 麒麟主机上搭建 Qt 5.14.2 的源码编译环境，包括依赖获取、编译和验证。

本文只讨论离线依赖和 Qt 本身的安装。SSH、CLion Remote Host、VcXsrv 和 DISPLAY 的配置见[CLion Remote Host 远程开发环境搭建](./2026-01-05-clion-remote-host-setup.md)。

## 1. 背景和版本选择

如果项目对 Qt 版本没有要求，优先使用系统包管理器安装 Qt，维护成本最低。只有在项目需要固定版本、系统仓库版本过旧，或者需要完整的 Qt 模块时，才考虑源码编译。

选择系统版本时，先检查目标机已安装的 Qt：

```bash
qmake --version
```

银河麒麟 V10 2503 系统默认版本为 Qt 5.12.12。确认使用系统版本时，通过包管理器安装 Qt 开发组件：

```bash
sudo apt install qt5-default qtbase5-dev qtdeclarative5-dev qtquickcontrols2-5-dev qml-module-qtquick2 qml-module-qtquick-controls2 build-essential
```

**本文选择源码编译 Qt 5.14.2**，依据来自项目要求和原有环境记录：

- 需要与现有开发环境保持 Qt 版本一致；
- Qt 5.14.2 是 Qt 5.14 系列的最后一个补丁版本，源码构建流程成熟；
- 原有 ARM64 编译记录显示，Qt 5.15.x 在部分平台上遇到 V4/Yarr 相关链接问题，5.14.2 的编译稳定性更好；
- ARM64 平台没有可直接使用的 Qt 5.14.2 离线安装包，源码编译更容易固定版本、模块和安装路径。

**Qt 5.15 的 V4/Yarr 链接问题**：Qt 5.15 系列调整了底层 JavaScript 引擎（V4）和正则表达式引擎（Yarr）的符号可见性规则，在部分 ARM64 平台上出现链接错误，典型报错：

```
YarrPattern.cpp:(.text+0x9e0): undefined reference to `JSC::Yarr::newlineCreate()'
YarrPattern.cpp:(.text+0xa74): undefined reference to `JSC::Yarr::digitsCreate()'
YarrPattern.cpp:(.text+0xaf4): undefined reference to `JSC::Yarr::spacesCreate()'
```

该问题存在于 Qt 5.15.0 - 5.15.8。Qt 5.14.2 的实现方式不同，不受此影响。

这不是对所有项目的版本推荐。若项目允许使用系统版本，直接安装系统 Qt 仍然更简单。

## 2. 依赖获取的几种方式

内网主机不一定只能使用离线包，常见方案有三种。

### 2.1 Windows 网络共享

通过 Windows Internet 连接共享（ICS）让内网主机临时访问互联网，然后直接使用 apt 安装依赖。这种方式配置简单，适合网络策略允许临时联网的场景。ICS 的具体配置见[CLion Remote Host 远程开发环境搭建](./2026-01-05-clion-remote-host-setup.md)的第 0 步。

### 2.2 SSH 转发或代理

如果内网主机可以连接外网机，但不能直接访问软件源，可以通过 SSH 隧道、HTTP 代理或 SOCKS 代理转发软件源访问。它不需要复制大量 deb 包，但需要额外配置代理，并且依赖网络策略允许建立转发。

### 2.3 下载依赖并制作本地 apt 源

如果内网主机完全隔离，只能在外网机下载依赖，制作本地包源后传回内网机。本文采用这种方式。

制作的是 Qt 编译依赖的闭包，不是 Kylin 的完整镜像，下载量和传输量较小。

## 3. `install-deps.sh` 的原理

脚本有三个模式：

```bash
sudo ./install-deps.sh s    # 在目标内网机生成快照
sudo ./install-deps.sh d    # 在外网机求解并下载依赖
sudo ./install-deps.sh i    # 在内网机从本地源安装
```

脚本不把递归依赖列表直接交给 `apt install`。这是因为依赖关系中可能存在替代分支，例如 `make | make-guile`、`pkg-config | pkgconf`，把两侧都当成显式安装目标会引入互相冲突的软件包。

下载模式的实际流程是：

1. 快照模式导出目标机的 `/var/lib/dpkg/status` 和软件源清单；
2. 外网机使用目标机的状态快照，让 apt 模拟安装脚本中的目标包；
3. 从 apt 的模拟结果中提取求解器最终选择的精确包版本；
4. 下载这些精确版本，整理成一个本地 apt 源；
5. 内网机注册临时 `file:` 源，再由 apt 完成最后的依赖选择和安装。

因此，目标机已经安装的运行库版本会参与求解，能够避免开发包和目标机现有运行库之间的精确版本冲突。

脚本开头的 `PKGS` 数组是本文 Qt 编译依赖的目标包清单。如果项目需要额外的 Qt 模块，可以先修改这份清单，再重新执行下载流程。

部分 apt 版本对 `file:` 平板源的压缩索引支持不完整，脚本会同时生成未压缩的 `Packages` 和压缩的 `Packages.gz` 作为兼容处理。安装模式使用 `Packages.gz` 判断本地源目录是否完整，两个文件都不应删除。

## 4. 外网机和内网机的兼容边界

本文记录的验证场景是：

- 内网机：银河麒麟 V10 2503，ARM64；
- 外网机：具备 apt/dpkg 的 Debian 系列环境，能够访问目标机的软件源；
- 两台机器使用相同的 CPU 架构。

可以在两台机器上分别检查：

```bash
uname -m
dpkg --print-architecture
cat /etc/os-release
```

脚本通过目标机的状态快照和软件源清单处理发行版小版本差异。外网机和内网机不必安装完全相同的 Kylin 小版本：只要 apt/dpkg 体系兼容、目标软件源可访问且架构一致，包版本就由目标机的实际状态决定。Kylin 2303 外网机配合 Kylin 2503 内网机是本文验证过的组合。

因此，ARM64 Ubuntu 这类同架构的 Debian 系系统，理论上也可以作为下载机：它只负责使用 apt/dpkg 读取目标状态、解析目标源并下载 ARM64 包，并不会把这些包安装到自身系统中。但这依赖 Ubuntu 的 apt 能够识别目标 Kylin 软件源，并且已经配置相应的仓库签名密钥；这类组合未在本文中单独验证。

当前脚本没有设置 `APT::Architecture`，也没有配置 foreign architecture。外网机的本机架构会影响 apt 读取的软件包索引，因此不能直接把“x86 外网机下载 ARM64 包”作为当前脚本支持的用法。跨架构下载需要额外的 apt 配置，或使用 ARM64 容器、chroot、虚拟机等匹配环境，本文不展开。

另外，目标机快照中的软件源必须能被外网机访问。与 Qt 无关的第三方源如果在外网机不可达，应在生成快照前临时禁用，或确保外网机可以访问。

## 5. 使用离线依赖脚本

### 5.1 在内网机生成快照

把 `install-deps.sh` 复制到内网机后执行：

```bash
sudo ./install-deps.sh s
```

脚本会在脚本所在目录生成两个固定名称的文件：

```text
target-dpkg-status
target-sources.list
```

这两个文件分别记录目标机当前已安装的软件包状态和软件源配置。

### 5.2 在外网机下载依赖

将以下三个文件复制到外网机的同一目录：

```text
install-deps.sh
target-dpkg-status
target-sources.list
```

确认目标软件源可以访问后执行：

```bash
sudo ./install-deps.sh d
```

脚本会刷新索引、求解完整依赖闭包、下载精确版本，并在当前目录生成类似下面的目录：

```text
debs-20260909-xxxx/
```

目录中包含 deb 包、本地 apt 索引、目标包清单和状态快照校验信息。下载结束后，脚本会询问是否将其打包为 `deps-offline-*.tar.gz`。

### 5.3 在内网机安装

将打包文件传回内网机并解压：

```bash
tar -xzf deps-offline-*.tar.gz
cd debs-*
sudo ./install-deps.sh i
```

安装模式只使用当前离线包目录作为源，不连接在线软件源。不要使用下面的方式直接安装全部 deb：

```bash
dpkg -i *.deb
```

直接调用 `dpkg` 会绕过 apt 的依赖选择，容易把替代依赖分支或不匹配版本一起装进去。

下载包中保存了目标机状态快照的校验值。如果内网机在快照之后又安装、删除或升级了软件包，安装模式会拒绝继续；此时应重新生成快照并重新下载。

## 6. 准备 Qt 5.14.2 源码

源码和构建目录都使用纯英文路径。此前出现的：

```text
Could not find qmake spec ''.
Error processing project file: .../qt.pro
```

最终确认主要是源码或构建路径包含中文目录名导致的。不要直接在 `~/桌面/...` 下配置 Qt。

例如，将源码压缩包复制到英文目录后解压：

```bash
mkdir -p ~/qt-work
cp ~/桌面/qt-everywhere-src-5.14.2.tar.xz ~/qt-work/
cd ~/qt-work
tar -xJf qt-everywhere-src-5.14.2.tar.xz
mkdir -p build
```

最终目录结构类似：

```text
~/qt-work/qt-everywhere-src-5.14.2
~/qt-work/build
```

## 7. ARM64 上的三阶段编译

在 ARM64 主机上，Qt 源码编译可以分为三个阶段：

```text
configure  ->  make  ->  make install
```

### 7.1 配置

进入独立构建目录：

```bash
cd ~/qt-work/build

../qt-everywhere-src-5.14.2/configure \
  -platform linux-g++ \
  -prefix /opt/Qt5.14.2 \
  -opensource -confirm-license \
  -nomake examples \
  -nomake tests
```

`configure` 会检测编译器、系统库、图形库和目标平台，并生成 Makefile。结束时检查 Summary，确认需要的 Qt Widgets、Qt Quick 等模块没有因为缺少依赖而被跳过。

**OpenGL 参数**：`configure` 不指定 `-opengl` 参数时，会自动检测并使用系统的桌面版 OpenGL。ARM PC 运行 Linux 桌面系统时具备完整的桌面级显卡驱动，应使用标准桌面 OpenGL，而不是面向嵌入式设备的 OpenGL ES。

### 7.2 编译

```bash
make -j"$(nproc)"
```

ARM64 主机上的完整编译通常需要数小时。中途失败时，先保留输出定位具体模块；如果只是中断，通常可以直接重新执行 `make` 继续编译。并行编译偶尔因依赖竞争出错，中断后重新执行 `make -j"$(nproc)"` 通常可恢复。

若需重新编译，注意两个命令的区别：

| 命令 | 删除内容 | 保留内容 | 适用场景 |
|---|---|---|---|
| `make clean` | `.o` 文件、可执行文件 | Makefile、configure 结果 | 增量重编译 |
| `make distclean` | 所有产物、Makefile、配置缓存 | 原始源码 | 完全重新配置 |

增量重编译使用 `make clean`；执行 `make distclean` 后必须重新执行 `configure`。

### 7.3 安装

```bash
sudo make install
```

安装结果位于 `/opt/Qt5.14.2`。安装目录不需要在 configure 前手动创建。

## 8. 验证和 CMake 配置

检查 qmake：

```bash
/opt/Qt5.14.2/bin/qmake --version
```

检查 Qt Quick 等模块是否存在：

```bash
find /opt/Qt5.14.2 -name 'Qt5Quick*'
```

CMake 项目中可以指定：

```text
-DCMAKE_PREFIX_PATH=/opt/Qt5.14.2
```

这样 CMake 会优先从该目录查找 Qt 的配置文件和库。

## 9. 常见问题

### 9.1 依赖版本不匹配

首先检查外网机是否使用了目标机的 `target-dpkg-status` 和 `target-sources.list`。只使用外网机当前的软件源，或者混用 2303/2503 源，都会改变 apt 的候选版本。

### 9.2 Qt configure 找不到 qmake spec

优先检查源码路径和构建路径是否包含中文目录名，并确认使用了全新的构建目录。本次验证中，`/opt/Qt5.14.2` 是否预先存在不是导致该错误的原因。

### 9.3 Qt Location 安装失败

`make install` 若在 `qtlocation/src/positioning` 中提示找不到 `-lclip2tri`、`-lpoly2tri` 或 `-lclipper`，表示 Qt Location/Qt Positioning 模块未安装成功。它不影响此前已成功安装的 qtbase 及其他模块；若项目不使用定位功能，可以暂时忽略。

### 9.4 外网机无法刷新目标软件源

检查目标源的域名、套件版本和架构是否能从外网机访问。脚本可以处理目标机和外网机的小版本差异，但不能替代不可达的软件源，也不能自动把 x86 下载环境变成 ARM64 下载环境。

## 10. 与 CLion 远程开发衔接

Qt 安装完成后，在 CLion 的 CMake Profile 中指定第 8 节的 `CMAKE_PREFIX_PATH=/opt/Qt5.14.2`。远程工具链、Deployment、VcXsrv 和 DISPLAY 等 CLion 侧的配置集中在[CLion Remote Host 远程开发环境搭建](./2026-01-05-clion-remote-host-setup.md)，本文不再展开。

## 附录：完整的 `install-deps.sh`

完整的 `install-deps.sh` 如下。正文只说明使用方式和工作原理，脚本集中在附录中，便于单独更新。

```bash
#!/bin/bash
#===============================================================
# 离线依赖 下载/安装 一体化脚本 v8
#
# 下载原理: 以指定的内网机 dpkg 状态（或空状态）让 apt 仅对目标包
#           求解，取得实际可安装方案中的精确包版本，再逐个下载。
#           不能把 apt-cache 的递归依赖图直接交给 apt 安装：其中
#           会同时包含互斥的替代依赖分支。
#
# 用法:
#   快照模式:  sudo ./install-deps.sh s        （在内网机上）
#   下载模式:  sudo ./install-deps.sh d [内网机-status] [内网机软件源清单]
#   安装模式:  sudo ./install-deps.sh i        （在内网机上）
#   指定目录:  sudo ./install-deps.sh i debs-xxxx
#
# 快照模式会在脚本同目录生成 target-dpkg-status 与 target-sources.list。
# 将脚本和这两个文件复制到外网机后，直接运行下载模式即可；脚本会自动
# 使用它们，使 apt 以内网机的实际已装版本和发行版软件源为基准求解。
#
# 不带参数运行会弹出选择菜单。
#===============================================================

#=============== 在这里修改你要下载的包（每次改这里就行）===============
PKGS=(
    build-essential
    perl
    python3
    libgl1-mesa-dev
    libfontconfig1-dev
    libfreetype6-dev
    libx11-dev
    libxext-dev
    libxfixes-dev
    libxi-dev
    libxrender-dev
    libxcb1-dev
    libx11-xcb-dev
    libxcb-glx0-dev
    libxcb-cursor-dev
    libxcb-icccm4-dev
    libxcb-image0-dev
    libxcb-keysyms1-dev
    libxcb-randr0-dev
    libxcb-render-util0-dev
    libxcb-shape0-dev
    libxcb-xinerama0-dev
    libxcb-xkb-dev
    libxkbcommon-dev
    libxkbcommon-x11-dev
    libssl-dev
    libsqlite3-dev
    libicu-dev
)
#======================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_LIST=/etc/apt/sources.list.d/offline-local.list
SNAPSHOT_STATUS_NAME=target-dpkg-status
SNAPSHOT_SOURCES_NAME=target-sources.list

#---------------------------------------------------------------
# 模式选择
#---------------------------------------------------------------
MODE="${1:-}"
if [ -z "$MODE" ]; then
    echo "============================================"
    echo " 离线依赖工具"
    echo "   s  快照模式  —— 在内网机导出软件包状态和软件源清单"
    echo "   d  下载模式  —— 在联网机上由求解器统一下载依赖并制作为本地 apt 源"
    echo "   i  安装模式  —— 在内网机上利用同目录的本地源安装"
    echo "============================================"
    read -r -p "请选择 [S/D/I]: " MODE
fi

case "$(echo "$MODE" | tr 'SDI' 'sdi')" in
    s)        MODE=snapshot ;;
    d)        MODE=download ;;
    i)        MODE=install ;;
    snapshot) ;;
    download) ;;
    install)  ;;
    *) echo "错误: 无效的选择 '$MODE'"; exit 1 ;;
esac

#===============================================================
#                        快 照 模 式
#===============================================================
if [ "$MODE" = "snapshot" ]; then
    if [ "$(id -u)" -ne 0 ]; then
        echo "错误: 快照需要权限，请用 sudo 运行"
        exit 1
    fi

    SNAPSHOT_STATUS_FILE="$SCRIPT_DIR/$SNAPSHOT_STATUS_NAME"
    SNAPSHOT_SOURCES_FILE="$SCRIPT_DIR/$SNAPSHOT_SOURCES_NAME"
    SOURCE_FILES=()

    if [ -f /etc/apt/sources.list ]; then
        SOURCE_FILES+=(/etc/apt/sources.list)
    fi
    if [ -d /etc/apt/sources.list.d ]; then
        while IFS= read -r -d '' source_file; do
            # 避免把上一次离线安装临时注册的本地源写入快照。
            [ "$source_file" = "$SOURCE_LIST" ] && continue
            SOURCE_FILES+=("$source_file")
        done < <(find /etc/apt/sources.list.d -maxdepth 1 -type f -name '*.list' -print0)
    fi

    if [ "${#SOURCE_FILES[@]}" -eq 0 ]; then
        echo "错误: 未找到 /etc/apt/sources.list 或 sources.list.d/*.list"
        exit 1
    fi

    echo "============================================"
    echo " 快照模式"
    echo " 状态文件  : $SNAPSHOT_STATUS_FILE"
    echo " 源清单    : $SNAPSHOT_SOURCES_FILE"
    echo " 架构      : $(dpkg --print-architecture)"
    echo " 系统      : $(lsb_release -ds 2>/dev/null || cat /etc/os-release | head -1)"
    echo "============================================"
    echo ""

    echo "[1/2] 导出内网机软件包状态..."
    if ! cp /var/lib/dpkg/status "$SNAPSHOT_STATUS_FILE"; then
        echo "错误: 无法导出 /var/lib/dpkg/status"
        exit 1
    fi
    chmod 0644 "$SNAPSHOT_STATUS_FILE"

    echo "[2/2] 导出软件源清单..."
    if ! grep -hE '^[[:space:]]*deb[[:space:]]' \
            "${SOURCE_FILES[@]}" > "$SNAPSHOT_SOURCES_FILE"; then
        rm -f "$SNAPSHOT_STATUS_FILE" "$SNAPSHOT_SOURCES_FILE"
        echo "错误: 未从传统 .list 软件源配置中找到任何 deb 条目"
        exit 1
    fi
    chmod 0644 "$SNAPSHOT_SOURCES_FILE"

    echo ""
    echo "============================================"
    echo " 快照完成！请将以下三个文件复制到外网机同一目录："
    echo "   $(basename "${BASH_SOURCE[0]}")"
    echo "   $SNAPSHOT_STATUS_NAME"
    echo "   $SNAPSHOT_SOURCES_NAME"
    echo " 外网机执行: sudo ./$(basename "${BASH_SOURCE[0]}") d"
    echo "============================================"
    exit 0
fi

#===============================================================
#                        安 装 模 式
#===============================================================
if [ "$MODE" = "install" ]; then

    if [ "$(id -u)" -ne 0 ]; then
        echo "错误: 安装需要权限，请用 sudo 运行"
        exit 1
    fi

    #------- 定位本地源目录 -------
    DEBS_DIR="${2:-}"

    if [ -z "$DEBS_DIR" ]; then
        # 优先：脚本所在目录本身就是源目录（从 tar 包解压出来的情况）
        if [ -f "$SCRIPT_DIR/Packages.gz" ]; then
            DEBS_DIR="$SCRIPT_DIR"
        else
            # 其次：同目录下最新的含 Packages.gz 的 debs-* 目录
            for d in $(ls -dt "$SCRIPT_DIR"/debs-* 2>/dev/null); do
                if [ -f "$d/Packages.gz" ]; then
                    DEBS_DIR="$d"
                    break
                fi
            done
        fi
    fi

    if [ -z "$DEBS_DIR" ] || [ ! -f "$DEBS_DIR/Packages.gz" ]; then
        echo "错误: 找不到本地源目录（需要包含 Packages.gz）"
        echo ""
        echo "请确认:"
        echo "  1. tar 包已解压，且本脚本与 debs 目录在一起"
        echo "  2. 或手动指定: sudo $0 i debs-xxxxxx"
        exit 1
    fi

    DEBS_DIR="$(cd "$DEBS_DIR" && pwd)"

    #------- 读取目标包列表 -------
    if [ ! -f "$DEBS_DIR/pkglist.txt" ]; then
        echo "错误: $DEBS_DIR 中缺少 pkglist.txt（下载时自动生成的目标包清单）"
        exit 1
    fi
    PKGLIST=$(cat "$DEBS_DIR/pkglist.txt")

    # 若下载时指定了内网机 status 快照，拒绝在状态已变化的机器上安装。
    # 否则 apt 可能因运行库补丁版本不同而无法满足 dev 包的精确依赖。
    if [ -f "$DEBS_DIR/target-status.sha256" ]; then
        EXPECTED_STATUS_SHA=$(awk 'NR == 1 { print $1 }' "$DEBS_DIR/target-status.sha256")
        ACTUAL_STATUS_SHA=$(sha256sum /var/lib/dpkg/status | awk '{ print $1 }')
        if [ -z "$EXPECTED_STATUS_SHA" ] || [ "$EXPECTED_STATUS_SHA" != "$ACTUAL_STATUS_SHA" ]; then
            echo "错误: 当前机器的软件包状态与下载离线包时的状态快照不一致"
            echo "请重新从本机复制 /var/lib/dpkg/status 到外网机，并重新执行下载模式。"
            exit 1
        fi
    fi

    echo "============================================"
    echo " 安装模式"
    echo " 本地源  : $DEBS_DIR"
    echo " 目标包  : $PKGLIST"
    echo "============================================"
    echo ""

    #------- [1/4] 注册临时本地源 -------
    echo "[1/4] 注册临时本地源..."
    echo "deb [trusted=yes] file:$DEBS_DIR ./" > "$SOURCE_LIST"

    #------- [2/4] 只更新本地源索引 -------
    echo "[2/4] 更新本地源索引..."
    if ! apt-get update \
            -o Dir::Etc::SourceList="$SOURCE_LIST" \
            -o Dir::Etc::SourceParts=-; then
        echo "错误: 无法读取本地源索引"
        rm -f "$SOURCE_LIST"
        exit 1
    fi

    #------- [3/4] 安装（强制只用本地源，屏蔽在线源）-------
    echo "[3/4] 由 apt 求解器从本地池挑选安装..."
    if apt-get install -y \
           --no-install-recommends \
           -o Dir::Etc::SourceList="$SOURCE_LIST" \
           -o Dir::Etc::SourceParts=- \
           $PKGLIST; then
        INSTALL_OK=yes
    else
        INSTALL_OK=no
    fi

    #------- [4/4] 清理 -------
    echo "[4/4] 清理临时源配置..."
    rm -f "$SOURCE_LIST"

    echo ""
    if [ "$INSTALL_OK" = "yes" ]; then
        echo "============================================"
        echo " 全部完成！验证: g++ --version"
        echo "============================================"
    else
        echo "============================================"
        echo " 安装过程有报错，请把上面的输出反馈排查"
        echo "============================================"
        exit 1
    fi

    exit 0
fi

#===============================================================
#                        下 载 模 式
#===============================================================
if [ "$(id -u)" -ne 0 ]; then
    echo "错误: 下载需要权限，请用 sudo 运行"
    exit 1
fi

for cmd in apt-get dpkg dpkg-scanpackages; do
    command -v "$cmd" >/dev/null 2>&1 || { echo "错误: 找不到 $cmd"; exit 1; }
done

STAMP="$(date +%Y%m%d-%H%M)"
OUT_DIR="$SCRIPT_DIR/debs-$STAMP"
TARGET_STATUS="${2:-}"
DOWNLOAD_SOURCE_LIST="${3:-}"
DOWNLOAD_SOURCE_OPTIONS=()

# 快照模式生成的固定文件与脚本放在同一目录时，下载模式自动使用它们。
if [ -z "$TARGET_STATUS" ] && [ -r "$SCRIPT_DIR/$SNAPSHOT_STATUS_NAME" ]; then
    TARGET_STATUS="$SCRIPT_DIR/$SNAPSHOT_STATUS_NAME"
fi
if [ -z "$DOWNLOAD_SOURCE_LIST" ] && [ -r "$SCRIPT_DIR/$SNAPSHOT_SOURCES_NAME" ]; then
    DOWNLOAD_SOURCE_LIST="$SCRIPT_DIR/$SNAPSHOT_SOURCES_NAME"
fi

if [ -n "$DOWNLOAD_SOURCE_LIST" ]; then
    if [ ! -r "$DOWNLOAD_SOURCE_LIST" ]; then
        echo "错误: 无法读取指定的软件源清单: $DOWNLOAD_SOURCE_LIST"
        exit 1
    fi
    DOWNLOAD_SOURCE_LIST="$(readlink -f "$DOWNLOAD_SOURCE_LIST")"
    DOWNLOAD_SOURCE_OPTIONS=(
        -o "Dir::Etc::SourceList=$DOWNLOAD_SOURCE_LIST"
        -o "Dir::Etc::SourceParts=-"
    )
fi

echo "============================================"
echo " 下载模式（求解器统一决策版）"
echo " 目标包数量: ${#PKGS[@]}"
echo " 输出目录  : $OUT_DIR"
echo " 架构      : $(dpkg --print-architecture)"
echo " 系统      : $(lsb_release -ds 2>/dev/null || cat /etc/os-release | head -1)"
if [ -n "$TARGET_STATUS" ]; then
    echo " 状态快照  : $TARGET_STATUS"
else
    echo " 状态快照  : 未指定（按空状态下载完整闭包）"
fi
if [ -n "$DOWNLOAD_SOURCE_LIST" ]; then
    echo " 软件源清单: $DOWNLOAD_SOURCE_LIST"
else
    echo " 软件源清单: 外网机当前配置"
fi
echo "============================================"

#---------------------------------------------------------------
# [1/5] 刷新软件源索引
#---------------------------------------------------------------
echo ""
echo "[1/5] 正在刷新源索引（保证所有包取自同一套最新套件）..."
if ! apt-get "${DOWNLOAD_SOURCE_OPTIONS[@]}" \
        -o APT::Update::Error-Mode=any update; then
    echo "错误: 源索引刷新失败。请确认所有 Kylin 软件源均可访问后再运行。"
    exit 1
fi

#---------------------------------------------------------------
# [2/5] 在空状态中由 apt 求解完整安装方案
#---------------------------------------------------------------
echo "[2/5] 正在由 apt 求解完整依赖方案..."

# 未指定状态快照时，使用空 status 文件模拟一台未安装目标依赖的机器，
# 以取得完整闭包。指定快照时，则以内网机的真实状态求解，避免 dev 包
# 与内网机已有运行库的精确版本依赖不一致。
PLAN_DIR=$(mktemp -d)
trap 'rm -rf "$PLAN_DIR"' EXIT
if [ -n "$TARGET_STATUS" ]; then
    if [ ! -r "$TARGET_STATUS" ]; then
        echo "错误: 无法读取指定的内网机 status 快照: $TARGET_STATUS"
        exit 1
    fi
    APT_STATUS="$(readlink -f "$TARGET_STATUS")"
    STATUS_MODE="内网机状态快照"
else
    APT_STATUS="$PLAN_DIR/status"
    : > "$APT_STATUS"
    STATUS_MODE="空状态（完整闭包）"
fi

if ! LC_ALL=C apt-get "${DOWNLOAD_SOURCE_OPTIONS[@]}" \
        -s --no-install-recommends \
        -o Dir::State::status="$APT_STATUS" \
        install "${PKGS[@]}" > "$PLAN_DIR/solution.txt" 2>&1; then
    cat "$PLAN_DIR/solution.txt"
    echo "错误: apt 无法为目标包求得可安装方案，请检查包名和软件源"
    exit 1
fi

# apt 的模拟输出中每个 Inst 行都是求解器最终选择的一个具体 deb。
# 显式保留版本可避免下载阶段的源更新或候选版本变化破坏该方案。
mapfile -t DOWNLOAD_SPECS < <(
    sed -n 's/^Inst \([^ ]*\).* (\([^ )]*\).*/\1=\2/p' "$PLAN_DIR/solution.txt"
)

if [ "${#DOWNLOAD_SPECS[@]}" -eq 0 ]; then
    echo "错误: 未能从 apt 求解结果中提取任何待下载包"
    exit 1
fi

TOTAL=${#DOWNLOAD_SPECS[@]}
printf '%s\n' "${DOWNLOAD_SPECS[@]}" > "$PLAN_DIR/solution-packages.txt"
echo "      求解完成，共 $TOTAL 个包（含依赖）；求解基准: $STATUS_MODE"

#---------------------------------------------------------------
# [3/5] 求解器统一决策 + 下载（关键步骤）
#---------------------------------------------------------------
# 使用上一步的精确版本清单下载，而不是将原始依赖图当作安装目标。
# 后者会要求 apt 同时安装所有替代分支，造成互斥包冲突。
echo "[3/5] 正在下载求解器选定的整个闭包..."
echo "      （这一步可能持续几分钟，请耐心等待）"
echo ""

mkdir -p "$OUT_DIR"
if ! (
    cd "$OUT_DIR" &&
    LC_ALL=C apt-get "${DOWNLOAD_SOURCE_OPTIONS[@]}" \
        download "${DOWNLOAD_SPECS[@]}"
); then
    echo ""
    echo "错误: 下载求解方案失败。请把上面的报错反馈排查。"
    exit 1
fi

echo ""
echo "      下载完成，包已保存到 $OUT_DIR"

#---------------------------------------------------------------
# [4/5] 制作本地 apt 源
#---------------------------------------------------------------
echo "[4/5] 整理包并制作本地 apt 源..."

CACHED_COUNT=$(find "$OUT_DIR" -maxdepth 1 -type f -name '*.deb' | wc -l)

if [ "$CACHED_COUNT" -eq 0 ]; then
    echo "错误: 输出目录中没有下载到任何 deb 包，无法继续"
    exit 1
fi

# 同时生成 Packages 和 Packages.gz
# （apt 的 file: 平板仓库在部分版本下只认未压缩的 Packages 文件，
#  只有 .gz 会导致索引加载失败）
(cd "$OUT_DIR" && \
    dpkg-scanpackages --multiversion . /dev/null 2>/dev/null > Packages && \
    gzip -9kc Packages > Packages.gz)

# 写入目标包清单（安装模式靠它知道要装什么）
echo "${PKGS[@]}" > "$OUT_DIR/pkglist.txt"

# 安装前核对内网机状态仍与下载时一致，防止错误地混用不同补丁级别。
if [ -n "$TARGET_STATUS" ]; then
    sha256sum "$APT_STATUS" > "$OUT_DIR/target-status.sha256"
fi
if [ -n "$DOWNLOAD_SOURCE_LIST" ]; then
    cp "$DOWNLOAD_SOURCE_LIST" "$OUT_DIR/target-sources.list"
fi

# 拷贝脚本自身进包，内网机解压后即有安装工具
cp "${BASH_SOURCE[0]}" "$OUT_DIR/$(basename "${BASH_SOURCE[0]}")"

#---------------------------------------------------------------
# [5/5] 汇总 + 打包
#---------------------------------------------------------------
DEB_COUNT=$(ls "$OUT_DIR"/*.deb 2>/dev/null | wc -l)
DEB_SIZE=$(du -sh "$OUT_DIR" | cut -f1)

echo "[5/5] 完成"
echo ""
echo "============================================"
echo " 下载完成！"
echo " 位置: $OUT_DIR"
echo " 成功: $DEB_COUNT 个 deb 包，共 $DEB_SIZE"
echo "============================================"
echo ""

#------- 版本一致性自检 -------
echo ">>> 版本一致性自检（dev 包与运行库版本应成对一致）："
for stem in libsqlite3 libfontconfig1 libssl libfreetype6 libicu; do
    PAIR=$(ls "$OUT_DIR" 2>/dev/null | grep "^${stem}" | sort)
    [ -n "$PAIR" ] && echo "$PAIR" | sed 's/^/    /'
done
echo ""

read -r -p "是否现在自动打包为 tar.gz? [y/N] " ans
if [ "$ans" = "y" ] || [ "$ans" = "Y" ]; then
    TARBALL="$SCRIPT_DIR/deps-offline-$STAMP.tar.gz"
    tar czf "$TARBALL" -C "$SCRIPT_DIR" "$(basename "$OUT_DIR")"
    echo ""
    echo "已生成: $TARBALL ($(du -sh "$TARBALL" | cut -f1))"
    echo ""
    echo "===== 内网机操作（就两条命令）====="
    echo "  tar xzf $(basename "$TARBALL")"
    echo "  cd $(basename "$OUT_DIR") && sudo ./$(basename "${BASH_SOURCE[0]}") i"
    echo "==================================="
fi

```
