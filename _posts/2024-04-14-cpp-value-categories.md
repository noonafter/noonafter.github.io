---
layout: article
title: C++ 值类别详解
date: 2024-04-14 17:11:33 +0800
tags:
  - cpp
  - value-categories
---


## 一、概述

C++ 中每个表达式（运算符及其操作数、字面值、变量名等）都具有一个值类别（value category）。值类别决定了表达式能否取地址、能否进行移动操作。

从 C++11 起，值类别体系基于两个独立属性（有身份，可移动）构建，形成三个基本类别：`lvalue`、`xvalue`、`prvalue`。



## 二、W 模型：两个独立属性

Bjarne Stroustrup 在 ["New Value Terminology"](https://www.stroustrup.com/terminology.pdf) 中提出，值类别由两个相互独立的属性决定：

- **有身份（has identity，记作 `i`）**：表达式可寻址，具有固定内存地址，可判断两个表达式是否指向同一对象。
- **可移动（can be moved from，记作 `m`）**：允许将资源从该表达式的对象转移走，源对象随后处于有效但不确定的状态。

两个属性理论上有四种组合，但"无身份且不可移动"在 C++ 中没有实际用途，因此只保留三种基本类别：

| 组合 | 有身份 | 可移动 | 类别名称 |
|------|--------|--------|----------|
| `iM` | 是 | 否 | **lvalue**（左值） |
| `im` | 是 | 是 | **xvalue**（将亡值） |
| `Im` | 否 | 是 | **prvalue**（纯右值） |

![W-model](https://noonafter.cn/assets/images/posts/2024-04-14-cpp-value-categories/W-model.png)

在 W 模型图示中，`lvalue` 位于左上角，`prvalue` 位于右上角，`xvalue` 位于中间。两个泛化类别由此派生：

- **glvalue**（广义左值）= `lvalue` + `xvalue`，即所有有身份的表达式（`i`）
- **rvalue**（右值）= `xvalue` + `prvalue`，即所有可移动的表达式（`m`）

该设计保留了 C 语言的二元性：每个表达式要么是左值，要么是右值，不能同时属于两者。



## 三、各类别详解

### 1、lvalue（左值）

**定义**：有身份，不可移动。

典型表达式：
- 变量名：`a`、`obj`
- 函数名：`func`
- 解引用表达式：`*p`
- 前置自增/自减：`++i`、`--i`
- 返回左值引用的函数调用：`f()` 其中 `f` 返回 `T&`
- 字符串字面值：`"hello"`（存储于rodata或stack，可取地址）

关键特征：可对其取地址（`&expr` 合法），若对象可修改则可出现在赋值左侧。

### 2、prvalue（纯右值）

**定义**：无身份，可移动。

典型表达式：
- 非字符串字面值：`42`、`3.14`、`true`
- 算术、逻辑、比较表达式：`a + b`、`a && b`、`a == b`
- 返回非引用类型的函数调用：`f()` 其中 `f` 返回 `T`
- 后置自增/自减：`i++`、`i--`
- `this` 指针
- lambda 表达式

关键特征：不可取地址，不对应具体的持久对象。

### 3、xvalue（将亡值）

**定义**：有身份，可移动。表示其资源可被复用的对象。

典型表达式：
- `std::move(x)` 的返回值
- 返回右值引用的函数调用：`f()` 其中 `f` 返回 `T&&`
- 对右值的成员访问：`rval.m`

关键特征：对象仍存在（有地址），但其资源可被转移走，这个类型为C++11新增的类别。

### 4、glvalue 与 rvalue

这两个类别是泛化分组，不直接对应具体表达式，用于语言规则的统一描述：

- **glvalue**：涵盖所有有身份的表达式（`lvalue` + `xvalue`），用于描述"可寻址"的场景，位于W模型左下角。
- **rvalue**：涵盖所有可移动的表达式（`xvalue` + `prvalue`），用于描述"可绑定到右值引用"的场景，位于W模型右下角。



### 5、对比表格

| 类别 | 有身份 | 可移动 | 典型示例 |
|------|--------|--------|----------|
| lvalue | 是 | 否 | 变量名、`*p`、`++i` |
| xvalue | 是 | 是 | `std::move(x)`、返回 `T&&` 的函数调用 |
| prvalue | 否 | 是 | `42`、`a+b`、lambda |
| glvalue | 是 | — | lvalue + xvalue |
| rvalue | — | 是 | xvalue + prvalue |



## 四、右值引用与移动语义

### 1、右值引用

`T&&` 是右值引用类型，用于绑定右值（`xvalue` 或 `prvalue`）。其主要用途是用于标记一个对象为“可移动”，从而触发移动构造函数或移动赋值运算符。

值得注意的是，rvalue可以用T&&绑定，也可以用const T&绑定，但不能用左值引用T&绑定。

```cpp
int i = 42; 
int &r = i;             // 正确: r引用i
int &&rr = i;           // 错误: 不能将一个右值引用绑定到一个左值上
int &r2 = i * 42;       // 错误: i*42是一个右值
const int &r3 = i * 42; // 正确: 可以将一个const的引用绑定到一个右值上
int &&rr2 = i * 42;     // 正确: 将rr2绑定到乘法结果上
```

### 2、移动语义

移动是一种资源转移操作。执行移动后，源对象处于**有效但不确定的状态**：可被赋值和析构，但其内部值不可访问。

```cpp
std::string s1 = "hello";
std::string s2 = std::move(s1); // s1 的资源转移给 s2
// s1 处于有效但不确定的状态，可赋值或析构，但不应访问其值
```

### 3、`std::move` 的适用范围

`std::move` 的本质是将表达式转换为 xvalue，使其可绑定到右值引用，从而触发移动构造或移动赋值。但**实际是否发生移动，取决于目标类型是否定义了移动操作**。

| 类型 | `std::move` 的效果 | 原因 |
|------|-------------------|------|
| 含堆资源的类（`string`、`vector`、`unique_ptr`） | 转移资源所有权，源对象置空 | 定义了移动构造/移动赋值，偷走内部指针 |
| 内置类型（`int`、`double`、裸指针） | 退化为拷贝，无实际效果 | 无内部资源可转移，拷贝与移动的机器码相同 |
| 字符串字面值（`"hello"`） | 无效果 | 字面量位于只读段，无所有权可转移 |
| 未定义移动操作的类 | 静默退化为拷贝 | 编译器找不到移动路径，回退到 `const T&` 重载 |

```cpp
// 有效：string 定义了移动构造
std::string s1 = "hello";
std::string s2 = std::move(s1); // s1 内部指针转移给 s2，s1 变为空串

// 无效：int 无内部资源
int a = 42;
int b = std::move(a); // 等同于 b = a，a 仍为 42

// 退化为拷贝：OldClass 只有拷贝构造
// 根据 C++ 的匹配规则，xvalue可以用const T&绑定。所以编译器会“退而求其次”，调用拷贝构造函数。
struct OldClass {
    std::string data;
    OldClass(const OldClass& other) : data(other.data) {}
};
OldClass x;
OldClass y = std::move(x); // 调用拷贝构造，非移动构造
```

`std::move` 不产生移动动作，只产生移动的可能性。移动动作由目标对象的构造函数或赋值运算符执行。

### 4、有名字的都是左值

C++ 规定：**有名字的表达式是左值**，无论其类型是否为右值引用。这一规则是为了工程安全而人为设定的，而不是通过语义进行推导得到的。例如，在以下代码中，表达式rref是左值

```cpp
int a = 42;
int& lref = a;
int&& rref = std::move(a);

// rref 的类型是 int&&（右值引用），但表达式 rref 本身是左值
// 正确，对 rref 取地址合法：&rref
int *ptr = &rref;

// 错误，使用右值引用绑定rref(左值)
int &&rref2 = rref;
```

这一规则防止对同一具名对象的意外二次移动。若要对具名右值引用再次触发移动，必须显式调用 `std::move()`：

```cpp
void process(std::string&& s) {
    std::string local = std::move(s); // 必须显式 move，否则 s 是左值，触发拷贝
}
```

区分：
- 有名字的右值引用变量（如 `rref`）→ **lvalue**（物理属性：有名字）
- 无名的右值引用（如 `std::move(x)` 的返回值）→ **xvalue**（有身份，可移动）


**经验判断规则**：有名字的表达式是左值；无名字的对象，除 `std::move()` 返回值、返回 `T&&` 的函数调用结果（均为 xvalue）以及字符串字面值（lvalue）外，基本都是 prvalue。



## 五、用 `decltype` 验证值类别

`decltype` 对表达式的处理规则直接反映值类别：

- `decltype(expr)` 其中 `expr` 是 **lvalue** → 推导为 `T&`
- `decltype(expr)` 其中 `expr` 是 **xvalue** → 推导为 `T&&`
- `decltype(expr)` 其中 `expr` 是 **prvalue** → 推导为 `T`

```cpp
int x = 0;

// lvalue：变量名
static_assert(std::is_same_v<decltype((x)), int&>);

// prvalue：字面量
static_assert(std::is_same_v<decltype(42), int>);

// xvalue：std::move 返回值
static_assert(std::is_same_v<decltype(std::move(x)), int&&>);

// 注意：decltype(x) 与 decltype((x)) 不同
// decltype(x)  → int（变量声明类型）
// decltype((x)) → int&（表达式值类别：lvalue）
```



## 六、注意事项

- **字符串字面值是左值**，非字符串字面值（`42`、`true`）是 prvalue。
- **前置 `++i` 是左值**，后置 `i++` 是 prvalue（返回旧值的副本）。
- `std::move()` 不执行任何移动操作，仅将表达式转换为 `xvalue`，实际移动由构造函数或赋值运算符完成。
- 移动后的对象处于有效但不确定的状态，标准库类型（如 `std::string`、`std::vector`）保证可被重新赋值或析构，但不保证具体值。
- 右值引用形参在函数体内是左值，转发时需使用 `std::forward<T>()` 保留原始值类别（完美转发）。


## 参考文章

- [cpprefenence-value_category](https://cppreference.cn/w/cpp/language/value_category)
- [stackoverflow-empirically-determine-value-category-of-c11-expression](https://stackoverflow.com/questions/16637945/empirically-determine-value-category-of-c11-expression/16638081#16638081)
- [new value terminology](https://www.stroustrup.com/terminology.pdf)
