---
layout: article
title: 内存模型与并发编程
date: 2026-05-15 10:00:00 +0800
tags:
  - memory-model
  - concurrency
  - cpp-atomic
  - memory-order
  - cpp
---


[前文](./2026-05-15-mesi-store-buffer-invalid-queue.md)推演了 MESI 协议引入 Store Buffer 和 Invalidate Queue 后如何导致内存重排，以及写屏障和读屏障如何恢复顺序。本文从程序员的视角出发，回答一个实践问题：并发代码为什么会出错，以及 C++ 提供了什么工具来防止这些错误。

## 一、单核的承诺与多核的现实

### 1、as-if-serial：编译器和 CPU 的优化红线

编译器和 CPU 在优化时遵守一条不可逾越的红线：**as-if-serial**（仿佛是顺序执行）。不管怎么重排序、怎么乱序执行，单线程程序的最终结果不能被改变。

这依赖于数据依赖分析：

```c
int a = 1;
int b = 2;
```

`a` 和 `b` 互不影响，编译器或 CPU 可以自由调换顺序——单线程无法感知。

```c
int a = 1;
int b = a + 2;
```

`b` 依赖 `a`，编译器和 CPU 不会将 `b = a + 2` 重排到 `a = 1` 之前——这违反数据依赖，破坏 as-if-serial。

即使两个没有依赖的语句发生了乱序执行，现代 CPU 通过**乱序执行、顺序退休**（Out-of-Order Execution with In-order Retirement）机制保证：内部计算可以乱序完成，但结果写入寄存器或内存时，依然按代码顺序提交。当前线程自己观察到的执行结果，始终与严格顺序执行一致。

### 2、as-if-serial 的边界

as-if-serial 只对当前线程负责，对其他线程的观测不做任何承诺。

硬件设计者追求性能，不会实现完全的顺序一致性（Sequential Consistency）——那要求禁止 Store Buffer 和乱序执行，代价不可接受。as-if-serial 是妥协的产物：单核上一切正常，多核上"自己觉得按顺序执行"不等于"别人看到按顺序生效"。

前文的 `foo/bar` 示例已经证明了这一点：CPU 0 按顺序执行了 `a=1; b=1`，但 CPU 1 看到 `b=1` 时 `a` 仍为 0——Store Buffer 导致 `b=1` 先于 `a=1` 对其他核心可见。

以下从三个维度分析 as-if-serial 在多核下具体如何失效。

## 二、并发代码为何出错：三个失效模式

### 1、原子性失效

一个看似简单的 `i++` 在 CPU 内部被拆解为三步：

1. **Read**：从 Cache Line 读出值
2. **Modify**：在 ALU 中加 1
3. **Write**：写回 Store Buffer，触发 MESI 的 Invalidate 广播

执行 Modify 时，该核心并未独占这块内存。其他核心可能同时读到了同一个旧值，各自加 1 后写回，MESI 协议虽保证最终只有一个值留下，但另一个核心的加 1 操作已被覆盖。

x86 提供的解决方案是 **LOCK 前缀**（如 `lock xadd`）。使用 `std::atomic` 时，编译器在汇编指令前加上 LOCK 前缀，它做两件事：

- **缓存锁定**（Cache Locking）：利用 MESI 协议，强制将 Cache Line 锁定在 M 或 E 状态，期间拒绝其他核心对该地址的读写请求
- **阻止乱序 + 冲刷缓冲区**：阻止指令前后的读写操作重排，强制排空 Store Buffer

直到"读-改-写"三步完成，Cache Line 锁定才解除。

**边界条件**：缓存锁定仅在数据不跨越 Cache Line 边界时生效。若原子变量横跨两个 Cache Line（如未对齐的 8 字节变量恰好跨越 64 字节边界），LOCK 前缀退化为**总线锁**（Bus Lock），锁定整个前端总线，性能代价远高于缓存锁定。这也是原子变量通常要求自然对齐的原因。

### 2、可见性失效

一个线程修改了数据，另一个线程何时能看到？前文已经给出了答案：Store Buffer 导致写入延迟生效，Invalidate Queue 导致读取过期数据。两者共同造成多核间的可见性滞后。

可见性失效的直觉表述：**写了不等于别人立刻看得见**。写屏障冲刷 Store Buffer，读屏障处理 Invalidate Queue，这是恢复可见性的手段。

