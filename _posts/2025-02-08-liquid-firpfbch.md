---
title: liquid源码分析之二：firpfbch
tags: liquid
---

## 概述
liquid库中多相信道器包括三个源文件，分别是
- firpfbch.proto.c，最大抽取多相信道器，M/P=1
- firpfbch2.proto.c，半抽取多相信道器，M/P=2
- firpfbchr.proto.c，有理数过采样多相信道器，M/P=rational

其中，M为通道个数，P为抽取/内插倍数，firpfbch和firpfbch2使用时都需要先指明类型，这是因为两者都实现了synthesizer和analyzer，因此在_create时需要指定类型，而firpfbchr只实现了analyzer，因此不需要指定类型（M/P=有理数时很难实现synthesizer，而且应用的意义不大）

本文对最大抽取多相信道器firpfbch进行说明。

<!--more-->

## 使用示例

```c
   // create filterbank objects from prototype
    firpfbch_crcf q = firpfbch_crcf_create(LIQUID_ANALYZER, num_channels, 2*m, h);

    // channelize input data
    for (i=0; i<num_frames; i++) {
        // execute analysis filter bank
        firpfbch_crcf_analyzer_execute(q, &x[i*num_channels], &y[i*num_channels]);
    }

    // destroy channelizer object
    firpfbch_crcf_destroy(q);
```

- 第一步：使用firpfbch_crcf_create创建多相信道器对象，并返回一个firpfbch_crcf_s *指针，这里注意第三个参数为子滤波器长度（firpfbch2和r中为滤波器长度一半）
- 第二步：使用firpfbch_crcf_analyzer_execute或firpfbch_crcf_synthesizer_execute执行一次，输入M个点，输出M个点。
- 第三步：使用完毕后，使用firpfbch_crcf_destroy销毁对象。

## 源码分析

### firpfbch_crcf_s结构体

```c
// firpfbch object structure definition
struct FIRPFBCH(_s) {
    int type;                   // synthesis/analysis
    unsigned int num_channels;  // number of channels
    unsigned int p;             // filter length (symbols)

    // filter
    unsigned int h_len;         // filter length
    TC * h;                     // filter coefficients
    
    // create separate bank of dotprod and window objects
    DOTPROD() * dp;             // dot product object array
    WINDOW() * w;               // window buffer object array
    unsigned int filter_index;  // running filter index (analysis)

    // fft plan
    FFT_PLAN fft;               // fft|ifft object
    TO * x;                     // fft|ifft transform input array
    TO * X;                     // fft|ifft transform output array
};
```
可以看出，firpfbch_crcf_s结构体内部，保存了多相信道器的参数和相关变量，并用到了滑动窗WINDOW()和点积DOTPROD()来完成滤波器组的操作，并且包含fft相关对象。

### firpfbch_crcf_create函数

```c
// create FIR polyphase filterbank channelizer object
//  _type   : channelizer type (LIQUID_ANALYZER | LIQUID_SYNTHESIZER)
//  _M      : number of channels
//  _p      : filter length (symbols)
//  _h      : filter coefficients, [size: _M*_p x 1]
FIRPFBCH() FIRPFBCH(_create)(int          _type,
                             unsigned int _M,
                             unsigned int _p,
                             TC *         _h)
{
    // 校验输入
if (_type != LIQUID_ANALYZER && _type != LIQUID_SYNTHESIZER)
    return liquid_error_config("firpfbch_%s_create(), invalid type: %d", EXTENSION_FULL, _type);
if (_M == 0)
    return liquid_error_config("firpfbch_%s_create(), number of channels must be greater than 0", EXTENSION_FULL);
if (_p == 0)
    return liquid_error_config("firpfbch_%s_create(), invalid filter size (must be greater than 0)", EXTENSION_FULL);

    // 分配主对象内存
    FIRPFBCH() q = (FIRPFBCH()) malloc(sizeof(struct FIRPFBCH(_s)));

    // 设置相关参数
    q->type         = _type;
    q->num_channels = _M;
    q->p            = _p;

    q->h_len = q->num_channels * q->p;

    // 分配M个WINDOW和DOTPROD对象指针的内存
    q->dp = (DOTPROD()*) malloc((q->num_channels)*sizeof(DOTPROD()));
    q->w  = (WINDOW()*)  malloc((q->num_channels)*sizeof(WINDOW()));

    // 拷贝滤波器系数
    q->h = (TC*) malloc((q->h_len)*sizeof(TC));
    unsigned int i;
    for (i=0; i<q->h_len; i++)
        q->h[i] = _h[i];

    // 生成滤波器组中的M个子滤波器系数
    unsigned int n;
    unsigned int h_sub_len = q->p;
    TC h_sub[h_sub_len];
    for (i=0; i<q->num_channels; i++) {
        // sub-sample prototype filter, loading coefficients in reverse order
        for (n=0; n<h_sub_len; n++) {
            h_sub[h_sub_len-n-1] = q->h[i + n*(q->num_channels)];
        }
        // 创建WINDOW和DOTPROD对象
        q->dp[i] = DOTPROD(_create)(h_sub,h_sub_len);
        q->w[i]  = WINDOW(_create)(h_sub_len);
    }

    // 分配FFT的输入输出内存
    q->x = (T*) FFT_MALLOC((q->num_channels)*sizeof(T));
    q->X = (T*) FFT_MALLOC((q->num_channels)*sizeof(T));

    // 创建fftplan，这里其实有点问题，无论synthesizer还是analysiser，都只用FFT_DIR_BACKWARD就行，对应了后面analysiser进行fft时，输入反序，因此做的也是ifft
    if (q->type == LIQUID_ANALYZER)
        q->fft = FFT_CREATE_PLAN(q->num_channels, q->X, q->x, FFT_DIR_FORWARD, FFT_METHOD);
    else
        q->fft = FFT_CREATE_PLAN(q->num_channels, q->X, q->x, FFT_DIR_BACKWARD, FFT_METHOD);

    // reset filterbank object
    FIRPFBCH(_reset)(q);

    // return filterbank object
    return q;
}
```

