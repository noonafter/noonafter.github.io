---
layout: article
title: C++ RAII 的边界：从资源所有权到 Qt 线程的有序关闭
date: 2025-04-08 00:00:00 +0800
tags:
  - cpp/basic
  - raii
  - qt
  - thread
---

C++ 的 RAII 可以自动管理许多资源，但线程、外部 SDK 和业务状态仍然需要明确的关闭顺序。本文从 Rule of 3/5/0 出发，区分对象销毁、资源释放和运行时关闭，并用一个简化的 Qt 示例说明 `QThread`、`deleteLater()` 与线程内 SDK 清理之间的关系。

<!--more-->

## 一、先区分三种生命周期语义

C++ 资源管理经常被概括为“构造时获取资源，析构时释放资源”。这句话描述了 RAII 的核心，但在涉及线程、外部 SDK 和业务状态时还不够完整。实际设计中至少要区分三件事：

1. **对象销毁**：C++ 对象离开作用域或被 `delete`，析构函数和成员析构函数开始执行。
2. **资源释放**：关闭文件、释放句柄、断开数据库连接、释放内存等。
3. **运行时关闭**：停止任务、通知其他线程、刷新队列、发送协议状态、等待回调结束。

对象销毁可能触发一部分资源释放，但不一定包含完整的运行时关闭流程。反过来，运行时关闭也不一定马上销毁对象。例如一个服务可以先进入停止状态，之后仍被保留用于读取状态或重新启动。

### 1、RAII 解决什么问题

RAII 把资源的最终释放绑定到拥有者对象的生命周期，从而覆盖异常和提前返回路径：

```cpp
{
    std::ofstream file("result.txt");
    file << "data";
} // file 析构，文件自动关闭
```

锁守卫、`std::unique_ptr`、容器、文件流和许多系统句柄包装类都采用这一模式。调用者不需要在每个 `return` 前重复写清理代码。

但 RAII 不能替调用者决定所有业务策略。数据库关闭前是否必须刷新缓存、网络连接是立即断开还是等待发送完成、硬件采集是否允许丢弃当前帧，这些都需要由更高层的接口明确决定。

### 2、`stop()`、`shutdown()` 和析构函数的职责

一个常见的生命周期接口可以写成：

```cpp
class Service {
public:
    bool start();
    void stop();              // 运行期间主动关闭
    ~Service() noexcept;     // 对象销毁时的最终清理
};
```

`stop()` 或 `shutdown()` 通常负责可观察的关闭协议：停止定时器、取消任务、刷新数据、在指定线程关闭 SDK，并等待相关线程结束。析构函数负责释放对象本身及其 RAII 成员，也可以调用一个幂等且不抛异常的 `stopNoexcept()` 作为最后保障。

析构函数不适合作为完整关闭流程的唯一入口，原因包括：

- 不能方便地把失败原因返回给调用者；
- 析构函数通常必须满足 `noexcept`，不适合传播设备或网络错误；
- 关闭动作可能要求在特定线程执行；
- 等待其他线程可能长时间阻塞，甚至形成死锁；
- 关闭过程可能依赖仍然存活的协调对象。

因此，问题不是“关闭动作能不能写进析构函数”，而是“资源是否在对象销毁前，以满足所有权、线程和业务约束的方式被关闭”。

## 二、Rule of 3/5/0：析构函数与拷贝控制

### 1、Rule of 3：管理裸资源时一起审查三个函数

如果一个类直接拥有裸指针、文件描述符或其他需要手工释放的资源，通常要一起审查：

- 析构函数；
- 拷贝构造函数；
- 拷贝赋值运算符。

例如下面的类只有析构函数：

```cpp
class Buffer {
public:
    explicit Buffer(std::size_t size)
        : data_(new char[size]), size_(size) {}

    ~Buffer() { delete[] data_; }

private:
    char* data_;
    std::size_t size_;
};
```

编译器仍可能生成按成员复制的拷贝构造函数。于是：

```cpp
Buffer first(1024);
Buffer second = first; // 两个对象指向同一块内存
```

两个析构函数会释放同一地址，产生双重释放。解决方案有两种：为类实现真正的深拷贝，或者明确禁止拷贝。

### 2、Rule of 5：移动语义带来另外两个函数

C++11 增加了移动构造和移动赋值。资源拥有类如果需要自定义析构、拷贝或移动中的任意一个，就要审查五个特殊成员函数：

