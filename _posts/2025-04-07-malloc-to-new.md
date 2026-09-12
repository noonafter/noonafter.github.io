---
layout: article
title: 从 malloc 到 new：C++ 堆内存管理的演进
date: 2025-04-07 9:00:00 +0800
tags:
  - cpp/basic
  - memory
---


上一篇建立了栈与堆的基本认知：堆提供了栈无法给予的空间容量、动态大小和灵活生命周期，但代价是需要程序员手动管理。本篇将沿着历史演进的脉络，剖析 C 语言的 `malloc/free` 与 C++ 的 `new/delete` 在设计上的本质差异，以及为什么现代 C++ 最终走向了"尽量不直接写 `new`"的实践准则。

## 一、malloc/free：只管内存，不管对象

`malloc` 和 `free` 是 C 标准库提供的堆内存管理函数，其职责极为单纯：

- `malloc(size_t n)`：向堆申请 `n` 个字节的原始内存，返回 `void*` 指针
- `free(void* ptr)`：将 `ptr` 指向的内存归还给堆管理器

```c
// C 语言风格
int* arr = (int*)malloc(10 * sizeof(int));  // 申请 40 字节原始内存
if (arr == NULL) { /* 处理失败 */ }
arr[0] = 42;
free(arr);  // 归还内存
```

`malloc/free` 的核心局限在于：**它们只操作字节，对 C++ 对象一无所知**。

- 不会调用构造函数：`malloc` 返回的是未初始化的原始内存，对象处于无效状态
- 不会调用析构函数：`free` 直接回收内存，对象内部持有的资源（如文件句柄、子对象）不会被清理
- 类型不安全：返回 `void*`，必须手动强制类型转换，编译器无法检查

对于 C 语言的 `struct`（纯数据，无构造/析构概念），`malloc/free` 完全够用。但 C++ 引入了类、构造函数、析构函数和继承，`malloc/free` 的模型在此彻底失效。

## 二、new/delete：语言运算符，而非库函数

C++ 引入 `new` 和 `delete` 来解决 `malloc/free` 的根本缺陷。它们的身份是**语言运算符**（operator），而非普通函数——这一设计赋予了它们操作语言内部语义的特权。

### new 表达式的三步执行流程

执行 `T* ptr = new T(args);` 时，编译器生成的代码包含三个不可分割的步骤：

1. **分配内存**：调用底层函数 `operator new(sizeof(T))`，申请足够容纳 `T` 的原始内存
2. **构造对象**：在分配的内存地址上调用构造函数 `T::T(args)`，将原始内存初始化为合法对象
3. **返回类型化指针**：返回 `T*`，无需手动强转

### delete 表达式的两步执行流程

执行 `delete ptr;` 时：

1. **析构对象**：调用 `ptr->~T()`，清理对象内部持有的所有资源
2. **释放内存**：调用底层函数 `operator delete(ptr)`，将内存归还给堆管理器

**顺序至关重要**：`delete` 必须先析构再释放，`new` 必须先分配再构造。这个顺序保证了对象在整个生命周期内始终处于合法状态。

### 与 malloc/free 的本质对比

| 特性 | `malloc` / `free` | `new` / `delete` |
|------|-------------------|------------------|
| 身份 | 标准库函数 | 语言运算符 |
| 构造/析构 | 不调用 | 自动调用 |
| 类型安全 | 返回 `void*`，需强转 | 直接返回 `T*` |
| 大小计算 | 需手动 `sizeof` | 编译器自动计算 |
| 失败处理 | 返回 `NULL` | 抛出 `std::bad_alloc` |
| 可重载 | 不可针对类型重载 | 可针对特定类重载 |

### 为什么设计为运算符

将 `new/delete` 设计为运算符而非函数，核心原因有三：

**类型安全与自动大小计算**：编译器在编译期就知道 `T` 的大小，无需程序员手写 `sizeof(T)`，也无需强制类型转换。

**触发构造与析构**：普通函数调用无法在指定内存地址上启动构造函数。`new` 作为运算符，拥有直接操作对象生命周期的语言级特权。

**支持针对类型重载**：可以为特定类重载 `operator new`，实现自定义内存分配策略（如内存池），而语法与标准 `new` 完全一致。

## 三、new 的三种形态

C++ 中的 `new` 实际上有三种不同语义，理解它们的区别对于阅读底层代码至关重要。

### new 表达式（最常用）

组合动作：分配内存 + 调用构造函数。这是日常开发中使用的形式。

```cpp
MyClass* ptr = new MyClass(10);
```

### operator new 函数（底层分配）

这是 `new` 表达式在第一步调用的底层函数，职责等同于 `malloc`：只分配原始内存，不构造对象。可以重载它来改变程序的内存分配行为。

