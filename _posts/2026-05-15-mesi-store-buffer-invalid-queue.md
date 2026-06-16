---
layout: article
title: MESI 的性能演进：Store Buffer、Invalidate Queue 与内存屏障
date: 2026-05-15 10:00:00 +0800
tags:
  - cache
  - concurrency
  - memory
---


## 一、缓存结构

现代 CPU 的速度远超内存系统。2006 年的 CPU 每纳秒可执行十条指令，主存访问延迟约数十纳秒，两者相差两个数量级；到了 2026 年，CPU 吞吐提升至每纳秒十至二十条指令，而 DDR5 在多核总线下的访问延迟因排队与校验开销退步至近百纳秒，差距扩大至三个数量级。这一持续扩大的速度差距，是现代 CPU 配备数十乃至上百兆字节缓存的根本原因。

![](https://noonafter.cn/assets/images/posts/2026-05-15-mesi-store-buffer-invalid-queue/cache-structure.jpg)

数据在 CPU 缓存与内存之间以固定长度的块流动，称为**缓存行**（Cache Line），大小通常为 2 的幂次方，范围从 16 到 256 字节。CPU 首次访问某个数据项时，该数据项不在缓存中，发生**缓存未命中**（冷启动未命中），CPU 必须等待数百个时钟周期，直到数据从内存加载到缓存。后续访问命中缓存，可全速运行。

缓存填满后，新的未命中需要逐出旧条目腾出空间，称为**容量未命中**。但大型缓存通常实现为硬件哈希表——其哈希桶（CPU 设计者称为"组"）大小固定、不支持链式链接，且相联度（每个桶的条目数）有限。因此即使缓存未满，也可能因哈希冲突被迫逐出旧条目，称为**相联性未命中**。

写入操作时，CPU 必须先将该数据项从其他 CPU 的缓存中移除（使其失效），才能安全修改。如果数据项存在于当前 CPU 缓存但处于只读状态，此过程称为**写未命中**。完成失效操作后，CPU 可重复读写该数据项。

若其他 CPU 随后尝试访问该数据项，则发生**通信未命中**——由第一个 CPU 为写入而使其失效导致。此类未命中通常由多核间通过共享数据通信（如互斥锁）引起。

缓存一致性协议负责确保所有 CPU 对数据的视图保持一致，防止数据丢失或不同 CPU 缓存中同一数据项的值相互冲突。

## 二、缓存一致性协议

缓存一致性协议管理缓存行状态，防止数据不一致或丢失。实际协议可能包含数十个状态，以下聚焦四状态的 **MESI** 协议。

### 1、MESI 四种状态

| 状态 | 含义 | 所有权 | 写回内存义务 | 内存一致性 |
|------|------|--------|-------------|-----------|
| **M** (Modified) | 已修改，与内存不一致 | 当前 CPU 独占 | 逐出前必须写回或移交 | 内存过期 |
| **E** (Exclusive) | 未修改，与内存一致 | 当前 CPU 独占 | 无需写回，可直接丢弃 | 内存有效 |
| **S** (Shared) | 未修改，与内存一致 | 多 CPU 共享，写入需许可 | 无需写回，可直接丢弃 | 内存有效 |
| **I** (Invalid) | 无有效数据 | 无 | 无 | — |

**M** 与 **E** 的关键区别：M 状态下内存数据过期，逐出缓存行前必须写回或移交给其他 CPU；E 状态下内存数据有效，可直接丢弃。两者的共同点是当前 CPU 独占该缓存行，可随时写入而无需与其他 CPU 协商。

**S** 状态下，数据可能存在于多个 CPU 的缓存中，任何 CPU 写入前须先获得其他 CPU 许可。

**I** 状态的缓存行不存储有效数据，新数据优先放入 I 状态的缓存行，避免替换有效数据导致未命中。

### 2、MESI 协议消息

缓存行在系统中移动需要 CPU 之间的通信。共享总线上的消息类型如下：

| 消息 | 说明 | 响应要求 |
|------|------|---------|
| **Read** | 请求指定物理地址的缓存行数据 | Read Response |
| **Read Response** | 响应 Read，返回缓存行数据 | — |
| **Invalidate** | 通知其他缓存移除指定地址的缓存行 | Invalidate ACK |
| **Invalidate ACK** | 确认已从缓存中移除指定数据 | — |
| **Read Invalidate** | Read + Invalidate 的组合 | Read Response + 一组 Invalidate ACK |
| **Writeback** | 将 M 状态的缓存行数据写回内存 | — |

Read Response 可能由内存或其他缓存提供——若某缓存持有 M 状态的数据，则必须由该缓存提供响应。

共享内存多处理器系统在硬件层面通过消息传递实现缓存一致性。使用分布式共享内存的 SMP 集群，在架构的两个层面都依赖消息传递。

### 3、MESI 状态转换

![](https://noonafter.cn/assets/images/posts/2026-05-15-mesi-store-buffer-invalid-queue/mesi-state-transition.jpg)

| 转换 | 触发条件 | 起始状态 | 目标状态 | 协议消息 |
|------|---------|---------|---------|---------|
| (a) | 写回内存，保留只读副本 | M | S | Writeback |
| (b) | CPU 向已独占的缓存行写入 | E | M | 无 |
| (c) | 收到 Read Invalidate，发送数据并失效本地副本 | M | I | Read Response + Invalidate ACK |
| (d) | 对不在缓存中的数据执行原子读-改-写 | I | M | Read Invalidate → Read Response + Invalidate ACK |
| (e) | 对只读数据执行原子读-改-写 | S | M | Invalidate → Invalidate ACK |
| (f) | 其他 CPU 读取此行，本 CPU 提供数据，保留只读副本 | M | S | Read → Read Response |
| (g) | 其他 CPU 读取此行，本 CPU 降级为只读 | E | S | Read → Read Response |
| (h) | CPU 预备写入，获取独占权 | S | E | Invalidate → Invalidate ACK |
| (i) | 其他 CPU 执行 Read Invalidate，本 CPU 发送数据并失效 | E/M | I | Read Response + Invalidate ACK |
| (j) | CPU 写入不在缓存中的数据 | I | E→M | Read Invalidate → Read Response + Invalidate ACK |
| (k) | CPU 加载数据到缓存 | I | E/S | Read → Read Response |
| (l) | 收到 Invalidate，使本地副本失效 | S | I | Invalidate ACK |

### 4、MESI 协议运行示例

以四 CPU 系统中地址 0 的数据流为例，缓存行大小为 256 字节。初始状态：所有 CPU 缓存行均为 I，内存数据有效。

| 序号 | CPU | 操作 | CPU 0 | CPU 1 | CPU 2 | CPU 3 | 内存 0 | 内存 8 |
|------|-----|------|-------|-------|-------|-------|--------|--------|
| 0 | — | 初始 | -/I | -/I | -/I | -/I | V | V |
| 1 | 0 | Load 0 | 0/E | -/I | -/I | -/I | V | V |
| 2 | 3 | Load 0 | 0/S | -/I | -/I | 0/S | V | V |
| 3 | 3 | Load 8 | 0/S | -/I | -/I | 8/E | V | V |
| 4 | 2 | Read Invalidate 0 | -/I | -/I | 0/E | 8/E | V | V |
| 5 | 2 | Store 0 | -/I | -/I | 0/M | 8/E | I | V |
| 6 | 1 | Atomic Inc 0 | -/I | 0/M | -/I | 8/E | I | V |
| 7 | 1 | Load 8 | -/I | 8/S | -/I | 8/S | V | V |

各步解析：

- **序号 1**：CPU 0 加载地址 0，无其他 CPU 持有副本 → E 状态
- **序号 2**：CPU 3 加载地址 0，CPU 0 响应 Read → 双方均降级为 S
- **序号 3**：CPU 3 加载地址 8，地址 0 的干净副本从 CPU 3 逐出（无回写），替换为 8/E
- **序号 4**：CPU 2 用 Read Invalidate 获取独占权，CPU 0 的副本失效
- **序号 5**：CPU 2 写入，状态变为 M，内存数据过期
- **序号 6**：CPU 1 用 Read Invalidate 从 CPU 2 获取数据并失效 CPU 2 的副本，CPU 1 变为 M
- **序号 7**：CPU 1 加载地址 8，先将地址 0 的脏数据写回内存（M→S），再与 CPU 3 共享地址 8

## 三、写入停顿与 Store Buffer

### 1、写入操作的不必要停顿

![](https://noonafter.cn/assets/images/posts/2026-05-15-mesi-store-buffer-invalid-queue/write-stall.jpg)

纯 MESI 协议下，CPU 0 向其他核心持有的 Shared 状态缓存行写入时，必须等待失效ACK到底才能写入。CPU 向本地内部结构写入仅需一个时钟周期（约 0.1 纳秒），但跨核写入必须将消息送上片上网络、在互连总线上发送 Invalidate 报文，并等待目标核心完成失效后返回 ACK。这一跨核交互的往返延迟在多核系统中通常需要数纳秒至数十纳秒，与核心内部的指令处理速度相差达两个甚至三个数量级（数百个时钟周期）。在没有异步缓冲的理想 MESI 状态下，CPU 0 只能在此期间让流水线彻底冻结停顿。然而，从结果来看，CPU 0 最终会无条件覆盖该缓存行的数据，这种为了多核强一致性而让高速执行引擎干等异步通信回执的代价，在物理尺度上是极其低效且毫无必要的。

### 2、Store Buffer

解决方案是在 CPU 与缓存之间添加 **Store Buffer**（存储缓冲区）。CPU 只需将写入记录存入 Store Buffer 即可继续执行后续指令（只需一个时钟周期，约 0.1 纳秒）。当缓存行最终到达时，数据从 Store Buffer 移入缓存行。

![](https://noonafter.cn/assets/images/posts/2026-05-15-mesi-store-buffer-invalid-queue/store-buffer.jpg)

### 3、Store Forwarding

Store Buffer 引入了自洽性违反问题。变量 `a` 和 `b` 初始为零，`a` 所在缓存行由 CPU 1 持有，`b` 由 CPU 0 持有：

```c
a = 1;
b = a + 1;
assert(b == 2);
```

执行序列：

1. CPU 0 执行 `a = 1`，缓存中无 `a` → 发送 Read Invalidate，将 `a=1` 存入 Store Buffer
2. CPU 1 收到 Read Invalidate，发送缓存行数据并使自身副本失效
3. CPU 0 执行 `b = a + 1`，收到来自 CPU 1 的缓存行（`a` 仍为 0）
4. CPU 0 从缓存加载 `a`，发现值为 0
5. CPU 0 将 Store Buffer 中的 `a=1` 应用到缓存行（但步骤 4 的加载已经使用了旧值）
6. CPU 0 计算 `b = 0 + 1 = 1`，存入缓存
7. `assert(b == 2)` **失败**

问题根源：`a` 存在两份拷贝——缓存中的旧值和 Store Buffer 中的新值。这破坏了一个基本保证：每个 CPU 始终将自身的操作视为按程序顺序发生。

硬件的修正方案是 **Store Forwarding**（存储转发）：CPU 执行加载操作时，同时查询 Store Buffer 和缓存。若 Store Buffer 中存在匹配地址的数据，直接从中读取，无需经过缓存。

![](https://noonafter.cn/assets/images/posts/2026-05-15-mesi-store-buffer-invalid-queue/store-forwarding.jpg)

启用 Store Forwarding 后，步骤 4 从 Store Buffer 中读到 `a=1`，计算 `b = 1 + 1 = 2`，断言通过。

### 4、Store Buffer 与内存屏障

Store Forwarding 修复了单核自洽性，但多核间的全局内存顺序仍可能被破坏：

```
初始状态: a = 0, b = 0
a 所在缓存行仅存在于 CPU 1
b 所在缓存行由 CPU 0 拥有

CPU 0 执行 foo():            CPU 1 执行 bar():
    a = 1;                       while (b == 0) continue;
    b = 1;                       assert(a == 1);
```

可能的执行序列：

1. CPU 0 执行 `a = 1`，缓存中无 `a` → 存入 Store Buffer，发送 Read Invalidate
2. CPU 1 执行 `while (b == 0)`，缓存中无 `b` → 发送 Read
3. CPU 0 执行 `b = 1`，`b` 已在缓存中（E 或 M 状态）→ **直接写入缓存**
4. CPU 0 收到 Read → 将 `b=1` 发送给 CPU 1，自身标记为 S
5. CPU 1 收到 `b=1` → 退出 while 循环
6. CPU 1 执行 `assert(a == 1)`，使用 `a` 的旧值 0 → **断言失败**
7. CPU 1 收到 Read Invalidate → 发送 `a` 的缓存行，使自身副本失效
8. CPU 0 收到缓存行 → 将 Store Buffer 中的 `a=1` 刷入缓存，但断言已经失败

`a=1` 需要跨核通信（延迟高），`b=1` 直接命中本地缓存（立即生效）。从全局视角看，`b=1` 先于 `a=1` 对其他核心可见——`foo()` 内部的写入顺序被硬件的异步机制重排了。

CPU 不知道变量间的关联关系，无法自动修复。硬件提供**内存屏障**指令，由软件显式声明顺序约束：

```
CPU 0 执行 foo():            CPU 1 执行 bar():
    a = 1;                       while (b == 0) continue;
    smp_mb();                    assert(a == 1);
    b = 1;
```

`smp_mb()` 的效果：将当前 Store Buffer 中的所有条目打上标记。屏障后的写操作，即使目标缓存行处于可写状态（E 或 M），也必须先写入 Store Buffer，等待所有标记条目刷入缓存后才能提交。

加入屏障后的执行序列：

1. CPU 0 执行 `a = 1`，缓存中无 `a` → 存入 Store Buffer，发送 Read Invalidate
2. CPU 1 执行 `while (b == 0)`，缓存中无 `b` → 发送 Read
3. CPU 0 执行 `smp_mb()` → **标记** Store Buffer 中的 `a=1`
4. CPU 0 执行 `b = 1`，`b` 在缓存中为 E 状态，但 Store Buffer 中存在标记条目 → **不能直接写入缓存**，存入 Store Buffer
5. CPU 0 收到 Read → 返回 `b` 的旧值 0，自身标记为 S
6. CPU 1 收到 `b=0` → 继续 while 循环
7. CPU 1 收到 Read Invalidate → 发送 `a` 的缓存行，本地置为 I
8. CPU 0 收到缓存行 → 将 Store Buffer 中的 **`a=1` 刷入缓存**（标记条目清空）
9. 标记条目清空后，CPU 0 尝试将 Store Buffer 中的 `b=1` 刷入缓存，但 `b` 为 S 状态 → 发送 Invalidate
10. CPU 1 收到 Invalidate → `b` 本地置为 I，返回 ACK
11. CPU 1 继续 `while (b == 0)`，`b` 不在缓存 → 发送 Read
12. CPU 0 收到 ACK → 将 `b=1` 写入缓存
13. CPU 0 收到 Read → 返回 `b=1`
14. CPU 1 收到 `b=1` → 退出循环
15. CPU 1 执行 `assert(a == 1)`，`a` 不在缓存 → 发送 Read → 从 CPU 0 获取 `a=1` → **断言通过**

`b=1` 在所有标记条目（`a=1`）刷入缓存之前被阻塞，保证了 `a=1` → `b=1` 的全局可见顺序。

## 四、Invalidate Queue

### 1、Store Buffer 的容量瓶颈

Store Buffer 容量极小（通常几个到十几个条目）。一段适度的写操作序列——尤其是全部导致缓存未命中时——就可能将其填满。填满后 CPU 必须等待失效处理完成、清空 Store Buffer 才能继续执行。内存屏障加剧了这一问题：屏障后的所有写操作必须等待屏障前的条目刷完，即使这些写操作命中缓存。

瓶颈的根源是 **Invalidate ACK 延迟过高**——目标 CPU 必须先完成缓存行失效操作，再返回 ACK。若 CPU 正在密集地加载和存储数据（全部命中缓存），失效操作可能被延迟。短时间内收到大量失效消息时，CPU 可能处理不过来，导致其他 CPU 停顿。

### 2、失效队列

解决方案同样是异步化：CPU 收到 Invalidate 消息后，将失效请求放入 **Invalidate Queue**（失效队列），**立即返回 ACK**。CPU 在后续合适的时机异步处理队列中的失效消息。

![](https://noonafter.cn/assets/images/posts/2026-05-15-mesi-store-buffer-invalid-queue/invalidate-queue.jpg)

拥有 Invalidate Queue 的 CPU 在失效消息入队后立即确认。CPU 在准备发送与某缓存行相关的 MESI 消息时，必须先检查 Invalidate Queue——若已有对应条目，必须等待该条目处理完毕。入队本质上是 CPU 的承诺：在发送与该缓存行相关的后续 MESI 消息之前，先处理队列中的对应条目。

在争用不高的场景下，CPU 很少受此承诺影响。但 Invalidate Queue 为内存乱序提供了新的机会。

### 3、失效队列与内存屏障

Invalidate Queue 引入了新的可见性窗口：CPU 已返回 ACK（对发送方承诺已失效），但在**真正处理队列中的失效消息之前**，本地缓存行仍然有效，仍可读到旧值。

```
初始状态: a = 0, b = 0
a 在 CPU 0 和 CPU 1 均为 S 状态
b 在 CPU 0 为 E 状态

CPU 0 执行 foo():            CPU 1 执行 bar():
    a = 1;                       while (b == 0) continue;
    smp_mb();                    assert(a == 1);
    b = 1;
```

可能的执行序列：

1. CPU 0 执行 `a = 1`，`a` 为 S → 存入 Store Buffer，发送 Invalidate
2. CPU 1 执行 `while (b == 0)`，`b` 不在缓存 → 发送 Read
3. CPU 1 收到 Invalidate → **放入 Invalidate Queue，立即返回 ACK**。`a` 旧值仍留在缓存中
4. CPU 0 收到 ACK → 将 `a=1` 从 Store Buffer 刷入缓存（M），`smp_mb()` 完成
5. CPU 0 执行 `b = 1`，`b` 为 E → **直接写入缓存**
6. CPU 0 收到 Read → 返回 `b=1`
7. CPU 1 收到 `b=1` → 退出循环
8. CPU 1 执行 `assert(a == 1)`，`a` 仍在缓存中为 S 状态（**Invalidate Queue 尚未处理**）→ 读到旧值 0，**断言失败**
9. CPU 1 处理 Invalidate Queue → 将 `a` 置为 I，但为时已晚

写屏障 `smp_mb()` 只管住了**写方的 Store Buffer**，管不了**读方的 Invalidate Queue**。

与写屏障对称，CPU 提供**读屏障** `smp_rmb()`：执行时标记 Invalidate Queue 中所有当前条目，屏障后的加载操作必须等待所有标记条目处理完毕。修改后的代码：

```
CPU 0 执行 foo():            CPU 1 执行 bar():
    a = 1;                       while (b == 0) continue;
    smp_wmb();                   smp_rmb();
    b = 1;                       assert(a == 1);
```

延续上节的执行序列，CPU 1 执行 `smp_rmb()` 时先清空 Invalidate Queue → `a` 的缓存行置为 I。后续 `assert(a == 1)` 发生缓存未命中 → 从 CPU 0 获取 `a=1` → 断言通过。

## 五、读写内存屏障概述

写屏障 `smp_wmb()` 只标记 Store Buffer，读屏障 `smp_rmb()` 只标记 Invalidate Queue。`foo()` 无需操作 Invalidate Queue，`bar()` 无需操作 Store Buffer——分离屏障避免了不必要的开销。

| 屏障类型 | Linux 函数 | 作用对象 | 保证 |
|----------|-----------|---------|------|
| 写屏障 | `smp_wmb()` | Store Buffer | 屏障前的写操作先于屏障后的写操作对其他 CPU 可见 |
| 读屏障 | `smp_rmb()` | Invalidate Queue | 屏障前的读操作先于屏障后的读操作获取最新值 |
| 全屏障 | `smp_mb()` | Store Buffer + Invalidate Queue | 同时具备写屏障和读屏障的效果 |

写屏障只对执行它的 CPU 上的写操作排序——屏障前的写操作先于屏障后的写操作被所有 CPU 看到。读屏障只对执行它的 CPU 上的读操作排序。全屏障同时排序读写操作。

从纯 MESI 到完整的内存屏障体系，硬件与软件的协作沿以下路径演进：

1. **纯 MESI** → 同步等待导致流水线阻塞，性能不可接受
2. **引入 Store Buffer / Invalidate Queue** → 异步化换取性能，代价是打破多核间的写入顺序和读取可见性
3. **引入内存屏障指令** → 软件在关键节点显式清空 Store Buffer 和 Invalidate Queue，强制恢复 MESI 的一致性语义

Store Buffer 和 Invalidate Queue 以"对内自洽、对外异步"的策略提升单核性能。内存屏障是硬件暴露给软件的一致性开关——它不改变底层机制，而是在关键节点关闭异步优化，换取多核间的数据安全。

回顾全文，两个层面的保证需要区分：

**缓存一致性**由 MESI 协议保证——同一地址不会被多个缓存持有矛盾值。Store Buffer 与 Invalidate Queue 提升了性能，代价是 MESI 的保证退化为异步弱一致性：每个地址最终一致，但跨地址的操作顺序无法保证。

**内存一致性**（内存模型）约束多地址间的操作可见顺序，是程序员在多核编程中真正需要的保证。MESI 协议不提供此保证，须由软件通过内存屏障显式恢复。

内存屏障确保的是内存一致性，但其实现机制落在缓存一致性的层面——写屏障操作 Store Buffer，读屏障操作 Invalidate Queue。本质上，内存屏障是软件通过 MESI 级别的结构手动强制同步，换取多核间的内存顺序保证。由此可得一个推论：内存屏障的性能开销是 cache 级别的——它将 Store Buffer 与 Invalidate Queue 费心隐藏的跨核通信延迟重新暴露出来，代价等于屏障所针对的异步优化原本要隐藏的开销。