```cpp
class FileHandle {
public:
    FileHandle(const FileHandle&) = delete;
    FileHandle& operator=(const FileHandle&) = delete;

    FileHandle(FileHandle&& other) noexcept
        : fd_(std::exchange(other.fd_, invalid_fd)) {}

    FileHandle& operator=(FileHandle&& other) noexcept {
        if (this != &other) {
            close_if_needed();
            fd_ = std::exchange(other.fd_, invalid_fd);
        }
        return *this;
    }

    ~FileHandle() { close_if_needed(); }

private:
    static constexpr int invalid_fd = -1;
    int fd_ = invalid_fd;

    void close_if_needed() noexcept {
        if (fd_ != invalid_fd) {
            close(fd_);
            fd_ = invalid_fd;
        }
    }
};
```

这个类型选择独占资源，因此禁止拷贝、支持移动。移动后源对象仍然有效，但不再拥有文件描述符。

需要注意一个语言规则：**用户声明析构函数通常会抑制隐式移动构造和隐式移动赋值，但不会自动禁止拷贝**。因此“这个类实际上不会被拷贝”不能只写在注释或设计文档中，应使用 `= delete`，或让成员类型自然删除拷贝操作。

### 3、Rule of 0：把资源交给已有 RAII 类型

现代 C++ 更希望业务类不直接管理裸资源，而是组合已经完成资源管理的成员：

```cpp
class Session {
private:
    std::unique_ptr<Device> device_;
    std::vector<std::byte> buffer_;
};
```

`unique_ptr` 负责释放设备对象，`vector` 负责释放缓冲区，`Session` 不需要手写析构、拷贝或移动操作。这就是 Rule of 0 的目标。

Rule of 0 并不要求整个程序完全没有自定义析构。底层资源封装、需要在特定线程关闭的对象，以及持有前置声明类型的 PImpl 类，仍可能需要显式析构。关键是让每个析构函数承担清晰且必要的责任。

### 4、QObject 的不可拷贝边界

`QObject` 通过 `Q_DISABLE_COPY` 禁止拷贝构造和拷贝赋值。一个 QObject 具有父子关系、信号槽连接、线程亲和性、定时器和外部观察者，复制一块内存并不能复制这些关系。

```cpp
class Controller : public QObject {
    Q_OBJECT
    Q_DISABLE_COPY(Controller)
};
```

这解决了“对象是否允许复制”的问题，但不等于解决了线程退出、SDK 关闭和数据库刷新。**不可拷贝性是类型约束，RAII 是资源释放策略，`stop()` 是运行时关闭协议**，三者关注点不同。

## 三、哪些清理由析构自动完成

### 1、QObject 父子关系和 `QTimer`

如果定时器这样创建：

```cpp
heartbeatTimer_ = new QTimer(this);
```

那么定时器属于当前 QObject。父对象析构时，Qt 会销毁子对象；`QTimer` 析构时也会停止定时器。因此仅为了防止泄漏，通常不需要再写：

```cpp
~Reporter() {
    heartbeatTimer_->stop();
}
```

但是“最终销毁时自动停止”和“服务进入关闭状态时立即停止”不是同一个语义。如果 `Reporter` 在调用 `Service::stop()` 后还会继续存活，就仍然需要显式的 `stopReporting()`。

### 2、`deleteLater()` 能做什么

```cpp
connect(thread, &QThread::finished,
        worker, &QObject::deleteLater);
```

这条连接安排 `worker` 在合适的 Qt 时机执行析构。析构会销毁 QObject 子对象、析构成员并断开信号连接。

`deleteLater()` 不会根据类名猜测业务动作，因此不会自动调用：

```cpp
worker->stopTask();
worker->flush();
worker->shutdownSdk();
```

如果外部 SDK 要求先执行 `stop()` 再执行 `release()`，只调用 `deleteLater()` 可能导致 SDK 仍在运行，或在错误的线程中释放句柄。对象销毁时机和外部资源关闭协议必须分别设计。

### 3、必须在销毁前完成的动作

有些动作不一定“必须由析构函数直接调用”，但必须在对象销毁前完成：