### 3、有序性失效

代码的执行顺序是否与书写顺序一致？有序性的破坏来自两个层面。

**编译器重排**

编译器在 `-O2`、`-O3` 优化下，会根据数据依赖分析重排指令。编译器只看当前线程的上下文，无法感知跨线程的数据依赖：

```c
// 线程 1
config_data = load_config();  // 步骤 A
initialized = true;            // 步骤 B
```

编译器认为 `config_data` 和 `initialized` 无依赖，可能将步骤 B 提前。单线程无影响，但线程 2 看到 `initialized == true` 后读取 `config_data`，可能读到未初始化的值。

编译器屏障（如 `asm volatile("" ::: "memory")`）可以阻止编译器对屏障两侧的重排优化，但不生成任何 CPU 屏障指令。

**CPU 重排**

即便编译器按顺序生成指令，CPU 的乱序执行和 Store Buffer 也会导致实际生效顺序与代码顺序不同。前文的 Dekker 反例展示了最对称的情况：

```
CPU 0（线程 A）            CPU 1（线程 B）
    X = 1;                    Y = 1;
    r1 = Y;                   r2 = X;
```

顺序一致性下，`X=1` 和 `Y=1` 必然有一个先执行，`r1==0 && r2==0` 不可能成立。但有 Store Buffer 时，两个核心各自将写入存入 Store Buffer 后立即从本地缓存读取对方的变量——对方写入尚未刷入缓存，两个核心都读到 0。

CPU 内存屏障（x86 的 `mfence`，ARM 的 `DMB`）强制恢复顺序。

### 4、三个失效的关系

| 问题 | 单线程 | 多线程 | 根源 | 解决手段 |
|------|--------|--------|------|---------|
| **原子性** | 天然安全 | 读-改-写被覆盖 | 操作非不可分割 | LOCK 前缀 / 互斥锁 |
| **可见性** | 天然可见 | 写入延迟生效 | Store Buffer / Invalidate Queue | 内存屏障 |
| **有序性** | as-if-serial 保证 | 执行顺序与代码顺序不一致 | 编译器重排 + CPU 重排 | 编译器屏障 + CPU 屏障 |

三者在底层相互关联：LOCK 前缀同时保证原子性和有序性，内存屏障同时恢复可见性和有序性。C++ 的 `memory_order_seq_cst`（默认内存序）同时提供全部三种保证。

## 三、C++ 的并发工具

### 1、volatile：常见误用

不同语言的 `volatile` 关键字语义差异极大，是并发编程中常见的认知陷阱：

| 语义 | C/C++ volatile | Java/C# volatile |
|------|----------------|------------------|
| 禁止编译器缓存到寄存器 | 是 | 是 |
| 提供内存屏障 | **否** | 是 |
| 保证跨核可见性 | **否** | 是 |
| 禁止指令重排 | **否** | 是 |

C/C++ 的 `volatile` 仅告诉编译器"该变量可能被外部因素修改，每次使用必须从内存读取，不允许优化到寄存器"。它解决的是编译器优化导致的可见性问题（如 `while (keep_running)` 循环变量被缓存到寄存器），**不提供任何内存屏障语义**，无法防止 CPU 重排。

Java/C# 的 `volatile` 在编译器约束之外，还会插入内存屏障指令，保证跨核可见性和有序性。

C/C++ `volatile` 适用于与硬件寄存器或信号处理函数交互的场景，**不适用于多线程同步**。多线程同步应使用 `std::atomic`。

### 2、std::atomic 与内存序

C++11 引入的 `std::atomic` 是并发编程的正确工具。它提供不同的内存序选项，对应不同程度的同步保证。选择哪个内存序，本质上是性能与安全之间的权衡。

| 内存序 | 保证 | 对应硬件操作 | 开销 |
|--------|------|-------------|------|
| `memory_order_relaxed` | 仅原子性，无可见性和有序性保证 | 无屏障 | 最低 |
| `memory_order_acquire` | 读屏障：屏障后的读写不会重排到屏障前 | 处理 Invalidate Queue | 中等 |
| `memory_order_release` | 写屏障：屏障前的读写不会重排到屏障后 | 冲刷 Store Buffer | 中等 |
| `memory_order_seq_cst` | 全屏障：顺序一致性 | 同时冲刷 Store Buffer 和处理 Invalidate Queue | 最高 |

