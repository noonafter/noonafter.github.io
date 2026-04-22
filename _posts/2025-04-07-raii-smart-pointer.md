---
layout: article
title: RAII 与智能指针的内部机制
date: 2025-04-07 10:00:00 +0800
tags:
  - cpp/stl
  - memory
  - raii
---


上一篇引入了三种智能指针作为裸 `new` 的替代方案。本篇深入它们的内部实现：`unique_ptr` 为何能做到零开销、`shared_ptr` 的引用计数如何工作、循环引用为何会导致内存泄漏以及 `weak_ptr` 如何打破它，最后解释为什么工厂函数 `make_unique`/`make_shared` 优于直接写 `new`。

## 一、RAII：用对象生命周期驱动资源释放

智能指针的底层哲学是 **RAII**（Resource Acquisition Is Initialization，资源获取即初始化）。这个名字描述的是一种绑定关系：

- **资源获取**发生在对象**构造**时
- **资源释放**发生在对象**析构**时

由于栈对象的析构由编译器保证（无论正常返回还是异常触发栈展开），将资源封装在栈对象中，就等于将资源的释放委托给了编译器。

```cpp
// 文件句柄的 RAII 封装示意
class FileHandle {
    FILE* fp_;
public:
    FileHandle(const char* path) : fp_(fopen(path, "r")) {}
    ~FileHandle() { if (fp_) fclose(fp_); }  // 析构时自动关闭
};

void readFile() {
    FileHandle f("data.txt");  // 构造时打开
    // ... 读取操作，即便抛出异常 ...
}   // f 析构，文件自动关闭
```

智能指针是 RAII 在堆内存管理上的具体应用：构造时接管堆内存，析构时释放堆内存。

## 二、unique_ptr 的零成本抽象

### 内部结构

`unique_ptr<T>` 的内部结构极为简单：本质上只是一个持有裸指针的包装器，加上一个自定义删除器（Deleter）。

```cpp
// 简化的 unique_ptr 实现示意
template<typename T>
class unique_ptr {
    T* ptr_;
public:
    explicit unique_ptr(T* p) : ptr_(p) {}
    ~unique_ptr() { delete ptr_; }          // 析构时自动释放

    // 禁止拷贝
    unique_ptr(const unique_ptr&) = delete;
    unique_ptr& operator=(const unique_ptr&) = delete;

    // 允许移动
    unique_ptr(unique_ptr&& other) noexcept : ptr_(other.ptr_) {
        other.ptr_ = nullptr;               // 转移后原指针置空
    }

    T* get() const { return ptr_; }
    T& operator*() const { return *ptr_; }
    T* operator->() const { return ptr_; }
};
```

### 为何是零成本

编译器在优化后，`unique_ptr` 与裸指针生成的机器码几乎完全相同：

- 没有额外的内存分配（`unique_ptr` 对象本身在栈上，大小等于一个指针）
- 没有运行时计数或查表
- 析构函数调用在编译期内联，不产生函数调用开销

**不可拷贝，只可移动**是独占语义的类型系统保障：编译器在编译期就能阻止意外的所有权共享，而非等到运行时崩溃。

```cpp
auto a = std::make_unique<MyClass>();
auto b = a;              // 编译错误：拷贝被禁止
auto b = std::move(a);   // 合法：所有权转移，a 变为 nullptr
```

## 三、shared_ptr 的引用计数实现

### 控制块（Control Block）

`shared_ptr` 比 `unique_ptr` 复杂，因为它需要支持多个持有者共同管理同一块内存。实现方式是在堆上额外分配一个**控制块**（Control Block），与被管理对象分开存储：

```
shared_ptr<T> 对象（栈上）：
┌──────────┬──────────┐
│  ptr_    │  ctrl_   │
│ (T* 指针) │(控制块指针)│
└──────────┴──────────┘
     │              │
     ▼              ▼
  堆上的 T 对象    堆上的控制块
                ┌─────────────────┐
                │ shared_count: 2 │  ← 强引用计数
                │ weak_count:   1 │  ← 弱引用计数
                │ deleter         │  ← 删除器
                └─────────────────┘
```

### 引用计数的生命周期规则

- **拷贝** `shared_ptr`：`shared_count` 加一
- **销毁** `shared_ptr`：`shared_count` 减一
- `shared_count` 降为 0：调用删除器，释放 **T 对象**的内存
- `weak_count` 降为 0：释放**控制块**本身的内存

```cpp
{
    auto a = std::make_shared<MyClass>();  // shared_count = 1
    {
        auto b = a;                        // shared_count = 2
        auto c = a;                        // shared_count = 3
    }                                      // b, c 析构，shared_count = 1
}                                          // a 析构，shared_count = 0，对象释放
```

### 线程安全性