| 动作 | 需要显式关闭的原因 | 只依赖析构的后果 |
| --- | --- | --- |
| 停止业务定时器 | `stop()` 后对象可能继续存活 | 继续发送心跳或状态 |
| 关闭数据库并刷新队列 | 需要决定提交、丢弃和错误处理 | 数据未写完或连接残留 |
| 在指定线程关闭 SDK | 外部库规定调用线程和顺序 | 未定义行为、设备仍占用或关闭失败 |
| 停止 worker | 需要取消任务、结束回调 | 线程仍可能访问共享数据 |
| 退出并等待线程 | 确认执行线程已不再访问对象 | `QThread` 被销毁时仍在运行 |

这些动作可以由显式 `stop()` 完成，也可以由析构函数调用一个已经定义好的关闭函数完成。区别在于，显式接口让调用方能够处理返回值、选择超时策略和决定何时关闭；析构函数只能执行最后的、不可失败或失败后只能记录日志的步骤。

## 四、QThread 为什么不自动 `quit()` 和 `wait()`

### 1、QThread 对象不是执行代码的线程

`QThread` 是一个 QObject 控制对象。调用 `start()` 后，Qt 创建并运行一个原生线程；`QThread` 对象本身通常仍然属于创建它的线程。默认的 `run()` 会运行线程事件循环。`QThread` 负责管理原生线程，但析构函数不会替上层决定或执行关闭策略。

因此有两个相关但不同的生命周期：

```text
QThread C++ 对象：创建、发出控制请求、最终析构
原生执行线程：启动、执行 run()、结束并由 wait() 确认
```

销毁 `QThread` 对象不会安全地终止仍在运行的原生线程。Qt 会在这种情况下报告 `QThread: Destroyed while thread is still running`，因为继续运行的线程可能访问已经失效的对象或其他共享状态。

### 2、`quit()`、`wait()` 和中断请求

- `quit()` 请求线程事件循环退出。如果线程没有运行事件循环，或者代码长时间占用线程而不返回事件循环，`quit()` 不能强制终止这段代码。
- `requestInterruption()` 只设置一个协作式中断请求，业务代码必须主动检查 `isInterruptionRequested()`。
- `wait()` 等待原生线程真正结束，相当于线程生命周期的 join。

Qt 无法在通用的 `QThread` 析构函数中自动选择关闭策略：自动 `wait()` 可能让 UI 线程无限阻塞；自动强制终止可能破坏锁、文件写入和外部 SDK 状态；自动 `quit()` 对没有事件循环的线程没有效果。因此 Qt 把顺序留给上层对象设计。

### 3、与 `std::thread` 和 `std::jthread` 对照

| 类型 | 析构时仍有关联线程 | 停止机制 |
| --- | --- | --- |
| `std::thread` | 调用 `std::terminate()` | 调用方自行选择 `join()` 或 `detach()` |
| `std::jthread` | 请求停止后自动 `join()` | `std::stop_token` 协作式停止 |
| `QThread` | 报告线程仍在运行的错误 | 调用方组合 `requestInterruption()`、`quit()` 和 `wait()` |

`std::jthread` 减少了忘记 `join()` 的风险，但没有替任务设计退出点。如果线程一直执行普通 `sleep_for()`、死循环或不可中断的阻塞 I/O，析构中的 `join()` 仍会等待很久甚至永久等待。

可中断等待需要任务主动配合，例如：

```cpp
std::jthread worker([](std::stop_token token) {
    std::mutex mutex;
    std::condition_variable_any condition;
    std::unique_lock lock(mutex);

    condition.wait_for(lock, token, std::chrono::seconds(10), [&] {
        return token.stop_requested();
    });

    // 收到停止请求或超时后，执行有限且明确的清理工作
});
```

`stop_token` 是通知，不是强制中断。写线程任务时就必须决定检查停止请求的时机，以及如何唤醒阻塞操作。

## 五、一个简化的 Qt 线程资源示例

下面的例子模拟一个约束明确的外部 SDK：句柄必须在创建它的线程中调用 `close()`，析构函数不会替代这个关闭协议。示例只保留线程生命周期相关代码，便于观察顺序。

### 1、需求和所有权关系

```text
DeviceRuntime（创建于主线程）
 ├── QThread（控制对象，父对象是 Runtime）
 └── DeviceWorker（移动到管理线程）
      ├── QTimer（worker 的子对象）
      └── SdkHandle（在管理线程创建和关闭）
```

