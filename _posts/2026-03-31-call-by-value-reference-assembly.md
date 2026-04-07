---
layout: article
title: 值传递与引用传递：汇编视角
date: 2025-03-31 09:16:28 +0800
tags:
  - c/c++
  - assembly
---


## 引言

C++的值传递、引用传递和指针传递在源码层面看似简单，但其底层实现机制存在本质差异。本文通过分析 g++ 生成的汇编代码，深入剖析这三种传递方式的实现原理，搞清楚编译器到底是如何处理对象的构造、拷贝与析构过程。

## 实验代码设计

为了观察参数传递的底层行为，设计了一个包含构造函数、拷贝构造函数和析构函数的简单类 `MyClass`，并实现了三种参数传递方式的函数：

```cpp
class MyClass {
public:
    int value;

    MyClass(int v) : value(v) {
        std::cout << "构造函数: " << value << std::endl;
    }

    MyClass(const MyClass& other) : value(other.value) {
        std::cout << "拷贝构造函数: " << value << std::endl;
    }

    ~MyClass() {
        std::cout << "析构函数: " << value << std::endl;
    }
};

void byValue(MyClass obj);
void byReference(MyClass& obj);
void byPointer(MyClass* obj);
```

通过在构造函数、拷贝构造函数和析构函数中插入输出语句，可以清晰追踪对象的生命周期。使用 `g++ -S test_class.cpp` 生成汇编代码。

## C++ 名称修饰机制（Name Mangling）

在深入分析汇编代码之前，需要理解 C++ 的名称修饰机制。由于 C++ 支持函数重载、命名空间、类成员函数等特性，编译器必须为每个符号生成唯一的标识符，这个过程称为名称修饰（Name Mangling）。

### 修饰规则解析

在生成的汇编代码中，可以看到以下符号：

- `_ZN7MyClassC1Ei`：`MyClass` 的完整构造函数（Complete Constructor）
- `_ZN7MyClassC2Ei`：`MyClass` 的基础构造函数（Base Constructor）
- `_ZN7MyClassC1ERKS_`：`MyClass` 的完整拷贝构造函数
- `_ZN7MyClassC2ERKS_`：`MyClass` 的基础拷贝构造函数
- `_ZN7MyClassD1Ev`：`MyClass` 的完整析构函数（Complete Destructor）
- `_ZN7MyClassD2Ev`：`MyClass` 的基础析构函数（Base Destructor）

### 符号结构分析

以 `_ZN7MyClassC2Ei` 为例，解析其结构：

- `_Z`：所有修饰名称的前缀，标识这是一个修饰后的符号
- `N`：表示嵌套名称（Nested Name），用于命名空间或类作用域
- `7MyClass`：类名长度为 7，类名为 `MyClass`
- `C2`：构造函数（Constructor）类型标识，`C2` 表示基础构造函数
- `E`：嵌套名称结束标记
- `i`：参数类型，`i` 表示 `int` 类型

对于拷贝构造函数 `_ZN7MyClassC2ERKS_`：

- `R`：表示引用类型（Reference）
- `K`：表示 `const` 修饰符
- `S_`：表示"与前面相同的类型"，即 `MyClass`

### 构造函数的 C1 与 C2

在汇编代码中，可以观察到构造函数存在两个版本：

```assembly
_ZN7MyClassC2Ei:              # 基础构造函数
    # ... 函数实现 ...

.weak   _ZN7MyClassC1Ei
.set    _ZN7MyClassC1Ei,_ZN7MyClassC2Ei
```

这里使用了 `.set` 伪指令，将 `C1` 设置为 `C2` 的别名。这种设计源于 C++ 对象模型中的继承机制：

- **C1（Complete Object Constructor）**：完整对象构造函数
- **C2（Base Object Constructor）**：基础对象构造函数
- **C3（Allocating Constructor）**：分配构造函数

对于不涉及虚继承和多继承的简单类，`C1` 和 `C2` 的实现完全相同，编译器将它们设置为别名避免代码重复。析构函数同样存在 `D1`/`D2` 版本，在本例中也被设置为别名。

## 值传递的汇编实现

### 源码层面

```cpp
MyClass a(10);
byValue(a);
```

### 汇编层面的完整流程

在 `main` 函数中，值传递的汇编代码展示了完整的对象拷贝过程：

```assembly
leaq    -36(%rbp), %rax       # a的地址，源对象
leaq    -28(%rbp), %rax       # 分配临时对象空间
movq    %rdx, %rsi            # a的地址作为第2个参数
movq    %rax, %rdi            # 临时对象地址作为第1个参数
call    _ZN7MyClassC1ERKS_    # 调用拷贝构造函数

leaq    -28(%rbp), %rax
movq    %rax, %rdi            # 临时对象地址作为参数
call    _Z7byValue7MyClass    # 调用byValue函数

leaq    -28(%rbp), %rax
movq    %rax, %rdi
call    _ZN7MyClassD1Ev       # 调用临时对象的析构函数
```

