---
title: 虚函数与虚表：汇编视角
tags: vptr c/c++
---


## 一、虚函数基本概念

### 1.1 什么是虚函数？

虚函数（Virtual Function）是C++实现多态的核心机制。通过在基类中使用 `virtual` 关键字声明函数，可以让派生类重写该函数，并在运行时根据对象的实际类型来调用相应的函数版本。

**核心特性：**

*   **动态绑定（Dynamic Binding）**：函数调用在运行时确定，而非编译时
*   **多态性（Polymorphism）**：同一接口可以有不同的实现
*   **虚表机制（Virtual Table）**：通过虚函数表实现动态分发

### 1.2 虚函数 vs 普通函数

```cpp
class Base {
public:
    virtual void virtFunc() {        // 虚函数：动态绑定
        std::cout << "Base::virtFunc" << std::endl;
    }
    void normalFunc() {              // 普通函数：静态绑定
        std::cout << "Base::normalFunc" << std::endl;
    }
};

class Derived : public Base {
public:
    void virtFunc() override {       // 重写虚函数
        std::cout << "Derived::virtFunc" << std::endl;
    }
};
```

**关键区别：**

*   虚函数通过对象的实际类型调用（运行时决定）
*   普通函数通过指针/引用的声明类型调用（编译时决定）

### 1.3 虚函数的工作原理概述

虚函数的实现依赖于两个关键数据结构：

1.  **虚函数表**：

    *   每个包含虚函数的类都有一个虚表
    *   虚表是一个函数指针数组，存储该类所有虚函数的地址
    *   编译时生成，存储在只读数据段
2.  **虚表指针**：

    *   每个包含虚函数的对象都有一个vptr
    *   vptr指向对象所属类的虚表
    *   在对象构造时初始化

**简化工作流程：**

    对象创建 → 编译器插入vptr初始化代码 → vptr指向类的虚表
             ↓
    函数调用 → 通过vptr查找虚表 → 获取函数指针 → 间接调用



***

## 二、测试代码分析

### 2.1 完整测试代码

```cpp
#include <iostream>

class Base {
public:
    virtual void virtFunc(){
        std::cout << "Base::virtFunc" << std::endl;
    }
    void normalFunc() {
        std::cout << "Base::normalFunc" << std::endl;
    }
};

class Derived : public Base {
public:
    void virtFunc() override {
        std::cout << "Derived::virtFunc" << std::endl;
    }
};

void testPolymorphism(Base* obj) {
    obj->virtFunc();   // 【关键点A】虚函数调用 (动态绑定)
    obj->normalFunc(); // 【关键点B】普通函数调用 (静态绑定)
    std::cout << "Hello" << std::endl;
}

int main() {
    Derived d;
    testPolymorphism(&d);
    return 0;
}
```

### 2.2 代码执行流程

1.  `main()` 创建 `Derived` 对象 `d`
2.  将 `d` 的地址传递给 `testPolymorphism()`
3.  调用 `virtFunc()` → 输出 "Derived::virtFunc"（动态绑定）
4.  调用 `normalFunc()` → 输出 "Base::normalFunc"（静态绑定）

***

## 三、虚表（Virtual Table）结构

### 3.1 虚表的内存布局

编译器为每个包含虚函数的类生成一个虚表（vtable），虚表是一个函数指针数组。

**从汇编代码中可以看到虚表定义：**

```asm
_ZTV7Derived:           # Derived类的虚表
    .quad   0           # 偏移量（用于多重继承）
    .quad   _ZTI7Derived    # 类型信息指针（RTTI）
    .quad   _ZN7Derived8virtFuncEv  # 虚函数指针：Derived::virtFunc()
```

**虚表结构说明：**

*   **偏移量**：在单继承中为0，多重继承时用于调整this指针
*   **类型信息**：指向RTTI（运行时类型信息），用于 `dynamic_cast` 和 `typeid`
*   **虚函数指针**：按声明顺序排列的虚函数地址

### 3.2 对象内存布局

每个包含虚函数的对象，其内存布局的**第一个成员**是虚表指针（vptr）：

    Derived对象内存布局：
    +-------------------+
    | vptr (8字节)      | → 指向 _ZTV7Derived + 16
    +-------------------+
    | 其他成员变量...    |
    +-------------------+

