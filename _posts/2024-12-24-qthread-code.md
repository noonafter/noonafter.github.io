---
title:【Qt源码分析】QThread类
tags: qt thread
---


本文基于 Qt 5.14.2 源码，主要分析 `QThread` 的实现原理。Qt 关于线程的源码位于 `Qt5.14.2\5.14.2\Src\qtbase\src\corelib\thread` 目录下。

核心代码文件包括：
*   **`qthread.h`**: 定义 `QThread` 公开接口。
*   **`qthread_p.h`**: 定义 `QThreadPrivate` 和 `QThreadData`，采用 Pimpl（Pointer to Implementation）模式，封装实现细节。
*   **`qthread.cpp`**: 实现平台无关的通用逻辑。
*   **`qthread_win.cpp`** & **`qthread_unix.cpp`**: 分别实现 Windows 和 Unix 平台特定的系统调用。

本文将以 Windows 平台下的实现（`qthread_win.cpp`）为例，剖析 `QThread::start()` 的底层机制。

## 1. 核心类结构概览

### QThread (qthread.h)
`QThread` 是一个管理线程的 C++ 类。
**关键概念**：`QThread` 对象本身（例如在 `main` 函数中 `new` 出来的对象）并不存在于新创建的子线程中，而是属于创建该对象的线程（通常是主线程）。它只是一个控制器，用于管理底层操作系统线程的生命周期（创建、启动、等待、销毁）。

### QThreadPrivate & QThreadData (qthread_p.h)
*   **QThreadPrivate**：采用 Pimpl 模式，隐藏了 `QThread` 的私有成员变量，如线程句柄、线程 ID、运行状态标志等。
*   **QThreadData**：存储线程相关的数据，包括线程局部存储（TLS）、事件循环派发器等。这两个类不直接面向用户，是 Qt 内部实现线程调用的基石。

## 2. QThread::start() 源码分析

`start()` 函数的作用是启动一个新的线程，该线程将执行 `run()` 函数。

以下是 `qthread_win.cpp` 中 `start()` 函数的源码及详细解析：

```cpp
void QThread::start(Priority priority)
{
    // 1. 获取 d 指针
    // Q_D 宏展开为：QThreadPrivate * const d = d_func();
    // 用于快速访问 QThread 的私有数据成员。
    Q_D(QThread);

    // 2. 加锁保护
    // 使用 QMutexLocker 对互斥量 d->mutex 进行加锁。
    // 利用 RAII 机制，在函数退出栈自动解锁。这保证了多线程环境下对线程状态操作的原子性，
    // 防止在启动线程的过程中，其他线程（如调用 wait()）同时修改状态导致竞争条件。
    QMutexLocker locker(&d->mutex);

    // 3. 检查并等待结束状态
    // 如果线程正处于“正在结束”阶段（isInFinish 为真），
    // 此时需要暂时解锁并调用 wait()，直到线程完全结束，然后重新加锁。
    // 这是为了防止重入启动同一个正在清理资源的线程。
    if (d->isInFinish) {
        locker.unlock();
        wait();
        locker.relock();
    }

    // 4. 检查运行状态
    // 如果线程已经在运行，直接返回，避免重复启动。
    if (d->running)
        return;

    // 5. 初始化线程状态标志
    d->running = true;
    d->finished = false;
    d->exited = false;
    d->returnCode = 0;
    d->interruptionRequested = false;

    /*
      NOTE: we create the thread in the suspended state, set the
      priority and then resume the thread.

      since threads are created with normal priority by default, we
      could get into a case where a thread (with priority less than
      NormalPriority) tries to create a new thread (also with priority
      less than NormalPriority), but the newly created thread preempts
      its 'parent' and runs at normal priority.
    */
    // 6. 创建底层系统线程（挂起状态）
    // 解释：为什么使用 CREATE_SUSPENDED？
    // Windows API 创建线程时，默认优先级通常是 NormalPriority。
    // 如果我们要创建一个低优先级线程，直接创建可能会导致它以 NormalPriority 抢占父线程。
    // 因此，先以挂起状态创建，设置好正确的优先级后，再唤醒。
  
    // 6.1 选择线程创建 API
    // 如果是 MSVC 编译器且使用静态链接 CRT (-MT/-MTd)，则使用 _beginthreadex。
    // 否则（动态链接 CRT -MD/-MDd 或 MinGW），使用 CreateThread。
    // 使用 _beginthreadex 是为了确保 C 运行时库（CRT）的线程局部数据被正确初始化。
#if defined(Q_CC_MSVC) && !defined(_DLL)
    // ... (省略 WINRT 特殊处理代码)
    d->handle = (Qt::HANDLE) _beginthreadex(NULL, d->stackSize, QThreadPrivate::start,
                                            this, CREATE_SUSPENDED, &(d->id));
#else
    // MSVC -MD or -MDd or MinGW build
    d->handle = CreateThread(nullptr, d->stackSize,
                             (LPTHREAD_START_ROUTINE)QThreadPrivate::start,
                             this, CREATE_SUSPENDED, (LPDWORD)&d->id);
#endif 

    // 7. 错误处理
    if (!d->handle) {
        qErrnoWarning("QThread::start: Failed to create thread");
        d->running = false;
        d->finished = true;
        return;
    }

    // 8. 设置线程优先级
    int prio;
    d->priority = priority;
  
    // 将 Qt 的枚举优先级映射为 Windows API 的优先级常量
    switch (d->priority) {
    case IdlePriority:
        prio = THREAD_PRIORITY_IDLE;
        break;
    // ... (省略其他优先级 case)
    case InheritPriority:
    default:
        // 默认继承创建者线程（父线程）的优先级
        prio = GetThreadPriority(GetCurrentThread());
        break;
    }

    if (!SetThreadPriority(d->handle, prio)) {
        qErrnoWarning("QThread::start: Failed to set thread priority");
    }

    // 9. 唤醒线程
    // 线程设置完毕，正式唤醒，此时操作系统开始调度该线程执行入口函数 QThreadPrivate::start。
    if (ResumeThread(d->handle) == (DWORD) -1) {
        qErrnoWarning("QThread::start: Failed to resume new thread");
    }
}
```