### 关键发现

**临时对象在调用者栈帧上分配**。从汇编代码可以看出，临时对象的地址为 `-28(%rbp)`，而原始对象 `a` 的地址为 `-36(%rbp)`，两者都位于 `main` 函数的栈帧中。这意味着：

1. **拷贝构造发生在函数调用前**：编译器在调用 `byValue` 之前，先在调用者栈帧上为临时对象分配空间
2. **临时对象的生命周期由调用者管理**：临时对象在 `byValue` 返回后立即被析构
3. **被调用函数接收的是临时对象的地址**：尽管源码中参数声明为 `MyClass obj`，但实际传递的是临时对象的指针

### 拷贝构造函数的实现

```assembly
_ZN7MyClassC2ERKS_:             # 拷贝构造函数
    movq    %rdi, -8(%rbp)      # 目标对象地址（第1个参数）
    movq    %rsi, -16(%rbp)     # 源对象地址（第2个参数）
    movq    -16(%rbp), %rax
    movl    (%rax), %edx        # 从源对象读取value成员
    movq    -8(%rbp), %rax
    movl    %edx, (%rax)        # 写入目标对象的value成员
```

拷贝构造函数接收两个指针参数：目标对象的 `this` 指针和源对象的引用（实际上也是指针）。通过间接寻址完成成员的逐一拷贝。

## 引用传递的汇编实现

### 源码层面

```cpp
MyClass b(20);
byReference(b);
```

### 汇编层面的完整流程

```assembly
leaq    -32(%rbp), %rax       # 对象b的地址
movl    $20, %esi
movq    %rax, %rdi
call    _ZN7MyClassC1Ei       # 调用构造函数

leaq    -32(%rbp), %rax
movq    %rax, %rdi            # 将b的地址作为参数
call    _Z11byReferenceR7MyClass   # 直接调用byReference
```

### 关键发现

**引用传递不涉及拷贝构造**。对比值传递的汇编代码，引用传递的实现极为简洁：

1. **无临时对象创建**：没有调用拷贝构造函数的指令
2. **直接传递对象地址**：将原始对象 `b` 的地址直接作为参数传递给函数
3. **无额外析构调用**：函数返回后不需要析构临时对象

### 引用传递函数的实现

```assembly
_Z11byReferenceR7MyClass:
    movq    %rdi, -8(%rbp)    # 将对象地址保存到栈中
    movq    -8(%rbp), %rax
    movl    (%rax), %eax      # 通过间接寻址访问value成员
    # ... 输出操作 ...
    movq    -8(%rbp), %rax
    movl    $200, (%rax)      # 直接修改原始对象的value
```

函数内部通过指针间接寻址访问对象成员，所有修改直接作用于原始对象。**引用在底层实现上等价于指针**，但在语法层面提供了更安全、更直观的接口。

## 指针传递的汇编实现

### 源码层面

```cpp
MyClass c(30);
byPointer(&c);
```

### 汇编层面的完整流程

```assembly
leaq    -28(%rbp), %rax       # 对象c的地址
movl    $30, %esi
movq    %rax, %rdi
call    _ZN7MyClassC1Ei       # 调用构造函数

leaq    -28(%rbp), %rax
movq    %rax, %rdi            # 将c的地址作为参数
call    _Z9byPointerP7MyClass # 直接调用byPointer
```

### 关键发现

**指针传递与引用传递在汇编层面完全一致**。两者的实现机制相同：

1. **传递对象地址**：都是将对象的内存地址作为参数
2. **通过间接寻址访问成员**：函数内部都使用指针解引用操作
3. **无拷贝开销**：都不涉及对象拷贝和临时对象创建

唯一的区别在于语法层面：引用必须在声明时初始化且不能重新绑定，而指针可以为空、可以重新赋值。

## 构造函数与析构函数的调用约定

### 构造函数的参数传递

从汇编代码可以观察到，构造函数遵循标准的调用约定（x86-64 System V ABI）：

```assembly
_ZN7MyClassC2Ei:
    movq    %rdi, -8(%rbp)    # 第1个参数：this指针
    movl    %esi, -12(%rbp)   # 第2个参数：int v
```

**构造函数的隐式 `this` 指针**作为第一个参数通过 `%rdi` 寄存器传递，用户定义的参数从第二个位置开始。这解释了为什么**在调用构造函数前，必须先为对象分配内存空间**。

