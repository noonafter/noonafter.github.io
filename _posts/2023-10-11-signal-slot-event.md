---
title: Qt信号槽与事件循环
tags: qt signal_slot event_loop
---
- [事件与事件循环](#事件与事件循环)
  - [事件的分类](#事件的分类)
  - [事件循环](#事件循环)
  - [退出事件循环的细节](#退出事件循环的细节)
  - [次线程中的 Spontaneous 事件](#次线程中的-spontaneous-事件)
- [信号槽机制](#信号槽机制)
  - [信号槽与事件的对比](#信号槽与事件的对比)
  - [Qt::ConnectionType 连接类型](#qtconnectiontype-连接类型)
  - [代码实例分析](#代码实例分析)
  - [运行结果与详细解析](#运行结果与详细解析)
  - [总结](#总结)
## 事件与事件循环
在Qt中，**事件**被封装为 `QEvent` 类及其子类的对象，用于表示应用程序内部或外部发生的各种动作（如鼠标点击、键盘输入、定时器超时等）。事件可以被任何 `QObject` 子类的对象接收并处理。
### 事件的分类
根据事件的创建方式和调度方式，Qt中的事件主要分为三类：
1.  **自发事件**：
    由窗口系统（如 Windows、X11）创建。例如，用户点击鼠标产生的按键事件。这些事件首先由系统截获，随后加入Qt的事件队列，等待主事件循环处理（系统将原生事件转换为 `QEvent` 实例，再分发给对应的 `QObject` 实例）。
2.  **推送事件**：
    由Qt应用程序（或框架内部）创建，并通过 `QCoreApplication::postEvent()` 加入Qt的事件队列。它们会等待事件循环的调度，按顺序处理。
3.  **发送事件**：
    由Qt应用程序创建，并通过 `QCoreApplication::sendEvent()` 直接传递给目标对象。这类事件不进入队列，而是立即调用接收者的 `event()` 函数进行处理，属于同步调用。
### 事件循环
Qt中的**事件循环**（**Event Loop**）是一个通过队列循环处理事件的机制。简单来说，当队列中有事件时，事件循环会取出并处理事件；如果队列中没有事件，事件循环会阻塞（挂起），等待新事件的到来，从而避免CPU空转。
在Qt程序中，**每个线程都可以有自己的事件循环**（每个线程同一时间只能拥有一个活动的事件循环，对应一个事件队列）。主线程（通常也是GUI线程）对应的事件循环被称为**主事件循环**。通常在 `main()` 函数末尾调用 `QCoreApplication::exec()`（或 `QApplication::exec()`）来启动主事件循环，直到调用 `exit()` 或 `quit()` 函数才会停止。
从概念上看，事件循环的逻辑类似于以下 `while` 循环：
```cpp
while (!exit_was_called) {
    // 1. 处理所有 Posted 事件
    while (!posted_event_queue_is_empty) {
        process_next_posted_event();
    }
    // 2. 处理 Spontaneous 事件（来自窗口系统）
    while (!spontaneous_event_queue_is_empty) {
        process_next_spontaneous_event();
    }
    // 3. 再次处理可能在上一步骤中产生的 Posted 事件
    while (!posted_event_queue_is_empty) {
        process_next_posted_event();
    }
}
```

事件循环首先处理队列中的 **Posted 事件**，直到队列为空；然后处理 **Spontaneous 事件**（系统将其转换为 `QEvent` 并发送给 `QObject`）；最后处理在 Spontaneous 事件处理过程中新产生的 Posted 事件。**Sent 事件不经过事件循环，直接调用接收者处理。**

关于事件的传递过程：事件循环通常将事件发送给特定的接收者对象。如果接收者没有处理该事件（即 `event()` 函数返回 `false`），事件可能会沿着对象树向上传播给父对象，直到被处理或到达顶端。

### 退出事件循环的细节

在使用事件循环时，`exec()` 用于开启，`exit()` 或 `quit()` 用于退出。

**值得注意的是**：`quit()` 或 `exit()` 函数并不会立即终止事件循环。它们仅仅是设置一个退出标志位，并将控制权返回给事件循环。当事件循环当前正在处理的事件（以及该事件触发的连锁调用）执行完毕，控制权重新回到 `exec()` 的顶层循环判断时，检测到退出标志，才会真正退出循环并返回。

### 次线程中的 Spontaneous 事件

关于 **次线程中创建的事件循环是否会处理 Spontaneous 事件**，这里给出一个明确的解释：

通常情况下，次线程的事件循环**不会**处理 Spontaneous 事件（即窗口系统事件）。

**原因**：窗口系统（如 X11 或 Windows）通常将原生事件（如鼠标移动）分发到**创建窗口的线程**。在Qt中，GUI控件（QWidget）及其子类必须在主线程（GUI线程）中使用。因此，绝大多数与用户交互相关的 Spontaneous 事件都由主线程的事件循环处理。

次线程的事件循环主要用于处理：

1.  **Posted 事件**：通过 `postEvent` 投递的事件。
2.  **跨线程的信号槽连接**：当使用 `Qt::QueuedConnection` 时，槽函数调用被封装为事件投递到接收者所在线程。

除非你在次线程中创建了原生窗口（这在标准Qt编程中极少见），否则该线程的事件循环只需要处理队列事件，无需处理 Spontaneous 事件。



## 信号槽机制

**信号槽**（**Signal-Slot**）和事件处理是Qt中两种不同的通信机制，它们都可以用于实现对象间的同步或异步通信。

### 信号槽与事件的对比

**信号槽机制**：

*   **特性**：Qt框架的核心特性，用于实现对象间的**松散耦合**通信。
*   **通信模式**：**广播**。发送者发出信号，不需要知道具体的接收者；一个信号可以连接多个槽函数。
*   **用途**：主要用于对象状态变更或特定动作发生时的通知。

**事件和事件处理**：

*   **特性**：通用的**事件驱动**编程范式，不仅限于Qt。
*   **通信模式**：**单播/定向传递**。事件通常有一个明确的目标接收者对象。
*   **用途**：主要用于处理外部输入（鼠标、键盘）或系统消息。

### Qt::ConnectionType 连接类型

使用 `connect` 连接信号与槽时，第5个参数 `Qt::ConnectionType` 决定了信号发射时的行为方式：

1.  **Qt::AutoConnection（默认值）**： Qt自动判断。如果信号发送者与接收者在同一线程，等同于 `DirectConnection`；如果在不同线程，等同于 `QueuedConnection`。
2.  **Qt::DirectConnection**： **同步**调用。当信号发射时，槽函数**立即**在信号发送者的线程中执行。无论接收者是否依附于该线程，槽函数都将在当前线程栈中运行。
3.  **Qt::QueuedConnection**： **异步**调用。当信号发射时，控制权立即返回。槽函数的调用被封装成一个事件，放入接收者所在线程的事件队列中。只有当接收者线程的事件循环取到该事件时，槽函数才会被执行。 *注：这要求接收者对象必须依附于一个拥有事件循环的线程。*
4.  **Qt::BlockingQueuedConnection**： 与 `QueuedConnection` 类似，信号会被放入队列，但**发送者线程会阻塞**，直到接收者线程的槽函数执行完毕。此连接类型**严禁**用于同一线程，否则会造成死锁。
5.  **Qt::UniqueConnection**： 这是一个标志位，可与上述类型按位或组合使用。如果相同的信号和槽（相同参数）已经存在连接，则不重复建立连接。

### 代码实例分析

下面的代码演示了事件循环的退出时机、不同连接类型的行为以及线程间交互。
```cpp

#include <QDebug>
#include <QCoreApplication>
#include <QTimer>
#include <QThread>

class Foo : public QObject {
    Q_OBJECT

public:
    Foo(QObject *parent = nullptr) : QObject(parent) {}

private:
    void doStuff() {
        qDebug() << QThread::currentThreadId() << ": Emit signal one";
        emit signal1();

        qDebug() << QThread::currentThreadId() << ": Emit signal finished";
        emit finished();

        qDebug() << QThread::currentThreadId() << ": Emit signal two";
        emit signal2();
    }

signals:
    void signal1();
    void finished();
    void signal2();

public slots:
    void slot1() {
        qDebug() << QThread::currentThreadId() << ": Execute slot one";
    }

    void slot2() {
        qDebug() << QThread::currentThreadId() << ": Execute slot two";
    }

    void start() {
        doStuff();

        qDebug() << QThread::currentThreadId() << ": Bye!";
    }
};

#include "main.moc"

int main(int argc, char **argv) {
    qDebug() << "main thread id:" << QThread::currentThreadId();
    QCoreApplication app(argc, argv);

    Foo foo;
    Foo foo2;
    QThread *foo2thread = new QThread(&app);
    
    // 将 foo2 移动到新线程 foo2thread
    foo2.moveToThread(foo2thread);
    foo2thread->start();

    // 连接 signal1 到两个槽
    // foo 和 foo 都在主线程 -> DirectConnection
    QObject::connect(&foo, &Foo::signal1, &foo, &Foo::slot1);
    // foo 在主线程，foo2 在次线程 -> AutoConnection (QueuedConnection)
    QObject::connect(&foo, &Foo::signal1, &foo2, &Foo::slot1);

    // 连接 finished 信号以退出循环
    // finished 发出时，主线程直接调用 quit（设置退出标志）
    QObject::connect(&foo, &Foo::finished, &app, &QCoreApplication::quit);
    // finished 发出时，向 foo2thread 投递 quit 事件
    QObject::connect(&foo, &Foo::finished, foo2thread, &QThread::quit);

    // 连接 signal2
    // 同线程 -> DirectConnection
    QObject::connect(&foo, &Foo::signal2, &foo, &Foo::slot2);
    // 跨线程 -> QueuedConnection
    QObject::connect(&foo, &Foo::signal2, &foo2, &Foo::slot2);

    // 定时器触发 foo 的 start 槽函数
    QTimer::singleShot(0, &foo, &Foo::start);
    
    return app.exec();
}
```

### 运行结果与详细解析

**运行结果示例：**

    <TEXT>main thread id: 0x165c0x165c : Emit signal one0x165c : Execute slot one0x165c : Emit signal finished0x5578 : Execute slot one0x165c : Emit signal two0x165c : Execute slot two0x165c : Bye!

*(注意：线程 ID 和 `0x5578` 处的打印顺序可能会因操作系统调度而略有不同，但逻辑流如下)*

**详细步骤解析：**

1.  **启动**： `foo` 在主线程，`foo2` 在次线程 `foo2thread`。`QTimer::singleShot` 将定时器超时事件投递到主事件队列。
2.  **进入事件循环**： `app.exec()` 启动。主事件循环处理定时器事件，触发 `foo.start()`。 注意：`foo.start()` 是通过事件循环调用的，此时处于 `QCoreApplication::exec()` 的调用栈深处。
3.  **执行 `doStuff()` - 第一部分**：

    *   **Emit `signal1`**:

        *   `foo.slot1` (DirectConnection): 立即在主线程执行。打印 `Execute slot one`。
        *   `foo2.slot1` (QueuedConnection): 调用被封为事件投递到 `foo2thread` 的事件队列。此时主线程继续执行，不等待次线程。
4.  **执行 `doStuff()` - 第二部分**：

    *   **Emit `finished`**:

        *   `app.quit()` (DirectConnection): **关键点！** 这直接调用 `QCoreApplication::exit(0)`。这**不会**立即跳出 `exec()`，它仅仅是设置了事件循环的“退出标志位”。
        *   `foo2thread.quit()` (QueuedConnection): 向次线程投递退出事件。
    *   *此时，主线程的 `doStuff()` 函数并没有停止，它依然在 `start()` -> `doStuff()` 的调用栈中运行。*
5.  **执行 `doStuff()` - 第三部分**：

    *   **Emit `signal2`**:

        *   `foo.slot2` (DirectConnection): 立即在主线程执行。打印 `Execute slot two`。
        *   `foo2.slot2` (QueuedConnection): 投递到次线程队列。
    *   `doStuff()` 函数返回。
6.  **结束 `start()`**： 打印 `Bye!`。`start()` 函数返回。
7.  **回到主事件循环**： 控制权最终回到了 `app.exec()` 的循环体。此时，循环检查“退出标志位”，发现已被设置为真。于是 `exec()` 返回，程序准备退出。 *注意：主线程结束得很快，此时次线程可能正在处理 `foo2.slot1`，或者正在等待处理 `quit` 事件。*
8.  **次线程的命运**： 由于 `finished` 信号先于 `signal2` 发射，投递到次线程的顺序是：`[slot1事件, quit事件, slot2事件]`。 当次线程处理完 `slot1` 后，下一个事件是 `quit`。`quit` 会导致次线程的事件循环结束。 **因此，排在 `quit` 之后的 `slot2` 事件永远不会被执行**。这就是为什么输出中没有看到次线程打印 `Execute slot two`。

### 总结

这个例子完美展示了以下几点：

1.  **DirectConnection 的同步性**：槽函数在 `emit` 语句处立即执行。
2.  **QueuedConnection 的异步性**：槽函数进入目标线程的队列等待。
3.  **quit() 的延迟特性**：`quit()` 只是设置标志，当前正在执行的槽函数（如 `start`）会完整跑完，函数返回后循环才会退出。
4.  **事件队列的处理顺序**：一旦线程的事件循环收到 `quit` 事件并处理，循环即终止，队列中剩余未处理的事件将被遗弃。