### 2.1 补充分析：QThreadPrivate::start

`start()` 函数虽然设置了参数并唤醒了线程，但真正的线程入口函数是静态方法 `QThreadPrivate::start`。这是一个 C 风格的回调函数，由操作系统直接调用。它的核心作用是**连接操作系统线程与 Qt 的 C++ 对象世界**。其逻辑伪代码如下：

```cpp
// 伪代码演示 QThreadPrivate::start 的逻辑
unsigned int __stdcall QThreadPrivate::start(void *arg)
{
    // 1. 获取 QThread 对象指针（即 this 指针）
    QThread *thr = reinterpret_cast<QThread *>(arg);

    // 2. 设置线程特定数据（TLS）
    // 将当前系统线程 ID 与 QThread 对象关联，使得 QThread::currentThread() 能够正确工作。
    QThreadData::setCurrent(thr->d_func()->data);

    // 3. 调用用户重写的 run()
    // 这里加 try-catch 是为了防止用户代码崩溃导致整个进程退出
    try {
        thr->run();
    } catch (...) {
        // 异常处理...
    }

    // 4. 清理与结束
    // 标记线程完成
    thr->d_func()->running = false;
    thr->d_func()->finished = true;
  
    // 发送 finished 信号
    emit thr->finished();

    // 5. 线程结束
    return 0;
}
```

## 3. 总结

通过分析 `QThread::start` 在 Windows 平台的实现，我们可以清晰地看到 Qt 封装底层系统调用的策略：

1.  **状态保护**：利用 `QMutex` 确保多线程操作下的状态一致性（如防止重复启动）。
2.  **API 选择**：根据编译环境和 CRT 链接方式，智能选择 `_beginthreadex` 或 `CreateThread`，确保线程安全。
3.  **优先级控制**：采用“先挂起、设置优先级、再唤醒”的策略，完美解决了新创建线程可能以错误优先级抢占父线程的潜在并发问题。
4.  **入口转发**：`start` 函数并不执行具体任务，它只负责启动系统线程，系统线程随即调用静态入口 `QThreadPrivate::start`，后者最终调用用户的虚函数 `run()`。

简而言之，`QThread::start` 完成了从 C++ 对象指令到操作系统线程创建的映射，是 Qt 跨平台线程模型的关键一环。