### 析构函数的实现

```assembly
_ZN7MyClassD2Ev:
    movq    %rdi, -8(%rbp)    # 将this指针保存到栈中
    # ... 输出操作 ...
```

析构函数只接收 `this` 指针作为参数，函数签名中的 `Ev` 表示无参数（`E` 结束标记，`v` 表示 `void`）。**析构函数负责清理对象资源，但不负责释放对象本身的内存**。

### 对象生命周期管理

在 `main` 函数的末尾，可以看到对象的析构顺序：

```assembly
leaq    -28(%rbp), %rax
movq    %rax, %rdi
call    _ZN7MyClassD1Ev       # 析构c

leaq    -32(%rbp), %rax
movq    %rax, %rdi
call    _ZN7MyClassD1Ev       # 析构b

leaq    -36(%rbp), %rax
movq    %rax, %rdi
call    _ZN7MyClassD1Ev       # 析构a
```

对象按照**构造顺序的逆序**进行析构，这是 C++ 栈对象生命周期管理的基本原则。编译器自动插入析构函数调用，确保资源正确释放。

## 异常处理与栈展开
在汇编代码的末尾处，我发现了多处析构函数的调用，这里是**异常处理代码**（exception handling），以下对异常处理代码进行简要分析。
### C++ 异常机制概述

需要明确的是，这里的"异常"是 **C++ 语言级别的异常（Exception）**，与硬件层面的中断（Interrupt）、陷阱（Trap）、故障（Fault）完全不同：

| 类型 | 触发方式 | 处理方式 | 是否涉及内核 |
|------|---------|---------|------------|
| 硬件异常（Trap/Fault） | CPU 检测到错误 | 操作系统处理 | 是 |
| C++ 异常（Exception） | 程序主动 `throw` | 用户代码 `catch` | 否 |

C++ 异常是纯用户态操作，不需要系统调用。当执行 `throw` 时：

1. 调用 `__cxa_throw` 函数（C++ ABI 标准函数）
2. 查找异常表，找到对应的处理代码
3. 执行栈展开（Stack Unwinding），调用已构造对象的析构函数
4. 跳转到 `catch` 块或继续向上传播

整个过程由编译器生成的代码和 C++ 运行时库配合完成。

### 异常处理表

汇编代码中包含了异常处理相关的段：

```assembly
.section    .gcc_except_table,"a",@progbits
.LLSDA2000:                    # Landing Site Data Area for main
    .byte   0xff               # 编码格式
    .byte   0xff
    .byte   0x1
    .uleb128 .LLSDACSE2000-.LLSDACSB2000  # 表的大小

.LLSDACSB2000:                 # Call Site Table Begin
    # 第1个异常范围
    .uleb128 .LEHB0-.LFB2000   # 起始位置偏移
    .uleb128 .LEHE0-.LEHB0     # 范围长度
    .uleb128 0                 # 没有处理器（继续传播）
    .uleb128 0                 # 没有类型过滤

    # 第2个异常范围
    .uleb128 .LEHB1-.LFB2000   # 起始：拷贝构造
    .uleb128 .LEHE1-.LEHB1     # 长度
    .uleb128 .L16-.LFB2000     # 跳转到 .L16 处理
    .uleb128 0

    # 第3个异常范围
    .uleb128 .LEHB2-.LFB2000   # 起始：byValue 调用
    .uleb128 .LEHE2-.LEHB2     # 长度
    .uleb128 .L15-.LFB2000     # 跳转到 .L15 处理
    .uleb128 0
```

这些数据结构记录了：
- 哪段代码可能抛出异常（`.LEHB*` 到 `.LEHE*`）
- 如果抛出异常应跳转到哪里（`.L15`、`.L16` 等）
- 相对于函数起始位置的偏移量

### 异常保护区域

在 `main` 函数中，可以看到异常保护区域的标记：

```assembly
.LEHB1:                        # 异常保护区域开始
    call    _ZN7MyClassC1ERKS_ # 拷贝构造可能抛异常
.LEHE1:                        # 异常保护区域结束

.LEHB2:
    call    _Z7byValue7MyClass # 函数调用可能抛异常
.LEHE2:
```

每个可能抛出异常的操作都被包裹在 `.LEHB*`（Exception Handler Begin）和 `.LEHE*`（Exception Handler End）标签之间。

### 栈展开的实现

当异常发生时，C++ 必须保证已构造的对象被正确析构，这个过程称为栈展开（Stack Unwinding）。在 `main` 函数中可以看到异常处理的跳转标签：