**为什么是 +16？**
虚表前16字节存储偏移量和RTTI指针，真正的函数指针从第16字节开始。

***

## 四、汇编代码深度解析

### 4.1 对象初始化：虚表指针的设置

**main函数中的关键汇编代码：**

```asm
main:
    # ... 函数序言 ...
    leaq    16+_ZTV7Derived(%rip), %rax  # 计算虚表地址（跳过前16字节）
    movq    %rax, -16(%rbp)              # 将vptr写入对象的第一个字段
    leaq    -16(%rbp), %rax              # 获取对象地址
    movq    %rax, %rdi                   # 作为参数传递
    call    _Z16testPolymorphismP4Base   # 调用testPolymorphism
```

**解析：**

1.  `leaq 16+_ZTV7Derived(%rip), %rax`：计算虚表中函数指针的起始地址
2.  `movq %rax, -16(%rbp)`：将虚表指针写入对象的首地址（这就是vptr）
3.  对象创建完成后，vptr已经指向正确的虚表

### 4.2 虚函数调用：动态分发机制

**testPolymorphism函数中的虚函数调用：**

```asm
_Z16testPolymorphismP4Base:
    # obj->virtFunc() 的实现
    movq    -8(%rbp), %rax      # 【步骤1】加载对象指针到rax
    movq    (%rax), %rax        # 【步骤2】解引用获取vptr（对象首8字节）
    movq    (%rax), %rdx        # 【步骤3】从虚表中取第一个函数指针
    movq    -8(%rbp), %rax      # 【步骤4】重新加载对象指针（作为this）
    movq    %rax, %rdi          # 【步骤5】将this指针放入rdi寄存器
    call    *%rdx               # 【步骤6】间接调用：跳转到rdx指向的函数
```

**动态分发的核心步骤：**

1.  从对象地址读取vptr（对象的前8字节）
2.  从vptr指向的虚表中读取函数指针
3.  通过函数指针间接调用（`call *%rdx`）

**关键点：** 这是一个**两次内存访问**的过程（读vptr + 读函数指针），这就是虚函数调用比普通函数慢的原因。

### 4.3 普通函数调用：静态绑定

**testPolymorphism函数中的普通函数调用：**

```asm
    # obj->normalFunc() 的实现
    movq    -8(%rbp), %rax      # 加载对象指针
    movq    %rax, %rdi          # 将对象指针作为this传递
    call    _ZN4Base10normalFuncEv  # 直接调用Base::normalFunc
```

**静态绑定的特点：**

*   **直接调用**：`call` 指令直接指定函数地址
*   **编译时确定**：调用哪个函数在编译时就已经决定
*   **性能更高**：只需一次函数调用，无需查表

**对比总结：**

| 调用类型 | 指令形式         | 内存访问次数          | 绑定时机 |
| ---- | ------------ | --------------- | ---- |
| 虚函数  | `call *%rdx` | 2次（vptr + 函数指针） | 运行时  |
| 普通函数 | `call 函数地址`  | 0次额外访问          | 编译时  |

***

## 五、完整执行流程图解

### 5.1 虚函数调用的完整过程

    1. 对象创建阶段（编译时 + 运行时）
       ┌─────────────────────────────────────┐
       │ Derived d;                          │
       │ 编译器生成：                         │
       │   - 分配栈空间                       │
       │   - 初始化vptr = &_ZTV7Derived[2]   │
       └─────────────────────────────────────┘
                        ↓
    2. 函数调用阶段（运行时）
       ┌─────────────────────────────────────┐
       │ obj->virtFunc()                     │
       │                                     │
       │ 步骤1: 读取obj地址                   │
       │ 步骤2: 读取obj[0] → vptr            │
       │ 步骤3: 读取vptr[0] → 函数指针        │
       │ 步骤4: call *函数指针                │
       └─────────────────────────────────────┘
                        ↓
    3. 函数执行
       ┌─────────────────────────────────────┐
       │ Derived::virtFunc()                 │
       │ 输出: "Derived::virtFunc"           │
       └─────────────────────────────────────┘

