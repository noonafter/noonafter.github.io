---
layout: article
title: Linux 线程状态解析：内核源码与 ps 符号
date: 2025-05-11 15:30:00 +0800
tags:
  - linux
  - thread
---


## 一、进程与线程

### 1、进程是资源容器，线程是执行实体

传统 UNIX 系统中，进程同时承担两个角色：资源分配单位和调度单位。引入线程后，这两个角色分离：

- **进程**：资源容器，提供独立的虚拟地址空间、文件描述符表、信号处理设置。它仍然代表一个运行中的程序实例。
- **线程**：执行实体，是 CPU 调度的基本单位，提供独立的逻辑控制流。

单线程进程中，进程与线程合一。多线程进程中，一个进程包含多个并发的逻辑控制流。

### 2、task_struct：内核眼中一切皆任务

Linux 内核不区分"进程对象"和"线程对象"，两者底层均用 `task_struct` 表示，统称为**可调度实体**（LWP，轻量级进程）。

- `fork()` 创建子进程：新建 `task_struct`，**不共享**地址空间、文件描述符表等。
- `clone()`（`pthread_create` 底层）创建线程：新建 `task_struct`，**共享**地址空间、文件描述符表等。

调度器始终以 `task_struct` 为单位进行调度，线程的引入只是让多个 `task_struct` 共享了更多资源。

ps命令显示的是主线程 `task_struct`（tgid == pid）的状态。我们通常说ps显示进程状态，是因为这个主线程的 `task_struct` 代表了这个进程，但是内核中并没有一个独立的“进程”结构体。

## 二、线程的内存视图

### 1、共享区域

同一进程内的所有线程共享进程用户态地址空间中的以下区域：

| 区域 | 说明 |
|------|------|
| 代码段（`.text`） | 可执行指令 |
| 数据段（`.data`、`.bss`、`.rodata`） | 全局变量、静态变量 |
| 堆（Heap） | `malloc` 动态分配的内存 |
| 共享库区域 | 动态链接库映射 |
| 文件描述符表、信号处理器 | 进程级资源 |

### 2、独有区域

每个线程私有：

- **栈（Stack）**：保存函数调用帧、局部变量、返回地址。
- **寄存器上下文**：`rip`（程序计数器）、`rsp`（栈顶指针）、`rbp`（栈帧基址）及通用寄存器。

**注意**：各线程的栈在物理上都位于进程的虚拟地址空间内，理论上可通过指针跨线程访问，但逻辑上视为私有。

### 3、为什么栈必须独有

每个线程有独立的函数调用链。若多个线程共享同一栈，函数调用的嵌套关系和局部变量将相互覆盖，无法正确执行。独立的 `rsp` 指向各自的栈顶，是线程独立执行的基础。



## 三、线程状态模型

### 1、内核源码中的状态定义

