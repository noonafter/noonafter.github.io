---
layout: article
title: nullptr：类型安全的空指针常量
date: 2024-04-03 10:00:00 +0800
tags:
  - cpp/basic
---


## 一、nullptr 的类型

`nullptr` 是 C++11 引入的字面值常量，用于表示空指针。与所有字面值常量一样，`nullptr` 具有明确的类型：`std::nullptr_t`。

`std::nullptr_t` 是 C++ 的基础类型之一，定义在 `<cstddef>` 头文件中。该类型具有以下特性：

- **隐式转换为任意指针类型**：`nullptr` 可以隐式转换为 `int*`、`char*`、`void*` 等任何指针类型
- **不能转换为整数类型**：`nullptr` 无法转换为 `int`、`long` 等整数类型，这保证了类型安全

这种设计使 `nullptr` 成为真正意义上的"万能空指针"——它可以赋值给任何指针类型的变量，但不会与整数类型混淆。

## 二、NULL 在 C++ 中的问题

在 C++11 之前，程序员使用 `NULL` 或 `0` 来表示空指针。当指针在初始化或赋值时暂时不知道指向的内存地址（注意这与不知道指针指向的对象类型是两个不同的问题），通常会写：

```cpp
int *p = NULL;
```

这种用法继承自 C 语言。然而，`NULL` 在 C 和 C++ 中的定义存在差异：

- **C 语言**：`NULL` 通常定义为 `(void*)0`
- **C++ 语言**：`NULL` 通常定义为整数常量 `0`

C++ 中 `NULL` 被定义为整数的原因是 C++ 不允许 `void*` 隐式转换为其他指针类型。这一差异在 C++ 的函数重载机制下引发了严重的语义模糊问题。

## 三、函数重载中的歧义

C++ 支持函数重载，允许同名函数接受不同类型的参数。当存在接受整数和指针的重载函数时，使用 `NULL` 会导致编译器无法确定调用哪个版本：

```cpp
#include <iostream>

void f(int a) {
    std::cout << "f(int)" << std::endl;
}

void f(char *b) {
    std::cout << "f(char*)" << std::endl;
}

int main() {
    f(NULL);    // error: call of overloaded 'f(NULL)' is ambiguous
    f(0);       // 调用 f(int)
    f(nullptr); // nullptr_t 隐式转换为 char*，调用 f(char*)
}
```

**问题分析**：

- `f(NULL)`：由于 `NULL` 是整数常量 `0`，编译器无法判断应该调用 `f(int)` 还是 `f(char*)`，产生歧义错误
- `f(0)`：明确传递整数，调用 `f(int)`
- `f(nullptr)`：`nullptr` 的类型是 `std::nullptr_t`，只能转换为指针类型，因此明确调用 `f(char*)`

这个例子清晰展示了 `nullptr` 的核心价值：**消除空指针表示在函数重载中的语义歧义**。

## 四、nullptr 的转换规则

`nullptr` 的类型转换遵循严格的规则：

### 1、指针类型转换

`nullptr` 可以隐式转换为任何指针类型：

```cpp
int *p1 = nullptr;       // 转换为 int*
char *p2 = nullptr;      // 转换为 char*
double *p3 = nullptr;    // 转换为 double*
```
如果有一个指针，在初始化或者赋值的时候暂时不知道指向内存哪里（注意这和指针指向什么类型是两个问题），那么可以先赋nullptr。

### 2、泛型指针转换

当不知道指针指向的对象类型时，可以使用泛型指针 `void*`。`void*` 与 `nullptr` 可以结合使用：

```cpp
void *p = nullptr;
```

**注意**：即使写成 `void *p = nullptr`，也会发生隐式类型转换——将 `std::nullptr_t` 转换为 `void*`。这不是简单的赋值，而是类型系统层面的转换。

### 3、整数类型转换

`nullptr` **不能**转换为整数类型：

```cpp
int x = nullptr;        // 编译错误
long y = nullptr;       // 编译错误
bool b = (nullptr);     // 可以转换为 bool（结果为 false）
```

唯一的例外是 `bool` 类型：`nullptr` 可以转换为 `false`，这符合空指针在条件判断中的语义。

## 五、使用建议

### 1、优先使用 nullptr

在 C++11 及以后的代码中，应始终使用 `nullptr` 而非 `NULL` 或 `0` 来表示空指针：

```cpp
// 推荐
int *p = nullptr;

// 不推荐
int *p = NULL;
int *p = 0;
```

### 2、类型安全优势

`nullptr` 提供了编译期类型检查，避免了指针与整数的混淆：

```cpp
void process(int *ptr);

process(0);       // 可以编译，但语义不清晰
process(nullptr); // 明确表示传递空指针
```

### 3、模板编程中的优势

在模板代码中，`nullptr` 能够正确推导为指针类型，而 `NULL` 会被推导为整数：

```cpp
template<typename T>
void func(T param);

func(NULL);    // T 被推导为 int
func(nullptr); // T 被推导为 std::nullptr_t
```

## 六、总结

`nullptr` 的引入解决了 C++ 中空指针表示的历史遗留问题：

- **类型明确**：`std::nullptr_t` 是独立的基础类型
- **转换安全**：只能转换为指针类型，不能转换为整数
- **语义清晰**：在函数重载中消除歧义
- **向后兼容**：可以与 `void*` 等传统指针类型无缝配合

在现代 C++ 代码中，`nullptr` 应作为表示空指针的唯一选择。
