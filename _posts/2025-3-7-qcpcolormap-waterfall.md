---
title: QCPColorMap瀑布图卡顿原因及解决方法
tags: qt,qcustomplot
---

# QCPColorMap绘制瀑布图卡顿原因及解决方案

---

## 目录
1. [绘图原理解析](#一绘图原理解析)
2. [卡顿解决方案](#二卡顿解决方案)


---

<a id="一绘图原理解析"></a>
## 一、绘图原理解析：从数据到像素
 [`QCPColorMap`](https://www.qcustomplot.com/documentation/classQCPColorMap.html)通过二维数据矩阵生成热力图，支持颜色梯度映射和数据范围动态调整。当数据进行实时更新时，可以用于绘制信号的瀑布图，但当图片尺寸比较大时，QCPColorMap刷新会有明显卡顿。以下从QCPColorMap绘图原理开始，逐步分析卡顿原因，并提出解决方案。

### 1. 核心成员
QCPColorMap类中有几个关键的成员变量：mMapData（存储颜色映射数据）、mGradient（颜色梯度）、mMapImage（存储生成的图像），如下所示。
| 成员 | 类型 | 核心作用 |
|---------------|---------------------|--------------------------------------------------------------------------|
| `mMapData` | `QCPColorMapData*` | 存储原始数据矩阵及空间元数据（尺寸/范围） |
| `mGradient` | `QCPColorGradient` | 定义数值到颜色的转换规则（梯度插值/周期模式） |
| `mMapImage` | `QImage` | 缓存渲染图像（ARGB32格式），支持过采样抗锯齿 |

```cpp
// 数据存储结构示意
class QCPColorMapData {
double* mData; // 一维数组存储二维数据（行优先）
QCPRange mKeyRange; // X轴映射范围
QCPRange mValueRange; // Y轴映射范围
int mKeySize, mValueSize;// 矩阵维度
};
```

### 2. 绘制流程

查看QCPColorMap::draw函数中关于图像更新的代码如下，
```cpp
// 条件检查：数据是否变化需要更新图像
if (mMapData->mDataModified || mMapImageInvalidated)
    updateMapImage();
```

如果数据发生更改或者因为其他原因导致mMapImage失效（比如调用setDataRange重新设置映射数据范围），则调用updateMapImage()进行图像更新。

updateMapImage()是将数据转化为像素的核心函数，其通过遍历内部QCPColorMapData，并使用QCPColorGradient::colorize将数据值转换为颜色像素。发生下列情况，都会导致updateMapImage的调用：
 * 数据修改（setData/setCell）
 * 数据范围变化（setDataRange）
 * 颜色梯度更新（setGradient）

### 3. 卡顿原因
从updateMapImage()源码中可以发现，计算像素的地方使用的是一个for循环
```cpp
for (int line=0; line<valueSize; ++line)
```
这意味着每当数据变化（如追加一行）触发updateMapImage()，会重新解算ColorMap中的全部数据，如果MapData是一个1000x1000矩阵，则需处理1,000,000次颜色转换，这是导致瀑布图刷新卡顿的主要原因。


---



<a id="卡顿解决方案"></a>
## 二、卡顿解决方案

根据以上分析可以发现，要解决瀑布图刷新卡顿的关键点在于避免每次修改数据后，重新解算整个ColorMap的数据。在每次输入最新一行数据之后，只需要解算最新输入的数据，其他像素点只需要平移就行。