`DeviceRuntime` 拥有 `QThread` 和 worker 的生命周期；worker 负责在自己的线程中使用 SDK。主线程不能直接调用 worker 的普通成员函数，因为那会绕过 Qt 的线程调度。

### 2、一个要求线程内关闭的 SDK 句柄

```cpp
class SdkHandle {
public:
    void open() {
        owner_ = QThread::currentThread();
        opened_ = true;
    }

    void close() {
        Q_ASSERT(owner_ == QThread::currentThread());
        opened_ = false;
    }

private:
    QThread* owner_ = nullptr;
    bool opened_ = false;
};
```

真实 SDK 的句柄通常由厂商 API 创建和释放。这里用 `Q_ASSERT` 表示“关闭必须发生在创建线程”的约束。

### 3、worker：在所属线程执行开始和关闭

```cpp
class DeviceWorker final : public QObject {
    Q_OBJECT

public slots:
    void startDevice() {
        if (handle_ || timer_) {
            return;
        }

        handle_ = std::make_unique<SdkHandle>();
        handle_->open();
        timer_ = new QTimer(this);
        timer_->start(100);
    }

    void stopDevice() {
        if (stopped_) {
            return;
        }

        if (timer_) {
            timer_->stop();
        }
        if (handle_) {
            handle_->close();
            handle_.reset();
        }
        stopped_ = true;
    }

private:
    QTimer* timer_ = nullptr;
    std::unique_ptr<SdkHandle> handle_;
    bool stopped_ = false;
};
```

`QTimer` 是 worker 的子对象，worker 析构时会自动销毁它。SDK 句柄的内存由 `unique_ptr` 管理，但业务关闭仍由 `stopDevice()` 明确完成，并且调用发生在 worker 所属线程。

### 4、runtime：先关闭业务，再退出线程

```cpp
class DeviceRuntime final : public QObject {
    Q_OBJECT
    Q_DISABLE_COPY(DeviceRuntime)

public:
    explicit DeviceRuntime(QObject* parent = nullptr)
        : QObject(parent), thread_(new QThread(this)) {}

    ~DeviceRuntime() override {
        stop();
    }

    void start() {
        if (started_) {
            return;
        }

        worker_ = new DeviceWorker;
        worker_->moveToThread(thread_);
        connect(thread_, &QThread::finished,
                worker_, &QObject::deleteLater);

        started_ = true;
        thread_->start();
        QMetaObject::invokeMethod(worker_, "startDevice",
                                  Qt::BlockingQueuedConnection);
    }

    void stop() {
        if (!started_ || stopped_) {
            return;
        }

        // 在 worker 所属线程关闭 SDK 和定时器。
        QMetaObject::invokeMethod(worker_, "stopDevice",
                                  Qt::BlockingQueuedConnection);

        // stopDevice 返回后，worker 不再使用 SDK；此时退出事件循环。
        thread_->quit();
        thread_->wait();
        stopped_ = true;
    }

private:
    QThread* thread_;
    DeviceWorker* worker_ = nullptr;
    bool started_ = false;
    bool stopped_ = false;
};
```

关闭顺序是：

1. 通过 `BlockingQueuedConnection` 把 `stopDevice()` 投递到 worker 线程，并等待它完成；
2. worker 停止定时器、关闭并释放 SDK 句柄；
3. 调用 `quit()` 请求事件循环退出；
4. 调用 `wait()` 确认原生线程已经结束；
5. `finished` 信号触发 `worker->deleteLater()`，完成 QObject 的销毁。

如果只执行 `thread_->quit()` 和 `thread_->wait()`，线程可能确实结束，但 SDK 的业务关闭动作没有执行。若 SDK 析构函数也不负责释放外部连接，句柄会泄漏；若 SDK 析构要求特定线程，则在错误线程释放还可能产生未定义行为。`deleteLater()` 只解决第 5 步，不能替代第 1、2 步。

### 5、什么时候析构函数不需要调用 `stop()`

如果上层拥有明确的关闭协议：

```cpp
int main(int argc, char** argv) {
    QCoreApplication app(argc, argv);
    DeviceRuntime runtime;
    runtime.start();

    const int result = app.exec();
    runtime.stop();
    return result;
}
```

并且所有异常和提前返回路径都能保证执行 `runtime.stop()`，析构函数可以只依赖成员析构和 Qt 的父子关系。此时 `stop()` 是主关闭入口，析构函数不必重复完整流程。

