---
layout: article
title: 同步/异步、阻塞/非阻塞：概念分析
date: 2025-05-20 10:00:00 +0800
tags:
  - async
  - os
  - thread
---


同步/异步、阻塞/非阻塞是编程中常被混淆的两组概念。本文通过文件读取示例，阐明这两组概念的区别及其组合应用。

## 一、核心概念定义

### 1、同步与异步

**关注点**：任务/逻辑控制流的执行流程。

**同步（Synchronous）**：任务按顺序执行。任务A在启动任务B后，需要等待任务B完成（A需要B的执行结果），才能进行下一步的操作。

> 同步并没有规定等待期间任务A不能进行活动，只是规定了**任务A的下一步操作**与任务B之间的执行顺序。

**异步（Asynchronous）**：任务可以同时或独立执行。任务A在启动任务B后，会继续执行自身，而无需等待任务B完成。任务B完成时通过回调、信号等机制通知任务A。

> 任务A后续所有的工作与任务B都没有明确的时间顺序(次序)关系

![sync_async](https://noonafter.cn/assets/images/posts/2025-05-20-sync-async-blocking-concepts/sync_async.png)

### 2、阻塞与非阻塞

**关注点**：调用者（caller）在函数调用期间的状态。

**阻塞（Blocking）**：函数调用时，调用者失去控制权并等待被调用者（callee）完成。在此期间无法执行其他任务。

**非阻塞（Non-blocking）**：函数调用后，调用者立即恢复控制权，可以执行其他任务，无需等待。

## 二、四种组合模式

从上一节定义中可以发现，同步/异步关注的是任务的顺序（针对任务流程，并不关心某个具体函数）。阻塞/非阻塞关注的是函数调用瞬间的调用者的状态（针对某个具体的函数对象，不关心流程之间的关系）

那么，当有一个函数，他的作用就是在任务A中启动一个任务B时，就会同时涉及到这两个问题，从而导致这个函数有4种不同的组合模式：**同步阻塞，同步非阻塞，异步阻塞，异步非阻塞**。

广义来讲，每个函数都可以认为是一个子任务，因此，每个函数都可以按照这个方法来分类：即**每次具体的函数调用都属于这四类之一**，但同一个函数在不同上下文中可能属于不同类型（不同参数或状态下，同一个函数可能启动了不同的任务）。对于大多数函数，类型是确定的。

### 1、同步阻塞

同步阻塞是最常见的函数调用方式。调用函数后，程序等待任务完成（期间调用者失去控制权），然后按顺序执行下一步代码。

**适用场景**：简单脚本、顺序任务。实现直观，逻辑清晰。

**Python 示例**：

```python
def synchronous_blocking_read():
    print("Starting file read")
    with open('example.txt', 'r') as f:
        data = f.read() # 该函数在任务A中启动了任务B（读取文件数据）
    print("File read complete")
    print("Data:", data)

print("Main program starts")
synchronous_blocking_read()
print("Main program ends")
```

**输出**：

```
Main program starts
Starting file read
File read complete
Data: (文件内容)
Main program ends
```

**执行流程**：`open()` 函数打开文件，`read()` 方法读取内容。程序等待文件读取完成后才继续执行。

> 感兴趣的小伙伴，可以分析一下print函数，他也属于同步阻塞函数

### 2、同步非阻塞

同步非阻塞通常与轮询技术结合使用。调用者立即恢复控制权，但需要周期性检查任务状态。任务仍按顺序完成。

**适用场景**：难以引入异步处理的场景，需要通过轮询检查状态。

**Python 示例**：

```python
import os
import errno
import time

def synchronous_nonblocking_read():
    print("Starting file read")
    fd = os.open('example.txt', os.O_RDONLY | os.O_NONBLOCK)
    data = b''
    while True:
        try:
            chunk = os.read(fd, 1024)
            if not chunk:
                break
            data += chunk
        except BlockingIOError as e:
            if e.errno in (errno.EAGAIN, errno.EWOULDBLOCK):
                print("Waiting for data...")
                time.sleep(0.1)
                continue
            else:
                raise
    os.close(fd)
    print("File read complete")
    print("Data:", data.decode())

print("Main program starts")
synchronous_nonblocking_read()
print("Main program ends")
```

**输出**：

```
Main program starts
Starting file read
Waiting for data...
Waiting for data...
File read complete
Data: (文件内容)
Main program ends
```

**执行流程**：`os.open()` 以非阻塞模式打开文件。`os.read()` 尝试读取数据，若数据未就绪则抛出 `BlockingIOError`。异常处理器检查错误码，短暂等待后重试。文件读取完成后退出循环。

**注意**：`BlockingIOError` 在常规文件系统中可能不会触发，此示例主要用于说明非阻塞 I/O 的轮询模式。该模式更常用于套接字和管道等 I/O 流。

### 3、异步阻塞

异步调用任务，但等待任务完成。异步表示任务A和任务B之间没有顺序要求，阻塞表示任务A启动任务B后，停下来等待任务B结束。

这种方式未能利用异步处理的优势，效率低下，实际应用中罕见。

### 4、异步非阻塞

任务异步调用，调用者立即恢复控制权执行其他任务。任务完成时通过回调或事件通知调用者。这种方式可以高效利用资源，在任务执行期间处理其他操作。

**适用场景**：大规模网络请求、I/O 密集型操作。通过高效利用资源提升性能。

**Python 示例**：

```python
import asyncio
import aiofiles

async def asynchronous_nonblocking_read():
    print("Starting file read")
    async with aiofiles.open('example.txt', 'r') as f:
        data = await f.read()
    print("File read complete")
    print("Data:", data)

async def main():
    print("Main program starts")
    task = asyncio.create_task(asynchronous_nonblocking_read())
    print("Performing other tasks...")
    await task
    print("Main program ends")

asyncio.run(main())
```

**输出**：

```
Main program starts
Performing other tasks...
Starting file read
File read complete
Data: (文件内容)
Main program ends
```

**执行流程**：`aiofiles.open()` 异步打开文件。`await f.read()` 允许事件循环在读取文件时执行其他任务。`asyncio.create_task()` 调度任务并立即返回控制权。文件读取期间，程序可以继续执行其他操作。

## 三、概念对比

### 1、同步 vs 异步

| 维度 | 同步 | 异步 |
|------|------|------|
| 关注点 | 任务的顺序和依赖关系 |  |
| 执行方式 | 按顺序执行，等待前一任务完成 | 任务独立执行，通过通知机制返回结果 |
| 适用场景 | 任务间有依赖关系 | 任务间相互独立 |

### 2、阻塞 vs 非阻塞

| 维度 | 阻塞 | 非阻塞 |
|------|------|--------|
| 关注点 | 调用者是否失去控制权 |  |
| 执行方式 | 调用者等待任务完成 | 调用者立即恢复控制权 |
| 适用场景 | 简单顺序任务 | 需要响应性的任务 |

## 四、实践建议

**同步阻塞**：实现简单，适合顺序任务。代码逻辑清晰，易于理解和维护。

**同步非阻塞**：需要轮询检查状态，CPU 开销较大。适用于难以引入异步处理但需要一定响应性的场景。

**异步阻塞**：效率低下，实际应用中应避免。

**异步非阻塞**：性能最优，适合大规模 I/O 操作。通过高效利用资源，在任务执行期间处理其他操作，显著提升系统响应性和吞吐量。

## 五、选择指南

选择合适的模式取决于具体需求：

- 任务间有明确依赖关系且逻辑简单时，使用同步阻塞。
- 需要提升响应性但任务间仍有顺序要求时，考虑同步非阻塞。
- 任务间相互独立且需要高并发处理时，使用异步非阻塞。

理解并正确应用这些概念，可以优化程序的响应性和资源利用率。