可以看出，firpfbch_crcf_create函数不仅会分配firpfbch_crcf_s结构体内存，初始化相关参数，还会逐个创建要用到的对象，总的来说，_create函数会进行根据用户输入参数分配内存、初始化对象，并返回对象指针。

### _analyzer_execute函数

```c
int FIRPFBCH(_analyzer_execute)(FIRPFBCH() _q,
                                TI *       _x,
                                TO *       _y)
{
    unsigned int i;

    // 将输入M个点分别push到M个滑动窗中，等待进行滤波
    for (i=0; i<_q->num_channels; i++)
        FIRPFBCH(_analyzer_push)(_q, _x[i]);

    // 执行多相滤波和fft
    return FIRPFBCH(_analyzer_run)(_q, 0, _y);
}
```

### _analyzer_push源码
```c
// push single sample into analysis filterbank, updating index
// counter appropriately
//  _q      :   filterbank channelizer object
//  _x      :   input sample
int FIRPFBCH(_analyzer_push)(FIRPFBCH() _q,
                             TI         _x)
{
    // push sample into filter
    WINDOW(_push)(_q->w[_q->filter_index], _x);

    // decrement filter index
    _q->filter_index = (_q->filter_index + _q->num_channels - 1) % _q->num_channels;
    return LIQUID_OK;
}
```

### _analyzer_run源码
```c
// run filterbank analyzer dot products, DFT
//  _q      :   filterbank channelizer object
//  _k      :   filterbank alignment index
//  _y      :   output array, [size: num_channels x 1]
int FIRPFBCH(_analyzer_run)(FIRPFBCH()   _q,
                            unsigned int _k,
                            TO *         _y)
{
    unsigned int i;

    // execute filter outputs, reversing order of output (not
    // sure why this is necessary)
    // 这里将fft的输入反向放入，相当于执行ifft
    T * r;  // read pointer
    unsigned int index;
    for (i=0; i<_q->num_channels; i++) {
        // compute appropriate index
        index = (i+_k) % _q->num_channels;

        // read buffer at specified index
        WINDOW(_read)(_q->w[index], &r);

        // compute dot product
        DOTPROD(_execute)(_q->dp[i], r, &_q->X[_q->num_channels-i-1]);
    }

    // execute DFT, store result in buffer 'x'
    FFT_EXECUTE(_q->fft);

    // move to output array
    memmove(_y, _q->x, _q->num_channels*sizeof(TO));
    return LIQUID_OK;
}
```


### _synthesizer_execute源码
```c
// execute filterbank as synthesizer on block of samples
//  _q      :   filterbank channelizer object
//  _x      :   channelized input, [size: num_channels x 1]
//  _y      :   output time series, [size: num_channels x 1]
int FIRPFBCH(_synthesizer_execute)(FIRPFBCH() _q,
                                   TI *       _x,
                                   TO *       _y)
{
    unsigned int i;

    // 将输入复制到ifft的输入buffer
    memmove(_q->X, _x, _q->num_channels*sizeof(TI));

    // 执行ifft
    FFT_EXECUTE(_q->fft);

    // 将ifft结果存入M个滑动窗，执行M次点积
    T * r;      // read pointer
    for (i=0; i<_q->num_channels; i++) {
        WINDOW(_push)(_q->w[i], _q->x[i]);
        WINDOW(_read)(_q->w[i], &r);
        DOTPROD(_execute)(_q->dp[i], r, &_y[i]);

        // normalize by DFT scaling factor
        //_y[i] /= (float) (_q->num_channels);
    }
    return LIQUID_OK;
}
```