[Linux 5.0.21](https://elixir.bootlin.com/linux/v5.0.21/source/include/linux/sched.h#L71) 在 `include/linux/sched.h` 中以位掩码定义 `task_struct` 的状态字段 `__state`：

```c
/* Used in tsk->__state: */
#define TASK_RUNNING            0x00000000
#define TASK_INTERRUPTIBLE      0x00000001
#define TASK_UNINTERRUPTIBLE    0x00000002
#define __TASK_STOPPED          0x00000004
#define __TASK_TRACED           0x00000008
/* Used in tsk->exit_state: */
#define EXIT_DEAD               0x00000010
#define EXIT_ZOMBIE             0x00000020
/* Used in tsk->__state again: */
#define TASK_PARKED             0x00000040
#define TASK_DEAD               0x00000080
#define TASK_WAKEKILL           0x00000100
#define TASK_WAKING             0x00000200
#define TASK_NOLOAD             0x00000400
#define TASK_NEW                0x00000800
/* ... */

/* Convenience macros: */
#define TASK_KILLABLE           (TASK_WAKEKILL | TASK_UNINTERRUPTIBLE)
#define TASK_STOPPED            (TASK_WAKEKILL | __TASK_STOPPED)
#define TASK_IDLE               (TASK_UNINTERRUPTIBLE | TASK_NOLOAD)
#define TASK_NORMAL             (TASK_INTERRUPTIBLE | TASK_UNINTERRUPTIBLE)
```

状态字段采用位掩码设计，允许通过按位或组合出复合状态。例如 `TASK_KILLABLE` 是 `TASK_UNINTERRUPTIBLE` 的变体，在等待硬件 I/O 的同时仍可响应 `SIGKILL`。`TASK_IDLE` 用于内核空闲线程，不计入系统负载。

实际使用中，需要关注的核心状态只有以下几个：

### 2、核心状态与 ps 符号对照

| 内核状态宏 | ps 符号 | 含义 |
|-----------|---------|------|
| `TASK_RUNNING` | `R` | 正在 CPU 上运行，或在就绪队列等待调度 |
| `TASK_INTERRUPTIBLE` | `S` | 可中断睡眠，等待事件，可被信号唤醒 |
| `TASK_UNINTERRUPTIBLE` | `D` | 不可中断睡眠，通常等待硬件 I/O，不响应信号 |
| `__TASK_STOPPED` | `T` | 收到 `SIGSTOP`/`SIGTSTP` 暂停 |
| `__TASK_TRACED` | `T` | 被 `ptrace` 跟踪暂停（调试器挂起） |
| `EXIT_ZOMBIE` | `Z` | 已退出，父进程尚未调用 `wait()` 回收 |
| `EXIT_DEAD` | `X` | 即将彻底销毁，`ps` 通常不可见 |

`ps` 还会附加修饰符，如 `S+`（前台进程组）、`Ss`（会话领导者）、`l`（多线程）等。`ps` 默认按线程组（TGID）聚合显示，使用 `ps -eLf` 或 `top -H` 可查看每个线程的独立状态。

### 3、R 状态的内部拆分：Ready 与 Running

内核的 `TASK_RUNNING`（值为 `0`）涵盖两种逻辑状态，`ps` 均显示为 `R`，但调度语义不同：

- **Ready（就绪）**：线程在调度器的运行队列（Runqueue）中排队，等待分配 CPU。
- **Running（运行）**：线程占用 CPU，`current` 指针指向该 `task_struct`，正在执行指令。

线程从睡眠唤醒后，先进入 Ready，再由调度器选中进入 Running，不会直接跳到 Running。



## 四、阻塞的本质

### 1、定义

**阻塞**：线程主动等待某个条件（事件或资源），内核将其状态从 `TASK_RUNNING` 切换为睡眠态，并将其从就绪队列移出，放入等待队列。条件满足后，内核将其唤醒并重新加入就绪队列。

阻塞期间线程不占用 CPU。

### 2、TASK_INTERRUPTIBLE vs TASK_UNINTERRUPTIBLE

| | `S`（可中断睡眠） | `D`（不可中断睡眠） |
|--|-----------------|-------------------|
| 能否被信号唤醒 | 能 | 否 |
| 典型场景 | `read` 等待数据、`sleep`、`pause`、`wait`、`mutex_lock` | 磁盘 I/O、特定设备驱动等待 |
| 设计原因 | 允许用户中断等待 | 保护硬件操作的原子性，防止驱动逻辑混乱 |

`D` 状态的进程无法被 `kill -9` 终止，只有等待硬件响应完成后才会自动醒来。这是系统卡死时某些进程无法杀死的根本原因。

### 3、Stopped（T）不是阻塞

| | 阻塞（S/D） | 停止（T） |
|--|------------|---------|
| 发起方式 | 线程主动调用系统调用 | 外界信号强制暂停 |
| 恢复条件 | 等待的事件发生，自动转为就绪 | 必须收到 `SIGCONT` 才能恢复 |
| 典型触发 | `read`、`sleep`、`wait` | `SIGSTOP`、`SIGTSTP`、`ptrace` |

`SIGSTOP` 产生的是 `T` 状态，不属于阻塞。

### 4、忙等待（Busy Waiting）vs 阻塞

| | 阻塞 | 忙等待/自旋 |
|--|------|-----------|
| CPU 占用 | 不占用，线程交出 CPU | 持续占用，循环执行检查指令 |
| 内核参与 | 涉及上下文切换和状态管理 | 不涉及（或极少） |
| ps 状态 | `S` 或 `D` | `R` |
| 适用场景 | 等待时间较长（如磁盘 I/O） | 等待时间极短（如多核自旋锁） |

用户态忙等示例：

```c
while (!flag) { /* 空循环，持续消耗 CPU */ }
```

内核态自旋锁（`spin_lock`）在获取不到锁时持续循环检测，不会进入睡眠。



## 五、线程状态转换

### 1、状态转换图

![thread-state](https://noonafter.cn/assets/images/posts/2025-05-11-linux-thread-state/thread-state.png)

图中共 8 个节点：起始黑点、Ready、Running、Sleeping、DiskSleep、Stopped、Traced、Zombie、终点靶心。以下按转换类别逐一说明。

### 2、CPU 调度流转

线程创建后进入 Ready，等待调度器选中：

| 转换 | 触发条件 |
|------|---------|
| 起始 → Ready | `clone()`/`fork()` 创建线程 |
| Ready → Running | 调度器选中（`schedule()`），分配 CPU 时间片 |
| Running → Ready | 时间片耗尽或被高优先级线程抢占（preempt） |

### 3、两种睡眠（阻塞）

线程主动等待某个条件时进入睡眠，让出 CPU：

| 转换 | 触发条件 | 对应内核状态 |
|------|---------|------------|
| Running → Sleeping | `read()`（无数据）、`write()`（缓冲区满）、`sleep()`、`pause()`、`wait()`/`waitpid()`、`mutex_lock()` 等系统调用阻塞 | `TASK_INTERRUPTIBLE` |
| Sleeping → Ready | 数据到达、定时器超时、信号唤醒 | — |
| Running → DiskSleep | 内核 I/O 等待（磁盘读写、特定设备驱动） | `TASK_UNINTERRUPTIBLE` |
| DiskSleep → Ready | I/O 完成，硬件中断唤醒 | — |

Sleeping（`S`）可被信号唤醒；DiskSleep（`D`）不响应任何信号，`kill -9` 也无效，只有等 I/O 完成才自动醒来。

几个常见调用的路径：

- **`sleep(n)`**：Running → Sleeping，定时器超时 → Ready。
- **`pause()`**：Running → Sleeping，收到任意非忽略信号并执行处理函数后 → Ready。
- **`waitpid()`**：Running → Sleeping，子进程状态变化后 → Ready。

### 4、暂停与跟踪

由外界信号强制暂停，不属于阻塞：

| 转换 | 触发条件 |
|------|---------|
| Running → Stopped | 收到 `SIGSTOP` 或 `SIGTSTP` |
| Stopped → Ready | 收到 `SIGCONT` |
| Running → Traced | `ptrace` 挂起（如 GDB 断点） |
| Traced → Ready | `ptrace` 恢复（调试器 continue） |

Stopped 和 Traced 在 `ps` 中均显示为 `T`，对应内核的 `__TASK_STOPPED` 和 `__TASK_TRACED`。

### 5、退出

| 转换 | 触发条件 |
|------|---------|
| Running → Zombie | `exit()`/`return`，或收到 `SIGKILL` |
| Zombie → 终止 | 父线程调用 `wait()`/`waitpid()` 回收，释放 `task_struct` |

`SIGKILL` 的实际作用范围比图中更广：处于 Running、Ready、Sleeping，乃至部分 DiskSleep（`TASK_KILLABLE`）状态的线程，收到 `SIGKILL` 后均会强制转为 Zombie，等待父进程回收。



## 六、注意事项

### 1、Z 状态（僵尸进程）

子进程调用 `exit()` 后，内核释放其大部分资源，但保留 `task_struct` 以存储退出码。父进程调用 `wait()` 读取退出码后，`task_struct` 才被彻底销毁。

若父进程未调用 `wait()` 就退出，子进程由 `init`（PID 1）接管并回收。若父进程长期运行且不回收子进程，僵尸进程会持续占用 PID 资源。


作为一个教学逻辑模型，它在概念上进行了简化，与真实的 Linux 内核代码实现存在以下三个经典区别：

### 2、“Running”与“Ready”的状态区分

图中，`Running` 与 `Ready` 之间通过时间片耗尽和调度器选中来切换，ps命令查看时均显示未R状态。

在 Linux 内核代码中，它们统称为 `TASK_RUNNING` 状态,区别仅在于该任务当前是否正在 CPU 上执行（即 current 指针指向谁），还是在调度器的运行队列（Runqueue）里排队等待 CPU 分配。

### 3、“DiskSleep” 的命名
图中 `DiskSleep` 表示等待磁盘 I/O 等资源的阻塞状态。ps命令查看时，显示为 D 状态。

在 Linux 内核代码中, 其对应 `TASK_UNINTERRUPTIBLE`（不可中断睡眠）。图中的 DiskSleep 实际上是一个形象化的术语，因为等待物理磁盘 I/O 是它最常见的触发场景。由于该状态无法被常规信号唤醒，因此进程不仅会“卡住”，有时甚至能抵御 kill -9 强行杀死，直至 I/O 完成。

### 4、信号（SIGKILL/SIGTERM）的普遍杀伤力

目前 `收到 SIGKILL信号` 只在 Running -> Zombie 的路径上，但实际情况是，无论进程是处于 Running、Ready、Sleeping、甚至大部分 DiskSleep（比如KILLABLE）状态，一旦它收到 SIGKILL 或 SIGTERM 等无法忽略/被阻塞的致命信号，它在内核中都会强制中断当前行为，最终无一例外地转为 Zombie（僵尸态），等待父进程进行回收。

### 5、观察线程状态

```bash
# 查看所有线程的状态（每个线程独立一行）
ps -eLf

# top 中显示线程视图
top -H

# 查看特定进程的线程状态
cat /proc/<pid>/status        # 主线程
ls /proc/<pid>/task/          # 列出所有线程 TID
cat /proc/<pid>/task/<tid>/status  # 特定线程状态
```
