---
layout: article
title: Qt 对象树解析
date: 2025-05-09 09:28:09 +0800
tags:
  - qt
  - cpp/dev
  - memory
---


## 对象树的概念

Qt 对象树是 Qt 框架提供的一种**父子所有权机制**。父对象负责在析构时自动删除所有子对象，从而简化 C++ 内存管理。

对象树解决的核心问题：在 GUI 应用中，控件层级深、生命周期复杂，手动追踪每个 `new` 出来的对象极易造成内存泄漏。对象树将所有权语义内嵌到对象关系中，父对象销毁时整棵子树随之销毁。

几个关键事实：

- 对象树与 MOC 无关，是纯 C++ 实现
- 适用于所有 `QObject` 派生类，不限于 GUI 控件
- `QTimer`、`QThread`、`QNetworkAccessManager` 等非 GUI 类同样支持



## 底层实现机制

### QObject 的核心成员

`QObject` 内部（通过 `QObjectPrivate`）维护两个关键成员：

```cpp
QObject *parent_;// 指向父对象，无父时为 nullptr
QList<QObject *> children_; // 子对象列表
```

### 构造时建立父子关系

```cpp
// 伪代码：QObject 构造函数
QObject::QObject(QObject *parent) {
    parent_ = nullptr;
    if (parent) {
        setParent(parent);
    }
}
```

### setParent() 的作用

```cpp
// 伪代码
void QObject::setParent(QObject *newParent) {
    if (parent_) {
        parent_->children_.removeOne(this); // 从旧父对象移除
    }
    parent_ = newParent;
    if (parent_) {
        parent_->children_.append(this);    // 加入新父对象列表
    }
}
```

`setParent()` 可在构造后调用，动态改变对象的归属。

### 子对象析构时的自我移除

子对象析构时，主动将自己从父对象的 `children_` 列表中移除，防止父对象后续析构时访问悬空指针：

```cpp
// 伪代码：QObject 析构函数开头
QObject::~QObject() {
    if (parent_) {
        parent_->children_.removeOne(this);
    }// ... 继续删除自己的子对象
}
```



## 自动析构的实现

### QObject 析构函数逻辑

```cpp
// 伪代码
QObject::~QObject() {
    // 1. 从父对象列表中移除自身
    if (parent_) {
        parent_->children_.removeOne(this);
    }
    // 2. 逆序删除所有子对象
    while (!children_.isEmpty()) {
        delete children_.last(); // 子对象析构时调用 removeOne，列表自动缩短
    }
}
```

### 级联析构过程

```
delete window
  └─ ~QMainWindow()
       ├─ delete children_.last() → ~QWidget(centralWidget)
       │    ├─ delete children_.last() → ~QPushButton(btn2)
       │    └─ delete children_.last() → ~QPushButton(btn1)
       └─ delete children_.last() → ~QMenuBar(menuBar)
```

### 逆序删除的原因

子对象以逆序（`children_.last()` 优先）删除：与构造顺序相反，符合 C++ 栈展开惯例；避免在迭代列表时因 `removeOne` 导致索引错位。



## 堆 vs 栈的注意事项

### 为什么子控件必须在堆上创建

父对象析构时会 `delete` 其 `children_` 列表中的每个指针。`delete` 只能作用于堆上的对象。若子对象在栈上创建，父对象析构时对其调用 `delete` 属于未定义行为。

### double-free 问题

```cpp
void dangerous_example() {
    QLabel label("hello");     // 先构造，在栈上
    QWidget parent;
    label.setParent(&parent);  // 加入 parent.children_

    // 栈展开（后构造先析构）：
    // 1. parent 先析构 → delete &label → label 在栈上，未定义行为
    // 2. label 再次析构 → double-free
}
```

**根本原因**：栈变量的析构顺序由编译器决定，与对象树的 `delete` 操作可能冲突。

### 正确的使用模式

```cpp
// 正确：子控件在堆上
QWidget *window = new QWidget;
QPushButton *btn = new QPushButton("OK", window); // 交由对象树管理

// 正确：顶层窗口可在栈上（无父对象，无 double-free 风险）
QWidget window;
QPushButton *btn = new QPushButton("OK", &window); // btn 在堆上
```



## deleteLater() 原理

### 为什么需要 deleteLater()