```cpp
void* raw = operator new(sizeof(MyClass));  // 仅分配，不构造
```

### placement new（定位构造）

在**已有内存**上构造对象，不进行任何内存分配。常用于内存池、`std::vector` 的底层扩容实现等高性能场景。

```cpp
char buffer[sizeof(MyClass)];
MyClass* ptr = new (buffer) MyClass(10);  // 在 buffer 上构造，不分配新内存
// 注意：必须手动调用析构函数，不能用 delete
ptr->~MyClass();
```

placement new 是三种形态中唯一需要手动调用析构函数的情况，因为内存本身不是由 `new` 分配的，不能交给 `delete` 释放。

## 四、裸 new 的三大危险

尽管 `new/delete` 相比 `malloc/free` 是巨大的进步，但在现代 C++（C++11 及以后）的实践中，直接使用裸 `new` 仍被视为危险行为。

### 危险一：内存泄漏

`new` 必须配套 `delete`。在复杂的控制流中，`delete` 极易被遗漏：

```cpp
void process(bool condition) {
    MyClass* obj = new MyClass();
    if (condition) {
        return;         // 提前返回，delete 被跳过，内存泄漏
    }
    // ... 其他逻辑 ...
    delete obj;
}
```

### 危险二：异常安全性缺失

若在 `new` 之后、`delete` 之前抛出异常，程序会直接跳转到 `catch` 块，`delete` 永远不会执行：

```cpp
void riskyFunction() {
    MyClass* ptr = new MyClass();
    doSomething();      // 若此处抛出异常
    delete ptr;         // 这行永远不会执行，内存泄漏
}
```

### 危险三：所有权语义模糊

看到一个原始指针 `T* ptr`，无法从类型上判断：

- 这块内存该由谁负责释放？
- 是否已经有其他地方持有同一个指针？
- 释放后，其他持有者是否还会访问？

这种所有权的不明确性是**重复释放**（double free）和**野指针**（dangling pointer）的根源。

```cpp
void ambiguous(MyClass* ptr) {
    // 该不该 delete ptr？调用者释放了吗？完全不清楚
    delete ptr;  // 可能是重复释放
}
```

## 五、智能指针：解决所有权问题的语言方案

裸 `new` 的三大危险本质上都源于同一个问题：**所有权语义无法从类型上表达**。C++11 引入了三种智能指针，通过类型系统将所有权关系显式化。

### std::unique_ptr（独占所有权）

同一时间只能有一个 `unique_ptr` 持有某块堆内存。它不可拷贝，只能移动（`std::move`）。当 `unique_ptr` 离开作用域时，自动调用 `delete`。

```cpp
std::unique_ptr<MyClass> ptr(new MyClass(10));
// ptr 离开作用域时，自动 delete
```

**开销**：几乎为零，与裸指针性能相当，是"零成本抽象"的典型。

### std::shared_ptr（共享所有权）

多个 `shared_ptr` 可以指向同一个对象，内部维护一个**引用计数**。每增加一个持有者，计数加一；持有者销毁，计数减一；计数归零时才真正释放内存。

```cpp
std::shared_ptr<MyClass> a(new MyClass(10));
std::shared_ptr<MyClass> b = a;  // 引用计数变为 2
// a 和 b 都离开作用域后，计数归零，内存释放
```

**开销**：引用计数的维护带来额外的原子操作开销，比 `unique_ptr` 稍重。

### std::weak_ptr（弱引用，不参与所有权）

`weak_ptr` 指向 `shared_ptr` 管理的对象，但**不增加引用计数**。它用于解决 `shared_ptr` 的循环引用问题，或表达"我只是观察，不负责生命周期"的语义。使用前需通过 `lock()` 升级为 `shared_ptr` 以安全访问。

```cpp
std::weak_ptr<MyClass> observer = sharedPtr;
if (auto ptr = observer.lock()) {  // 对象仍存活
    ptr->doSomething();
}
```

### 选择决策树

| 场景 | 选择 |
|------|------|
| 不需要跨函数生存 | 栈对象 `MyClass obj;` |
| 堆对象，所有权唯一 | `std::unique_ptr`（首选） |
| 堆对象，多处共享 | `std::shared_ptr` |
| 只观察，不持有 | `std::weak_ptr` 或裸指针（不负责释放） |
| 极底层：内存池、自定义容器 | 裸 `new/delete`（需严格封装） |

---

下一篇将深入智能指针的内部机制：`unique_ptr` 的零成本抽象原理、`shared_ptr` 引用计数的实现细节、`weak_ptr` 如何打破循环引用，以及为什么应该用 `make_unique`/`make_shared` 工厂函数而非直接写 `new`。