**memory_order_relaxed**

只保证操作的原子性（不会出现读-改-写被覆盖），不提供任何可见性和有序性保证。适用于计数器等不需要同步的场景：

```cpp
std::atomic<int> counter{0};

// 多个线程同时执行
counter.fetch_add(1, std::memory_order_relaxed);
```

每个线程的递增不会被覆盖，但各线程看到 counter 的值顺序没有保证。如果只需要"总数正确"，`relaxed` 足够。

**acquire/release：实践中的最佳平衡点**

`acquire` 和 `release` 通常配对使用，形成同步关系——`release` 之前的所有写操作对 `acquire` 之后的读操作可见。这是实践中最常用的模式：

```cpp
std::atomic<bool> ready{false};
int data = 0;

// 线程 1（生产者）
data = 42;                                        // 步骤 A
ready.store(true, std::memory_order_release);     // 步骤 B

// 线程 2（消费者）
while (!ready.load(std::memory_order_acquire)) {} // 步骤 C
assert(data == 42);                                // 步骤 D，保证成功
```

同步关系的建立过程：

1. 线程 1 的 `release` 保证步骤 A 不会被重排到步骤 B 之后——即使 `data` 不在本地缓存，写入也必须在 Store Buffer 中排于 `ready` 之前
2. 线程 2 的 `acquire` 保证步骤 D 不会被重排到步骤 C 之前——读取 `ready` 时先处理 Invalidate Queue，确保看到最新的 `data`
3. 当 `acquire` 读到 `release` 写入的值时，**同步关系建立**：线程 1 在 `release` 之前的所有写操作，对线程 2 在 `acquire` 之后的读操作可见

这个模式覆盖了绝大多数生产者-消费者场景，性能优于 `seq_cst`，安全性远优于 `relaxed`。

**memory_order_seq_cst：默认的安全选择**

`seq_cst` 是 `std::atomic` 操作的默认内存序，同时提供原子性、可见性和有序性三重保证。所有 `seq_cst` 操作在全局上保持一致的顺序。代价是性能最高开销。

在不确认该用哪个内存序时，使用默认的 `seq_cst` 是安全的。只有在对性能有明确要求、且能证明更弱的内存序足够时，才考虑降级。

**内存序与硬件屏障的映射**

前文推演的 Linux 内核屏障 API 与 C++ 内存序映射到同一套硬件指令，只是抽象层级不同：

| Linux 内核 | C++ 内存序 | 作用 |
|-----------|-----------|------|
| `smp_wmb()` | `memory_order_release` | 冲刷 Store Buffer |
| `smp_rmb()` | `memory_order_acquire` | 处理 Invalidate Queue |
| `smp_mb()` | `memory_order_seq_cst` | 两者兼做 |

## 四、架构差异：同一份代码的不同命运

不同 CPU 架构对重排的允许范围不同，形成了从强到弱的内存模型谱系。

| 重排类型 | x86 TSO | ARM Weak Model |
|----------|---------|----------------|
| Load-Load | 禁止 | 允许 |
| Load-Store | 禁止 | 允许 |
| Store-Store | 禁止 | 允许 |
| Store-Load | **允许** | 允许 |

x86 采用 **TSO**（Total Store Order）模型，仅允许 Store-Load 重排，对程序员较为友好。ARM、PowerPC 等架构采用弱内存模型，四种重排均可能发生。

同一份无锁并发代码在 x86 上运行正常，移植到 ARM 后出现数据竞争，根源不在代码逻辑，而在底层内存模型的承诺不同。x86 硬件自动禁止了 Load-Load、Load-Store、Store-Store 重排，相当于隐含了部分屏障；ARM 不提供这些隐含保证，必须由程序显式添加。

**实践建议**：

- 开发时使用 `std::atomic` 而非裸内存屏障，让编译器根据目标架构选择正确的指令
- 在 x86 上测试通过不等于逻辑正确——弱序架构会暴露 x86 隐含屏障掩盖的 bug
- 如需验证并发逻辑的正确性，应在 ARM 或使用 ThreadSanitizer 等工具进行测试