```assembly
.L15:                          # 异常处理入口点1
    endbr64
    movq    %rax, %rbx         # 保存异常对象指针
    leaq    -28(%rbp), %rax    # 取临时对象地址
    movq    %rax, %rdi
    call    _ZN7MyClassD1Ev    # 析构临时对象
    jmp     .L10               # 跳转继续清理

.L18:                          # 异常处理入口点2
    endbr64
    movq    %rax, %rbx
    leaq    -28(%rbp), %rax    # 取对象c地址
    movq    %rax, %rdi
    call    _ZN7MyClassD1Ev    # 析构对象c
    jmp     .L12

.L12:                          # 继续清理
    leaq    -32(%rbp), %rax    # 取对象b地址
    movq    %rax, %rdi
    call    _ZN7MyClassD1Ev    # 析构对象b
    jmp     .L10

.L10:                          # 最后清理
    leaq    -36(%rbp), %rax    # 取对象a地址
    movq    %rax, %rdi
    call    _ZN7MyClassD1Ev    # 析构对象a
    movq    %rbx, %rax         # 恢复异常对象
    # ... 栈保护检查 ...
    call    _Unwind_Resume@PLT # 继续向上抛出异常
```

### 异常处理的执行流程

假设在值传递过程中抛出异常：

```cpp
MyClass a(10);
byValue(a);  // 如果在拷贝构造或函数内部抛出异常
```

清理顺序为：
1. 析构临时对象（如果拷贝构造已完成）
2. 析构对象 `a`（已构造完成）
3. 调用 `_Unwind_Resume` 继续向上传播异常

编译器确保按照**构造顺序的逆序**析构对象，防止资源泄漏。这体现了 C++ 的 RAII（Resource Acquisition Is Initialization）原则在底层的实现。

### 性能开销

异常处理机制带来的开销包括：
- 生成额外的清理代码（`.L15`、`.L16` 等标签）
- 维护异常表（`.gcc_except_table` 段）
- 运行时查表和栈展开的开销

如果代码不使用异常，可以使用 `-fno-exceptions` 编译选项去掉这些代码，减小二进制体积并提升性能。

## 性能对比与优化建议

### 开销分析

通过汇编代码可以量化三种传递方式的性能差异：

**值传递的开销**：
- 1 次拷贝构造函数调用
- 1 次析构函数调用
- 临时对象的栈空间分配
- 成员数据的完整拷贝

**引用传递的开销**：
- 仅传递 8 字节地址（64 位系统）
- 无额外函数调用
- 无内存分配

**指针传递的开销**：
- 与引用传递完全相同

### 实际性能影响

对于本例中的简单类（仅包含一个 `int` 成员），值传递的开销主要体现在函数调用上。但对于包含大量成员或动态分配资源的复杂类，拷贝构造的开销将显著增加。

### 优化建议

1. **对于只读操作，优先使用 `const` 引用**：避免拷贝开销，同时保证对象不被修改
2. **对于需要修改的对象，使用非 `const` 引用或指针**：直接操作原始对象
3. **对于基本类型和小型对象，值传递可能更高效**：避免间接寻址的开销，且编译器可能将其优化为寄存器传递
4. **利用移动语义（C++11）**：对于临时对象，使用移动构造代替拷贝构造

## 深入理解：引用的本质

### 引用是编译器的语法糖

尽管 C++ 标准将引用描述为"对象的别名"，但从汇编层面看，**引用的实现方式与指针完全相同**。观察引用传递和指针传递的汇编代码，两者在机器指令层面没有任何区别。

引用本质上是编译器提供的语法糖，在底层通过指针实现，但在语法层面提供了更安全、更直观的接口：

1. **必须初始化**：引用声明时必须绑定到对象，避免了空指针问题
2. **不可重新绑定**：引用一旦绑定，不能指向其他对象，减少了逻辑错误
3. **自动解引用**：使用引用时无需显式解引用操作，代码更简洁

这些安全特性都是编译期保证的，运行时引用与指针的行为完全一致。



在启用优化的情况下，编译器可能直接在调用者的栈帧上构造对象，完全避免拷贝和移动操作。

## 总结

通过汇编代码的分析，揭示了 C++ 参数传递机制的底层实现：

1. **值传递**通过拷贝构造在调用者栈帧上创建临时对象，函数操作的是副本，原始对象不受影响
2. **引用传递**和**指针传递**在底层实现上完全相同，都是传递对象地址，函数直接操作原始对象
3. **名称修饰机制**为重载函数和类成员生成唯一符号，支持 C++ 的高级特性
4. **构造函数的 C1/C2 版本**用于处理虚继承场景，对于简单类会被优化为同一实现
5. **异常处理机制**确保在异常发生时正确调用析构函数，实现 RAII 原则