### 5.2 内存布局示意图

    栈内存：
    +------------------+  ← rbp-16
    | vptr             | → 指向 _ZTV7Derived+16
    +------------------+
    | (Derived对象d)   |
    +------------------+

    虚表内存（只读数据段）：
    _ZTV7Derived:
    +------------------+  ← _ZTV7Derived+0
    | 0 (offset)       |
    +------------------+  ← _ZTV7Derived+8
    | _ZTI7Derived     |
    +------------------+  ← _ZTV7Derived+16 (vptr指向这里)
    | Derived::virtFunc|
    +------------------+

***

## 六、关键技术细节

### 6.1 符号名称修饰（Name Mangling）

C++编译器会对函数名进行修饰以支持函数重载和命名空间：

    原始名称                    修饰后名称
    -------------------------------------------------
    Derived::virtFunc()      → _ZN7Derived8virtFuncEv
    Base::normalFunc()       → _ZN4Base10normalFuncEv
    testPolymorphism()       → _Z16testPolymorphismP4Base

**解码规则：**

*   `_Z`：修饰名称前缀
*   `N...E`：嵌套名称（类成员）
*   `7Derived`：7个字符的类名"Derived"
*   `8virtFunc`：8个字符的函数名"virtFunc"
*   `v`：返回类型void
*   `P4Base`：参数类型为Base指针

### 6.2 寄存器使用约定（x86-64 调用约定）

    寄存器    用途
    --------------------------
    %rdi     第1个参数（this指针）
    %rsi     第2个参数
    %rdx     第3个参数 / 临时存储函数指针
    %rax     返回值 / 临时计算
    %rbp     栈帧基址指针
    %rsp     栈顶指针

### 6.3 虚函数调用的性能开销

**开销来源：**

1.  **额外内存访问**：两次指针解引用（vptr + 函数指针）
2.  **缓存不友好**：虚表和对象可能不在同一缓存行
3.  **分支预测失败**：间接调用难以预测跳转目标
4.  **内联优化受限**：编译器难以内联虚函数调用

**典型性能对比：**

*   普通函数调用：\~1-2 CPU周期
*   虚函数调用：\~5-10 CPU周期（包含缓存命中）

***

## 七、深入理解：三种函数调用对比

### 7.1 三种调用方式的汇编对比

**1. 虚函数调用（动态绑定）**

```asm
movq    -8(%rbp), %rax      # 加载对象指针
movq    (%rax), %rax        # 读取vptr
movq    (%rax), %rdx        # 读取函数指针
movq    -8(%rbp), %rax      # 重新加载this
movq    %rax, %rdi
call    *%rdx               # 间接调用
```

**2. 普通成员函数调用（静态绑定）**

```asm
movq    -8(%rbp), %rax      # 加载对象指针
movq    %rax, %rdi          # 传递this
call    _ZN4Base10normalFuncEv  # 直接调用
```

**3. 库函数调用（动态链接）**

```asm
leaq    .LC2(%rip), %rax    # 加载字符串地址
movq    %rax, %rsi          # 传递参数
leaq    _ZSt4cout(%rip), %rax
movq    %rax, %rdi
call    _ZStlsISt11char_traitsIcEE...@PLT  # PLT调用
```

### 7.2 PLT（Procedure Linkage Table）机制

`@PLT` 后缀表示通过过程链接表调用，这是动态链接的机制：

*   首次调用时解析符号地址
*   后续调用直接跳转到已解析的地址
*   与虚函数类似，也是间接调用，但解析发生在加载时

***

## 八、实践要点与最佳实践

### 8.1 何时使用虚函数

**适合使用虚函数的场景：**

*   需要运行时多态性
*   通过基类指针/引用操作派生类对象
*   实现接口抽象（纯虚函数）
*   需要动态类型识别（RTTI）

**不适合使用虚函数的场景：**

*   性能关键路径（如游戏引擎的每帧调用）
*   简单的工具类或数据结构
*   不需要继承和多态的类

### 8.2 虚函数使用注意事项

1.  **析构函数应该是虚函数**
    ```cpp
    class Base {
    public:
        virtual ~Base() {}  // 确保正确释放派生类资源
    };
    ```

2.  **构造函数中不要调用虚函数**
    *   构造时vptr尚未完全初始化
    *   调用的是当前类的版本，而非派生类版本

3.  **虚函数不能是static或inline**
    *   static函数没有this指针
    *   inline建议可能被忽略（虚函数难以内联）

### 8.3 编译和查看汇编代码