在槽函数中直接 `delete this` 存在风险：Qt 的信号槽分发机制在调用槽函数后，可能还需要访问发送者对象的内部状态，直接 `delete` 会导致悬空指针。

### 实现机制

```cpp
void QObject::deleteLater() {
    // 向事件循环投递一个 DeferredDelete 事件
    QCoreApplication::postEvent(this, new QDeferredDeleteEvent());
}
```

`postEvent` 是线程安全的，事件被放入对象所属线程的事件队列。

### 处理时机

```
槽函数执行
  → 槽函数返回
  → Qt 信号分发完成
  → 事件循环下一轮
  → 处理 DeferredDelete
  → delete obj（调用栈已安全）
```

注意：若无事件循环运行，`deleteLater()` 投递的事件不会被处理，对象不会被删除。

### 与对象树的关系

`deleteLater()` 调用后，对象仍在父对象的 `children_` 列表中，直到实际 `delete` 发生。实际 `delete` 时，正常的对象树析构逻辑执行：子对象级联删除，自身从父对象列表移除。



## 对象树与内存管理模式对比

| 管理方式 | 适用场景 | 优点 | 缺点 |
|---|---|---|---|
| **Qt 对象树** | QObject 派生类，GUI 控件层级 | 无需手动 delete，与信号槽集成 | 仅限 QObject；所有权语义隐式 |
| **RAII / `unique_ptr`** | 非 QObject 类，或需要明确所有权语义 | 所有权显式，编译期检查 | 不能直接用于有父对象的 QObject |
| **手动 `delete`** | 极少数需要精确控制析构时机的场景 | 完全控制 | 极易泄漏或 double-free |

`unique_ptr<QObject>` 与对象树混用时需特别注意：若 `QObject` 有父对象，`unique_ptr` 析构时调用 `delete`，父对象析构时再次 `delete`，导致 double-free。



## 常见陷阱

### 陷阱 1：栈上创建带父对象的子控件

```cpp
void setup(QWidget *parent) {
    QLabel label("text", parent); // 栈上 + 有父对象
} // label 析构，从 parent->children_ 移除；parent 析构时再次 delete → 崩溃
```

规则：**只要指定了父对象，必须在堆上创建。**

### 陷阱 2：父对象不是 QObject 派生类

```cpp
struct Container {
    QPushButton btn; // 错误：Container 不是 QObject，btn 无法加入对象树
};
```

对象树要求父对象必须是 `QObject` 或其派生类。

### 陷阱 3：跨线程 delete

```cpp
// 线程 B 中
delete obj; // 错误：对象树操作（从 parent->children_ 移除）非线程安全
```

跨线程删除对象应使用 `deleteLater()`，它通过事件系统将删除操作派发回对象所属线程。

### 陷阱 4：子对象析构时访问父对象

```cpp
class B : public QObject {
public:
    QObject *a_ref; // 裸指针，指向父对象 A~B() { a_ref->doSomething(); } // 危险：父对象正在析构中
};
```

析构顺序：父对象先进入析构，在析构函数内 `delete` 子对象。子对象析构时，父对象已处于析构中间状态，通过裸指针访问父对象属于未定义行为。使用 `QPointer<QObject>` 可自动置空悬空指针。



## 实际应用建议

### 顶层窗口与子控件的分配策略

```cpp
int main(int argc, char *argv[]) {
    QApplication app(argc, argv);

    QMainWindow window;                // 顶层：栈上，无父对象
    auto *btn = new QPushButton("Click", &window);  // 子控件：堆上，对象树管理

    window.show();
    return app.exec();
    // window 析构 → btn 自动删除
}
```

### 非 GUI 的 QObject 同样适用

```cpp
QObject root;
auto *timer   = new QTimer(&root);
auto *manager = new QNetworkAccessManager(&root);
// root 析构时，timer 和 manager 自动删除
```

### 何时用对象树，何时用 `unique_ptr`

**使用对象树：** 对象是 `QObject` 派生类；生命周期与 UI 层级绑定；需要 `deleteLater()` 语义。

**使用 `unique_ptr`：** 对象不是 `QObject` 派生类；顶层 `QObject`（无父对象）且需要明确所有权转移。

核心原则：**有父对象的 `QObject` 交给对象树；无父对象的顶层对象，可选择 `unique_ptr` 或栈分配。两种机制不要混用于同一个对象。**
