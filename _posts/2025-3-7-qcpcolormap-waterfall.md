---
title: QCPColorMap瀑布图卡顿原因及解决方法
tags: qt, qcustomplot
---

# QCPColorMap绘制瀑布图卡顿原因及解决方案


## 目录
1. [绘图原理解析](#一绘图原理解析)
2. [卡顿解决方案](#二卡顿解决方案)
3. [附录：代码](#附录：代码)


<a id="一绘图原理解析"></a>
## 一、绘图原理解析：从数据到像素
 [`QCPColorMap`](https://www.qcustomplot.com/documentation/classQCPColorMap.html)通过二维数据矩阵生成热力图，支持颜色梯度映射和数据范围动态调整。当数据进行实时更新时，可以用于绘制信号的瀑布图，但当图片尺寸比较大时，QCPColorMap刷新会有明显卡顿。以下从QCPColorMap绘图原理开始，逐步分析卡顿原因，并提出解决方案。下图是最终效果。

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
从updateMapImage()源码中可以发现，计算像素的地方使用的是一个for循环，即for (int line=0; line<lineCount; ++line)
```cpp
// ...
else // keyAxis->orientation() == Qt::Vertical
{
const int lineCount = keySize;
const int rowCount = valueSize;
for (int line=0; line<lineCount; ++line)
{
QRgb* pixels = reinterpret_cast<QRgb*>(localMapImage->scanLine(lineCount-1-line)); 
if (rawAlpha)
mGradient.colorize(rawData+line, rawAlpha+line, mDataRange, pixels, rowCount, lineCount, mDataScaleType==QCPAxis::stLogarithmic);
else
mGradient.colorize(rawData+line, mDataRange, pixels, rowCount, lineCount, mDataScaleType==QCPAxis::stLogarithmic);
}
}
// ...
```
这意味着每当数据变化（如追加一行）触发updateMapImage()，会重新解算ColorMap中的全部数据，如果MapData是一个1000x1000矩阵，则需处理1,000,000次颜色转换，这是导致瀑布图刷新卡顿的主要原因。



<a id="卡顿解决方案"></a>
## 二、卡顿解决方案

根据以上分析可以发现，要解决瀑布图刷新卡顿的关键点在于避免每次修改数据后，重新解算整个ColorMap的数据。在每次输入最新一行数据之后，只需要解算最新输入的数据，其他像素点只需要平移就行。详细代码见附录。

解决方案分为两步：
1. 在QCPColorMapData中提供setCellLatestRow或setDataLatestRow函数，在输入最新行数据的同时，避开对mDataModified的设置

2. 修改数据后提供一个新的解算函数updateMapImageTranslate（需要在setCellLatestRow后手动调用），只解算新入数据，并平移原有像素点，代替updateMapImage。



值得注意的是，setCellLatestRow只会对最新一行数据进行操作，而其他行数据都是最初的状态。如果数据范围变化（setDataRange）或颜色梯度更新（setGradient）后触发原有updateMapImage的流程，对所有数据进行结算，就会导致除了第一行像素，其他行像素均为最初状态。

当然也可以在QCPColorMapData中加上shiftRowsBackward函数将所有数据向后移动一行，空出第一行，然后调用setCellLatestRow修改数据。从而保证在触发原有updateMapImage后，图像任然正常显示，当然这会加大计算量。在工程中应该由用户决定是否接受增加一定计算量，换取在数据范围变化图像正常绘制的功能。


<a id="附录：代码"></a>
## 三、附录：代码
以下代码均QCPColorMap源码和QCPColorMapData源码进行添加和修改。在qcustomplot.h/cpp文件中加上对应代码，即可高效实现上述功能。

```cpp
void QCPColorMapData::setCellLatestRow(int keyIndex, double z)
{
if (keyIndex >= 0 && keyIndex < mKeySize)
{
mData[keyIndex] = z;
} else
qDebug() << Q_FUNC_INFO << "index out of bounds:" << keyIndex;
}
```


```cpp
void QCPColorMap::updateMapImageTranslate()
{
QCPAxis *keyAxis = mKeyAxis.data();
if (!keyAxis) return;
if (mMapData->isEmpty()) return;

const QImage::Format format = QImage::Format_ARGB32_Premultiplied;
const int keySize = mMapData->keySize();
const int valueSize = mMapData->valueSize();
int keyOversamplingFactor = mInterpolate ? 1 : int(1.0+100.0/double(keySize)); // make mMapImage have at least size 100, factor becomes 1 if size > 200 or interpolation is on
int valueOversamplingFactor = mInterpolate ? 1 : int(1.0+100.0/double(valueSize)); // make mMapImage have at least size 100, factor becomes 1 if size > 200 or interpolation is on

// resize mMapImage to correct dimensions including possible oversampling factors, according to key/value axes orientation:
if (keyAxis->orientation() == Qt::Horizontal && (mMapImage.width() != keySize*keyOversamplingFactor || mMapImage.height() != valueSize*valueOversamplingFactor))
mMapImage = QImage(QSize(keySize*keyOversamplingFactor, valueSize*valueOversamplingFactor), format);
else if (keyAxis->orientation() == Qt::Vertical && (mMapImage.width() != valueSize*valueOversamplingFactor || mMapImage.height() != keySize*keyOversamplingFactor))
mMapImage = QImage(QSize(valueSize*valueOversamplingFactor, keySize*keyOversamplingFactor), format);

if (mMapImage.isNull())
{
qDebug() << Q_FUNC_INFO << "Couldn't create map image (possibly too large for memory)";
mMapImage = QImage(QSize(10, 10), format);
mMapImage.fill(Qt::black);
} else
{
QImage *localMapImage = &mMapImage; // this is the image on which the colorization operates. Either the final mMapImage, or if we need oversampling, mUndersampledMapImage
if (keyOversamplingFactor > 1 || valueOversamplingFactor > 1)
{
// resize undersampled map image to actual key/value cell sizes:
if (keyAxis->orientation() == Qt::Horizontal && (mUndersampledMapImage.width() != keySize || mUndersampledMapImage.height() != valueSize))
mUndersampledMapImage = QImage(QSize(keySize, valueSize), format);
else if (keyAxis->orientation() == Qt::Vertical && (mUndersampledMapImage.width() != valueSize || mUndersampledMapImage.height() != keySize))
mUndersampledMapImage = QImage(QSize(valueSize, keySize), format);
localMapImage = &mUndersampledMapImage; // make the colorization run on the undersampled image
} else if (!mUndersampledMapImage.isNull())
mUndersampledMapImage = QImage(); // don't need oversampling mechanism anymore (map size has changed) but mUndersampledMapImage still has nonzero size, free it

const double *rawData = mMapData->mData;
const unsigned char *rawAlpha = mMapData->mAlpha;
if (keyAxis->orientation() == Qt::Horizontal)
{
const int lineCount = valueSize;
const int rowCount = keySize;

//vertically translate image pixels
for (int y = 1; y < lineCount; ++y) {
    const uchar *sourceLine = localMapImage->constScanLine(y);
    uchar *targetLine = localMapImage->scanLine(y - 1);
    memmove(targetLine, sourceLine, localMapImage->bytesPerLine());
}

for (int line=0; line<1; ++line)
{
QRgb* pixels = reinterpret_cast<QRgb*>(localMapImage->scanLine(lineCount-1-line)); // invert scanline index because QImage counts scanlines from top, but our vertical index counts from bottom (mathematical coordinate system)
if (rawAlpha)
mGradient.colorize(rawData+line*rowCount, rawAlpha+line*rowCount, mDataRange, pixels, rowCount, 1, mDataScaleType==QCPAxis::stLogarithmic);
else
mGradient.colorize(rawData+line*rowCount, mDataRange, pixels, rowCount, 1, mDataScaleType==QCPAxis::stLogarithmic);
}

} else // keyAxis->orientation() == Qt::Vertical
{
const int lineCount = keySize;
const int rowCount = valueSize;

//horizontally translate image pixels
int bytesPerPixel = localMapImage->depth() / 8;
for (int y = 0; y < lineCount; ++y) {
    uchar *line = localMapImage->scanLine(y);
    memmove(line + bytesPerPixel, line, (rowCount - 1) * bytesPerPixel);
}

//colorize to a QRgb* pixels[rowCount]
QRgb pixels[lineCount];
for (int line=0; line<1; ++line)
{
if (rawAlpha)
mGradient.colorize(rawData+line*rowCount, rawAlpha+line*rowCount, mDataRange, pixels, lineCount, 1, mDataScaleType==QCPAxis::stLogarithmic);
else
mGradient.colorize(rawData+line*rowCount, mDataRange, pixels, lineCount, 1, mDataScaleType==QCPAxis::stLogarithmic);
}

//set pixels at x=0, y=0:lineCount-1
for (int y = 0; y < lineCount; ++y)
{
    localMapImage->setPixel(0, y, pixels[y]);
}

}

if (keyOversamplingFactor > 1 || valueOversamplingFactor > 1)
{
if (keyAxis->orientation() == Qt::Horizontal)
mMapImage = mUndersampledMapImage.scaled(keySize*keyOversamplingFactor, valueSize*valueOversamplingFactor, Qt::IgnoreAspectRatio, Qt::FastTransformation);
else
mMapImage = mUndersampledMapImage.scaled(valueSize*valueOversamplingFactor, keySize*keyOversamplingFactor, Qt::IgnoreAspectRatio, Qt::FastTransformation);
}
}
mMapData->mDataModified = false;
mMapImageInvalidated = false;
}

```

```cpp
void QCPColorMapData::shiftRowsBackward(int shiftCount)
{
memmove(mData + shiftCount * mKeySize, mData, mKeySize * (mValueSize - shiftCount) * sizeof(mData[0]));
}
```