但这种约定必须覆盖所有退出路径。当前示例中如果 `main()` 直接让 `runtime` 离开作用域，而没有调用 `stop()`，那么析构函数调用 `stop()` 就是保证线程和 SDK 正确关闭的唯一入口。保留一个幂等的析构兜底，通常比依赖每个调用方都记住关闭顺序更可靠。

为保持示例重点，`DeviceRuntime` 只演示一次启动和一次关闭；实际可重启的组件还需要在 worker 删除完成后重新创建 worker，并处理启动失败、关闭超时和重复调用等状态。

### 6、常见错误顺序

下面的顺序存在风险：

```cpp
thread_->quit();
thread_->wait();
// 线程已经结束后才尝试调用 worker->stopDevice()
```

`stopDevice()` 是 worker 的槽函数，需要事件循环调度；事件循环已经退出后，调用可能永远无法完成。另一个错误是从 worker 自己的线程调用 `wait()`，这会等待自身结束并导致死锁。关闭接口应明确调用线程，并对跨线程调用增加断言或封装。

## 六、从项目代码审查资源生命周期

### 1、需要显式关闭或自定义析构的情况

- 服务拥有多个工作线程，必须按业务顺序停止 worker、关闭外部设备并等待线程；
- SDK 的 `stop`、`release` 规定调用线程或调用顺序；
- 数据库 worker 需要刷新队列并移除命名连接；
- 容器保存不带 QObject 父对象的裸指针，例如 `QList<StreamState*>`；
- 资源类需要表达独占所有权，必须删除拷贝并实现移动或显式禁止移动。

这些场景中，自定义析构有实际理由，但仍应把正常关闭放在公开的 `stop()` 或 `shutdown()` 中，让析构只做最后保障。

### 2、可以默认析构的情况

- 成员全部由 `unique_ptr`、容器、锁守卫或其他 RAII 类型管理；
- QObject 子对象已经建立了正确的父子关系；
- 析构函数只重复 Qt 自动完成的信号断开、定时器停止或空操作；
- 类没有拥有资源，也不需要在线程或业务状态之间协调。

例如，`FpgaSourceManager` 如果析构函数只负责断开 QObject 自身相关的连接，通常可以改为 `~FpgaSourceManager() = default`。这不会影响运行期的 `stopSource()`；运行期关闭和最终销毁仍然是两种不同操作。

### 3、一个实用检查顺序

审查一个类时，可以依次回答：

1. 这个类真正拥有哪一些资源？哪些只是借用的观察指针？
2. 每个资源由谁释放？释放动作是否已经被 RAII 成员或父子关系覆盖？
3. 资源关闭是否要求特定线程、事件循环或其他对象仍然存在？
4. 关闭失败、超时和未处理队列由谁决定？析构函数是否能够表达这些结果？
5. 对象是否允许拷贝和移动？如果不允许，是否由 `Q_DISABLE_COPY`、`= delete` 或成员类型强制保证？
6. 线程是否在 `QThread` 对象销毁前完成退出和等待？
7. `deleteLater()` 是否只承担对象销毁，业务关闭是否已经单独完成？
8. 自定义析构是否改变了隐式移动能力，是否需要补充 `noexcept` 的移动操作？

这组问题能把“析构函数是不是多余”转换成更具体的判断：它是否承担了 Qt 或成员类型无法自动完成的责任，且这个责任是否必须在对象销毁前完成。

## 结论

**Rule of 0 是优先目标，但不是“禁止自定义析构”。** 使用 RAII 成员可以自动完成普通资源释放；QObject 的父子关系可以自动销毁子对象；`deleteLater()` 可以安排线程安全的对象析构。但线程退出、外部 SDK 关闭、数据库刷新和业务状态转换仍然需要明确的运行时接口。

设计资源生命周期时，至少要同时检查三个边界：

- **所有权边界**：谁负责销毁对象和句柄；
- **线程边界**：在哪个线程创建、使用和关闭资源；
- **业务边界**：关闭时是刷新、等待、丢弃还是报告失败。

理想的调用方只需要面对少量稳定的生命周期操作：底层资源尽量使用 RAII，线程和设备由运行时对象管理，业务关闭通过 `stop()` 或 `shutdown()` 表达，析构函数只负责释放已经满足关闭条件的对象并提供幂等兜底。