引用计数的增减使用**原子操作**（`std::atomic`），因此多线程环境下对同一 `shared_ptr` 的拷贝和销毁是线程安全的。但这也是 `shared_ptr` 比 `unique_ptr` 开销更大的原因——原子操作比普通内存读写慢。

注意：引用计数本身的线程安全，**不等于**通过 `shared_ptr` 访问对象是线程安全的。对象内部的数据竞争仍需额外的同步机制。

## 四、循环引用与 weak_ptr

### 循环引用导致内存泄漏

当两个对象通过 `shared_ptr` 互相持有对方时，会形成循环引用，导致引用计数永远无法降为零：

```cpp
struct Node {
    std::shared_ptr<Node> next;
    std::shared_ptr<Node> prev;  // 双向链表
};

auto a = std::make_shared<Node>();
auto b = std::make_shared<Node>();
a->next = b;   // b 的 shared_count = 2
b->prev = a;   // a 的 shared_count = 2

// a, b 离开作用域，各自 shared_count 减为 1，但永远不会到 0
// 两个 Node 对象永远不会被释放 → 内存泄漏
```

### weak_ptr 打破循环

`weak_ptr` 持有控制块的指针（增加 `weak_count`），但**不增加 `shared_count`**，因此不影响对象的生命周期：

```cpp
struct Node {
    std::shared_ptr<Node> next;
    std::weak_ptr<Node> prev;    // 改为弱引用
};

auto a = std::make_shared<Node>();
auto b = std::make_shared<Node>();
a->next = b;   // b 的 shared_count = 2
b->prev = a;   // a 的 shared_count 仍为 1，weak_count = 2

// a 离开作用域，shared_count 降为 0，a 被释放
// b 的 next（指向 a）随之析构，b 的 shared_count 降为 0，b 被释放
```

使用 `weak_ptr` 时，必须先通过 `lock()` 升级为 `shared_ptr` 才能安全访问对象，因为对象可能已经被释放：

```cpp
if (auto node = weakPtr.lock()) {  // 返回 shared_ptr，若对象已释放则返回空
    node->doSomething();
}
```

## 五、为什么用工厂函数而非裸 new

### make_unique 的异常安全性

直接用 `new` 初始化 `unique_ptr` 存在一个微妙的异常安全漏洞。考虑以下函数调用：

```cpp
// 危险：参数求值顺序未定义
process(std::unique_ptr<A>(new A()), computeValue());
```

C++ 标准不规定函数参数的求值顺序。编译器可能按以下顺序执行：

1. `new A()` — 分配并构造 A
2. `computeValue()` — 若此处抛出异常
3. `unique_ptr<A>(...)` — 永远不会执行，A 的内存泄漏

`make_unique` 将分配和智能指针构造合并为一个原子操作，消除了这个窗口：

```cpp
process(std::make_unique<A>(), computeValue());  // 安全
```

### make_shared 的性能优势

`make_shared` 相比 `shared_ptr<T>(new T())` 有一个重要的性能优势：**将对象和控制块合并为一次内存分配**。

```
shared_ptr<T>(new T())：
  分配 1：堆上的 T 对象
  分配 2：堆上的控制块
  → 两次 malloc，两块不连续内存

make_shared<T>()：
  分配 1：堆上的 [T 对象 | 控制块]（连续内存）
  → 一次 malloc，缓存局部性更好
```

减少一次内存分配，同时提升缓存命中率，在高频创建 `shared_ptr` 的场景下性能差异显著。

### 代码简洁性

```cpp
// 类型名写两遍，冗余
std::unique_ptr<MyClass> ptr(new MyClass(arg1, arg2));

// 类型推导，简洁
auto ptr = std::make_unique<MyClass>(arg1, arg2);
```

## 六、栈展开与 RAII 的协作

将第一篇的栈展开机制与本篇的 RAII 结合，可以得出 C++ 异常安全的完整图景：

```cpp
void complexOperation() {
    auto conn = std::make_unique<DbConnection>();   // 获取数据库连接
    auto lock = std::make_unique<MutexLock>();      // 获取锁

    processData();  // 若此处抛出异常

    // 正常路径：函数返回，lock 和 conn 按构造的逆序析构
}
// 异常路径：栈展开触发，lock.~unique_ptr() 先执行，conn.~unique_ptr() 后执行
// 两条路径下，资源都得到正确释放
```

**析构顺序**：栈对象按构造的**逆序**析构，这保证了依赖关系的正确处理（后构造的对象可能依赖先构造的对象，因此先析构）。

---

至此，C++ 内存管理的核心机制已完整覆盖：从内存模型的底层布局，到手动管理的演进历史，再到现代 C++ 的自动化方案。第四篇将讨论更高级的话题：`operator new` 重载与内存池、常见内存 Bug 的排查，以及调试工具的使用。