## 原理
最大抽取多相信道器的原理较为简单，核心思想是通过多相分解和Noble Identity的等效结构，将滤波器组的设计和实现简化为更高效的形式，下面对analyzer和synthesizer的原理进行简要说明，详细原理参考论文[Digital Receivers and Transmitters Using Polyphase Filter Banks for Wireless Communications](https://ieeexplore.ieee.org/document/1193158)。

### 结构1
传统信道器原理如下图所示，每一路都是下变频、基带滤波器和抽取M三部分构成
![conventional channelizer](https://noonafter.cn/assets/images/posts/2025-02-08-liquid-firpfbch/conventional_channelizer.png)

以第k路通道为例，原始结构（结构1）如下图所示。
![chk struct1](https://noonafter.cn/assets/images/posts/2025-02-08-liquid-firpfbch/chk_struct1.png)
$x(n)$为接收到的信号，$\theta_k=\frac{2\pi k}{M}$，要求fk/fsa=k/M，
下变频、滤波后的信号为

$$\begin{aligned}y(n,k)&=\left[x(n)e^{-j\theta_kn}\right]*h(n)\\&=\sum_{r=0}^{N-1}x(n-r)e^{-j\theta_k(n-r)}h(r).\end{aligned}$$


### 结构2
将以上公式展开，

$$\begin{aligned}y(n,k)&\begin{aligned}&=\sum_{r=0}^{N-1}x(n-r)e^{-j(n-r)\theta_k}h(r)\end{aligned}\\&=\sum_{r=0}^{N-1}x(n-r)e^{-jn\theta_k}h(r)e^{jr\theta_k}\\&=e^{-jn\theta_k}\sum_{r=0}^{N-1}x(n-r)h(r)e^{jr\theta_k}.\end{aligned}$$


可以得到，与结构1等价的结构2：
![alt text](https://noonafter.cn/assets/images/posts/2025-02-08-liquid-firpfbch/chk_struct2.png)

即下变频+低通滤波等价于带通滤波+下变频，带通滤波器$h(n)e^{j\theta_k n}$对应的Z变换为$H(Ze^{-j\theta_k})$。注意，结构1和2的等价并不涉及抽取操作。


### 结构3
抽取之后，公式中下变频$e^{-j\theta_k n}$都变成$e^{-j\theta_k Mn}$，这说明只需要对抽取后的信号进行下变频即可，可以得到结构3

![alt text](https://noonafter.cn/assets/images/posts/2025-02-08-liquid-firpfbch/chk_struct3.png)

### 结构4
由于$\theta_k=\frac{2\pi k}{M}$，则$e^{-j\theta_k Mn}=1$，因此这里下变频可以忽略，可以得到结构4

![alt text](https://noonafter.cn/assets/images/posts/2025-02-08-liquid-firpfbch/chk_struct4.png)

### 结构5
这里暂时将带通滤波器$h(n)e^{j\theta_k n}$视为一个普通的滤波器$h(n)$，并将这个滤波器写为多相滤波器的形式（任意FIR滤波器都能够写成多相的形式，本质是加法的结合律）

![alt text](https://noonafter.cn/assets/images/posts/2025-02-08-liquid-firpfbch/chk_struct5.png)

$$
H(Z) = \begin{array}{ccccc}
h(0) & + & h(M+0)Z^{-M} & + & h(2M+0)Z^{-(2M+0)} & + & \cdots \\
h(1)Z^{-1} & + & h(M+1)Z^{-(M+1)} & + & h(2M+1)Z^{-(2M+1)} & + & \cdots \\
h(2)Z^{-2} & + & h(M+2)Z^{-(M+2)} & + & h(2M+2)Z^{-(2M+2)} & + & \cdots \\
h(3)Z^{-3} & + & h(M+3)Z^{-(M+3)} & + & h(2M+3)Z^{-(2M+3)} & + & \cdots \\
\vdots & \vdots & \vdots & \vdots & \vdots & \vdots \\
h(M-1)Z^{-(M-1)} & + & h(2M-1)Z^{-(2M-1)} & + & h(3M-1)Z^{-(3M-1)} & + & \cdots
\end{array}\\= H_0(Z^M) + Z^{-1}H_1(Z^M) + Z^{-2}H_2(Z^M) + \cdots + Z^{-(M-1)}H_{M-1}(Z^M)
$$


### 结构6
令$h(n) = h(n)e^{j\theta_k n}$代入多相滤波器中，


$$
G(Z) = H(Z) \bigg|_{Z = e^{-j\theta_k} Z} = H(e^{-j\theta_k} Z)
$$

可以得到带通滤波器的多相结构

![alt text](https://noonafter.cn/assets/images/posts/2025-02-08-liquid-firpfbch/chk_struct6.png)

### 结构7 
利用[noble identity](https://www.dsprelated.com/freebooks/sasp/Multirate_Noble_Identities.html)，将抽取和滤波操作互换位置，可以得到结构7。这里抽取和延迟可以一起看成一个换向器，数据从最下方开始添加。

![alt text](https://noonafter.cn/assets/images/posts/2025-02-08-liquid-firpfbch/chk_struct7.png)

输出的$y(nM,k)$只是第k通道的数据，可以表示为

$$
y(nM,k)=\sum_{r=0}^{M-1}y_r(nM)e^{j\left(2\pi/M\right)rk}.
$$

对于通道k来说，每一个支路上乘以的$e^{jrk\frac{2\pi}{M}}$都是一个常数，如果只想要某个通道上的数据，完全可以只利用结构7来进行实现。如果需要将M个通道的数据全部输出出来，刚好可以利用IFFT的操作来计算以上公式，从而同时获得M个通道的输出。准确来说，下图中$IFFT$应该是$ M\cdot IFFT$

![alt text](https://noonafter.cn/assets/images/posts/2025-02-08-liquid-firpfbch/chs.png)



### 值得注意的问题
在_analyzer_run函数源码中，将滤波器输出的值进行了反序，然后送入了fft，最后的结果完全等于$e^{j2\pi k/M} \cdot M \cdot ifft$，多出来的相位旋转因子$e^{j2\pi k/M}$可以看成是k通道上下变频载波的延迟（参考结构1），不影响信号正确性。

将_analyzer_run函数源码中的操作用框图表示如下

![alt text](https://noonafter.cn/assets/images/posts/2025-02-08-liquid-firpfbch/chs_fft.png)


## 关于fft的理解
从线性代数的角度，fft可以视为正交投影或者基变换。根据以上原理，也可以从多相信道器的角度来理解FFT以及加窗FFT。FFT操作实际上可以理解为一个滤波器组，这一组滤波器基于同一个原型滤波器，即时域为M点矩形，频域为sinc函数的滤波器。


假设输入信号的采样率为192KHz，执行8点FFT，则对应的滤波器组幅度响应如下图所示。

![alt text](https://noonafter.cn/assets/images/posts/2025-02-08-liquid-firpfbch/chs_hh.png)

从多相信道器的观点来看FFT，可以得到以下结论

- FFT等效于一个sinc滤波器组：FFT的每个频率bin可视为一个带通滤波器，这一组滤波器基于同一个原型滤波器，时域为矩形窗，幅度响应为sinc函数。

- 通道重叠：FFT的频率分辨率为Δf=fsa/N，即通道之间频率间隔fsep=Δf=fsa/N，而单通道幅度响应为sinc函数，其主瓣宽度为2Δf，这导致通道间存在重叠，通道的重叠现象在加窗之后仍然存在（加窗只是加快旁瓣衰减，主瓣宽度仍然为2Δf）。并且sinc函数通带内幅度变换太大，无法直接使用fft或加窗fft来进行通道划分。

- sinc函数旁瓣的影响：sinc函数的高旁瓣（第一旁瓣约为-13 dB）和慢衰减（按 1/ω 衰减）会使得强信号的能量泄漏到其他通道，导致弱信号被掩盖或误判。如果信号频率未对齐频率bin中心（即非整周期采样），泄漏现象会加剧，导致能量扩散到多个bin中。


由于sinc函数旁瓣的影响，原始FFT（无窗函数或其他处理）不适合高精度频谱监测，尤其在存在强信号时。改进方法：

- 加窗处理：使用汉宁窗（Hanning）、汉明窗（Hamming）或凯瑟窗（Kaiser）等窗函数，显著降低旁瓣（例如汉宁窗第一旁瓣为-31 dB），减少泄漏。

- 重叠采样：通过重叠FFT块（如50%重叠）提高频谱估计的平滑性和准确性。

- 平均处理：对多次FFT结果进行平均，抑制噪声和瞬时干扰。

- 高动态范围技术：结合峰值检测和插值算法，提高频率和幅值分辨率。


以下为加上hanning窗后的滤波器组的幅度响应。
![alt text](https://noonafter.cn/assets/images/posts/2025-02-08-liquid-firpfbch/chs_hanning.png)

可以发现，加窗虽然会使得旁瓣衰减加快，但会导致主瓣宽度增加，从而降低频率分辨率。因此，要得到高精度的频谱监视器，还是需要使用多相信道器，但原型滤波器依然会导致计算复杂度以及信号延迟的增加。