**生成汇编代码：**

```bash
g++ -S -O0 main.cpp -o main.s          # 无优化
g++ -S -O2 main.cpp -o main_opt.s      # 优化版本
```

**查看符号表：**

```bash
nm a.out | grep virtFunc               # 查看函数符号
objdump -d a.out                       # 反汇编可执行文件
c++filt _ZN7Derived8virtFuncEv         # 解码符号名称
```

***

## 九、总结

### 9.1 核心要点回顾

1.  **虚表机制**
    *   每个包含虚函数的类都有一个虚表（编译时生成）
    *   每个对象都有一个vptr指向其类的虚表（运行时初始化）
    *   虚表存储在只读数据段，所有同类对象共享

2.  **动态绑定实现**
    *   通过两次间接寻址实现：对象→vptr→函数指针
    *   运行时根据对象实际类型调用相应函数
    *   代价是额外的内存访问和性能开销

3.  **汇编层面的关键操作**
    *   对象初始化：`leaq 16+_ZTV7Derived(%rip), %rax` 设置vptr
    *   虚函数调用：`movq (%rax), %rax` → `call *%rdx` 间接调用
    *   普通函数调用：`call 函数地址` 直接调用

### 9.2 从汇编看C++设计哲学

虚函数机制体现了C++的核心设计理念：

*   **零开销原则**：不使用虚函数就不付出代价
*   **性能可控**：开发者可以选择动态绑定或静态绑定
*   **实现透明**：高级特性建立在简单的指针和函数调用之上

通过汇编代码，我们看到了C++多态性的底层实现并不神秘，它只是巧妙地利用了函数指针表和间接调用。理解这些机制，能帮助我们写出更高效、更可维护的代码。

***

## 附录：完整汇编代码注释

### A.1 虚表定义

```asm
_ZTV7Derived:                    # Derived类的虚表
    .quad   0                    # 偏移量（多重继承用）
    .quad   _ZTI7Derived         # RTTI类型信息
    .quad   _ZN7Derived8virtFuncEv  # 虚函数：Derived::virtFunc()
```

### A.2 main函数

```asm
main:
    pushq   %rbp
    movq    %rsp, %rbp
    subq    $16, %rsp

    # 创建Derived对象并初始化vptr
    leaq    16+_ZTV7Derived(%rip), %rax  # 获取虚表函数指针起始地址
    movq    %rax, -16(%rbp)              # 设置对象的vptr

    # 调用testPolymorphism(&d)
    leaq    -16(%rbp), %rax              # 获取对象地址
    movq    %rax, %rdi                   # 作为参数传递
    call    _Z16testPolymorphismP4Base

    movl    $0, %eax                     # 返回0
    leave
    ret
```

### A.3 testPolymorphism函数

```asm
_Z16testPolymorphismP4Base:
    pushq   %rbp
    movq    %rsp, %rbp
    subq    $16, %rsp
    movq    %rdi, -8(%rbp)               # 保存obj指针

    # obj->virtFunc() - 虚函数调用
    movq    -8(%rbp), %rax               # 加载obj
    movq    (%rax), %rax                 # 读取vptr
    movq    (%rax), %rdx                 # 读取第一个虚函数指针
    movq    -8(%rbp), %rax               # 重新加载obj作为this
    movq    %rax, %rdi
    call    *%rdx                        # 间接调用

    # obj->normalFunc() - 普通函数调用
    movq    -8(%rbp), %rax               # 加载obj
    movq    %rax, %rdi                   # 作为this传递
    call    _ZN4Base10normalFuncEv       # 直接调用Base::normalFunc

    # std::cout << "Hello" << std::endl
    leaq    .LC2(%rip), %rax
    movq    %rax, %rsi
    leaq    _ZSt4cout(%rip), %rax
    movq    %rax, %rdi
    call    _ZStlsISt11char_traitsIcEE...@PLT

    leave
    ret
```

***

**参考资料：**

*   C++ ABI规范：<https://itanium-cxx-abi.github.io/cxx-abi/>
*   x86-64 调用约定：System V AMD64 ABI
*   GCC内部实现文档

**编译环境：**

*   编译器：GCC 11.4.0
*   平台：x86-64 Linux
*   编译选项：`g++ -S -O0 main.cpp`
