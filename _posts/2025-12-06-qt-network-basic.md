---
layout: article
title: Qt 网络编程入门：QTcpServer 与 QTcpSocket 基础用法
date: 2025-12-06 10:00:00 +0800
tags:
  - qt
  - net
  - cpp/dev
  - async
---


## 一、引言

TCP（Transmission Control Protocol）是面向连接的可靠传输协议，基于客户端-服务器（Client-Server）模型：

- **服务器（Server）**：监听指定端口，等待客户端连接
- **客户端（Client）**：主动向服务器发起连接请求

Qt 网络模块提供了高层封装：
- **QTcpServer**：用于服务器端，管理连接监听和客户端接入
- **QTcpSocket**：用于客户端和服务器端的数据收发，封装了底层 socket 操作

本文通过实现一个简单的 Echo 服务器和客户端，演示 Qt 网络编程的基础用法。服务器接收客户端发送的消息，并将消息原样返回。

**环境要求：**
- Qt 5.12 或更高版本
- CMake 3.16 或更高版本
- 需要链接 Qt Network 模块


## 二、QTcpSocket 通信流程

典型的客户端-服务器通信流程：

![qtcpsocket](https://noonafter.cn/assets/images/posts/2025-12-06-qt-network-basic/qtcpsocket.png)

## 三、服务器端实现

### 1、核心流程

服务器端的工作流程：
1. **启动监听**：调用 `QTcpServer::listen()` 在指定端口监听
2. **接受连接**：当客户端连接时触发 `newConnection` 信号，使用`nextPendingConnection()`获取 socket 对象
3. **读取数据**：客户端 socket 触发 `readyRead` 信号时读取数据
4. **发送响应**：调用 `QTcpSocket::write()` 发送数据

### 2、头文件定义

```cpp
// echoserver.h
#ifndef ECHOSERVER_H
#define ECHOSERVER_H

#include <QTcpServer>
#include <QTcpSocket>
#include <QList>

class EchoServer : public QObject
{
    Q_OBJECT
public:
    explicit EchoServer(QObject *parent = nullptr);
    bool start(quint16 port);

private slots:
    void onNewConnection();
    void onReadyRead();
    void onDisconnected();

private:
    QTcpServer *m_server;
    QList<QTcpSocket*> m_clients;
};

#endif // ECHOSERVER_H
```

### 3、实现代码

```cpp
// echoserver.cpp
#include "echoserver.h"
#include <QDebug>

EchoServer::EchoServer(QObject *parent)
    : QObject(parent)
    , m_server(new QTcpServer(this))
{
    // 客户端连接时触发 onNewConnection
    connect(m_server, &QTcpServer::newConnection, 
            this, &EchoServer::onNewConnection);
}

bool EchoServer::start(quint16 port)
{
    // 在所有网络接口监听指定端口
    if (!m_server->listen(QHostAddress::Any, port)) {
        qDebug() << "服务器启动失败:" << m_server->errorString();
        return false;
    }
    qDebug() << "服务器启动成功，监听端口:" << port;
    return true;
}

void EchoServer::onNewConnection()
{
    // 获取新连接的客户端 socket 并保存
    QTcpSocket *client = m_server->nextPendingConnection();
    m_clients.append(client);
    
    qDebug() << "新客户端连接:" << client->peerAddress().toString() 
             << ":" << client->peerPort();
    
    // 连接客户端的数据就绪和断开信号
    connect(client, &QTcpSocket::readyRead, 
            this, &EchoServer::onReadyRead);
    connect(client, &QTcpSocket::disconnected, 
            this, &EchoServer::onDisconnected);
}

void EchoServer::onReadyRead()
{
    // sender() 获取触发信号的 socket
    QTcpSocket *client = qobject_cast<QTcpSocket*>(sender());
    if (!client) return;
    
    // 读取所有数据并原样返回（Echo）
    QByteArray data = client->readAll();
    qDebug() << "接收到数据:" << data.size() << "字节";
    client->write(data);
}

void EchoServer::onDisconnected()
{
    QTcpSocket *client = qobject_cast<QTcpSocket*>(sender());
    if (!client) return;
    
    qDebug() << "客户端断开连接:" << client->peerAddress().toString();
    m_clients.removeOne(client);
    client->deleteLater();  // 延迟删除，避免在信号处理期间删除
}
```

## 四、客户端实现

### 1、核心流程

客户端的工作流程：
1. **连接服务器**：调用 `QTcpSocket::connectToHost()`
2. **等待连接成功**：监听 `connected` 信号
3. **发送数据**：连接成功后调用 `write()` 发送数据
4. **接收响应**：监听 `readyRead` 信号并读取数据
5. **错误处理**：监听 `errorOccurred` 信号

### 2、头文件定义

```cpp
// echoclient.h
#ifndef ECHOCLIENT_H
#define ECHOCLIENT_H

#include <QObject>
#include <QTcpSocket>

class EchoClient : public QObject
{
    Q_OBJECT
public:
    explicit EchoClient(QObject *parent = nullptr);
    void connectToServer(const QString &host, quint16 port);
    void sendMessage(const QString &message);

private slots:
    void onConnected();
    void onReadyRead();
    void onDisconnected();
    void onErrorOccurred(QAbstractSocket::SocketError error);

private:
    QTcpSocket *m_socket;
};

#endif // ECHOCLIENT_H
```

### 3、实现代码

```cpp
// echoclient.cpp
#include "echoclient.h"
#include <QDebug>

EchoClient::EchoClient(QObject *parent)
    : QObject(parent)
    , m_socket(new QTcpSocket(this))
{
    // 连接四个关键信号
    connect(m_socket, &QTcpSocket::connected, 
            this, &EchoClient::onConnected);
    connect(m_socket, &QTcpSocket::readyRead, 
            this, &EchoClient::onReadyRead);
    connect(m_socket, &QTcpSocket::disconnected, 
            this, &EchoClient::onDisconnected);
    connect(m_socket, &QTcpSocket::errorOccurred, 
            this, &EchoClient::onErrorOccurred);
}

void EchoClient::connectToServer(const QString &host, quint16 port)
{
    qDebug() << "正在连接服务器:" << host << ":" << port;
    m_socket->connectToHost(host, port);  // 异步连接
}

void EchoClient::sendMessage(const QString &message)
{
    // 检查连接状态
    if (m_socket->state() != QAbstractSocket::ConnectedState) {
        qDebug() << "错误: 未连接到服务器";
        return;
    }
    
    QByteArray data = message.toUtf8();
    m_socket->write(data);
    qDebug() << "发送数据:" << data.size() << "字节";
}

void EchoClient::onConnected()
{
    qDebug() << "连接成功";
    sendMessage("Hello from Qt Client!");
}

void EchoClient::onReadyRead()
{
    QByteArray data = m_socket->readAll();
    qDebug() << "接收到响应:" << QString::fromUtf8(data);
}

void EchoClient::onDisconnected()
{
    qDebug() << "与服务器断开连接";
}

void EchoClient::onErrorOccurred(QAbstractSocket::SocketError error)
{
    qDebug() << "连接错误:" << m_socket->errorString();
}
```

## 五、运行与测试

### 1、main 函数示例

**服务器端：**

```cpp
// main.cpp (服务器)
#include <QCoreApplication>
#include "echoserver.h"

int main(int argc, char *argv[])
{
    QCoreApplication app(argc, argv);
    
    EchoServer server;
    if (!server.start(8888)) {
        return -1;
    }
    
    return app.exec();
}
```

**客户端：**

```cpp
// main.cpp (客户端)
#include <QCoreApplication>
#include "echoclient.h"

int main(int argc, char *argv[])
{
    QCoreApplication app(argc, argv);
    
    EchoClient client;
    client.connectToServer("127.0.0.1", 8888);
    
    return app.exec();
}
```

### 2、编译运行

**CMakeLists.txt：**

```cmake
cmake_minimum_required(VERSION 3.16)
project(EchoServer LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

find_package(Qt5 REQUIRED COMPONENTS Core Network)

# 服务器端
add_executable(server
    server_main.cpp
    echoserver.cpp
    echoserver.h
)
target_link_libraries(server Qt5::Core Qt5::Network)

# 客户端
add_executable(client
    client_main.cpp
    echoclient.cpp
    echoclient.h
)
target_link_libraries(client Qt5::Core Qt5::Network)
```

**编译步骤：**

```bash
mkdir build && cd build
cmake ..
cmake --build .
```

**测试步骤：**

1. 启动服务器：`./server`
2. 启动客户端：`./client`
3. 观察控制台输出

**预期输出：**

服务器端：
```
服务器启动成功，监听端口: 8888
新客户端连接: 127.0.0.1:54321
接收到数据: 22 字节
```

客户端：
```
正在连接服务器: 127.0.0.1:8888
连接成功
发送数据: 22 字节
接收到响应: Hello from Qt Client!
```

## 六、常见问题与处理

### 1、粘包问题

TCP 是字节流协议，不保证应用层消息边界。如果客户端快速发送多条消息，服务器的 `readyRead` 可能一次性读到多条消息合并的数据（粘包），或者一条消息被拆分成多次接收（拆包）。

**解决方案：设计应用层协议**

最简单的协议：**4 字节长度前缀 + 实际数据**

```cpp
// 发送数据（带长度前缀）
void sendMessage(QTcpSocket *socket, const QByteArray &data)
{
    QByteArray packet;
    QDataStream stream(&packet, QIODevice::WriteOnly);
    stream.setVersion(QDataStream::Qt_5_12);
    
    stream << quint32(data.size());  // 写入 4 字节长度
    packet.append(data);             // 追加实际数据
    
    socket->write(packet);
}

// 接收数据（解析长度前缀）
class MessageParser
{
public:
    void appendData(const QByteArray &data) {
        m_buffer.append(data);
    }
    
    QList<QByteArray> parseMessages() {
        QList<QByteArray> messages;
        
        while (m_buffer.size() >= 4) {
            quint32 msgLen;
            QDataStream stream(m_buffer);
            stream.setVersion(QDataStream::Qt_5_12);
            stream >> msgLen;
            
            if (m_buffer.size() < 4 + msgLen) {
                break;  // 数据不完整，等待下次接收
            }
            
            QByteArray message = m_buffer.mid(4, msgLen);
            messages.append(message);
            m_buffer.remove(0, 4 + msgLen);
        }
        
        return messages;
    }

private:
    QByteArray m_buffer;  // 成员变量，保存未处理的数据
};
```

**在服务器端使用：**

```cpp
// 为每个客户端维护一个解析器
QMap<QTcpSocket*, MessageParser*> m_parsers;

void EchoServer::onReadyRead()
{
    QTcpSocket *client = qobject_cast<QTcpSocket*>(sender());
    if (!client) return;
    
    MessageParser *parser = m_parsers[client];
    parser->appendData(client->readAll());
    
    QList<QByteArray> messages = parser->parseMessages();
    for (const QByteArray &msg : messages) {
        qDebug() << "完整消息:" << msg;
        // 处理完整消息
    }
}
```

### 2、错误处理

**服务器端常见错误：**

```cpp
bool EchoServer::start(quint16 port)
{
    if (!m_server->listen(QHostAddress::Any, port)) {
        switch (m_server->serverError()) {
        case QAbstractSocket::AddressInUseError:
            qDebug() << "端口已被占用";
            break;
        case QAbstractSocket::SocketAccessError:
            qDebug() << "权限不足（端口 < 1024 需要管理员权限）";
            break;
        default:
            qDebug() << "服务器启动失败:" << m_server->errorString();
        }
        return false;
    }
    return true;
}
```

**客户端错误处理：**

```cpp
void EchoClient::onErrorOccurred(QAbstractSocket::SocketError error)
{
    switch (error) {
    case QAbstractSocket::ConnectionRefusedError:
        qDebug() << "连接被拒绝（服务器未启动或端口错误）";
        break;
    case QAbstractSocket::RemoteHostClosedError:
        qDebug() << "服务器主动关闭连接";
        break;
    case QAbstractSocket::HostNotFoundError:
        qDebug() << "主机地址无法解析";
        break;
    case QAbstractSocket::NetworkError:
        qDebug() << "网络错误（检查网络连接）";
        break;
    default:
        qDebug() << "错误:" << m_socket->errorString();
    }
}
```

### 3、断线重连

客户端断线后自动重连：

```cpp
class EchoClient : public QObject
{
    // ... 其他代码 ...
private:
    QTimer *m_reconnectTimer;
    QString m_host;
    quint16 m_port;
    int m_reconnectAttempts;
    const int MAX_RECONNECT_ATTEMPTS = 5;
};

EchoClient::EchoClient(QObject *parent)
    : QObject(parent)
    , m_socket(new QTcpSocket(this))
    , m_reconnectTimer(new QTimer(this))
    , m_reconnectAttempts(0)
{
    // ... 原有信号连接 ...
    
    connect(m_reconnectTimer, &QTimer::timeout, this, [this]() {
        if (m_reconnectAttempts < MAX_RECONNECT_ATTEMPTS) {
            m_reconnectAttempts++;
            qDebug() << "尝试重连 (" << m_reconnectAttempts << "/" 
                     << MAX_RECONNECT_ATTEMPTS << ")";
            m_socket->connectToHost(m_host, m_port);
        } else {
            m_reconnectTimer->stop();
            qDebug() << "重连失败，已达到最大重试次数";
        }
    });
}

void EchoClient::connectToServer(const QString &host, quint16 port)
{
    m_host = host;
    m_port = port;
    m_reconnectAttempts = 0;
    m_socket->connectToHost(host, port);
}

void EchoClient::onConnected()
{
    qDebug() << "连接成功";
    m_reconnectAttempts = 0;
    m_reconnectTimer->stop();
    sendMessage("Hello from Qt Client!");
}

void EchoClient::onDisconnected()
{
    qDebug() << "与服务器断开连接，5秒后尝试重连";
    m_reconnectTimer->start(5000);  // 5秒后重连
}
```

## 七、API 参考

### 1、QTcpServer

**关键信号：**
- `newConnection()` - 客户端连接成功时触发，调用 `nextPendingConnection()` 获取 socket
- `acceptError(SocketError)` - 接受连接时发生错误

**关键方法：**
- `listen(QHostAddress, port)` - 开始监听
- `nextPendingConnection()` - 获取等待处理的客户端连接
- `close()` - 停止监听
- `isListening()` - 检查是否正在监听

### 2、QTcpSocket

**关键信号：**
- `connected()` - 连接成功建立
- `disconnected()` - 连接关闭
- `readyRead()` - 接收缓冲区有数据可读，调用 `read()` 或 `readAll()` 读取
- `bytesWritten(qint64)` - 数据写入底层缓冲区，用于跟踪发送进度
- `errorOccurred(SocketError)` - 发生错误
- `stateChanged(SocketState)` - socket 状态变化

**关键方法：**
- `connectToHost(host, port)` - 连接到服务器（异步）
- `write(data)` - 发送数据（异步，先写入内部缓冲区）
- `read(buffer, maxSize)` - 读取指定字节数
- `readAll()` - 读取接收缓冲区的所有数据
- `bytesAvailable()` - 返回接收缓冲区中可读字节数
- `disconnectFromHost()` - 关闭连接
- `abort()` - 立即终止连接（不等待数据发送完成）



## 八、进阶学习

掌握基础用法后，可以深入学习以下主题：

### 1、异步机制的底层原理

**推荐阅读：** [Qt 网络 IO 异步机制：从 epoll 到 readAll 的完整路径](./2025-12-06-qt-network-io-async.md)

深入理解：
- Qt 事件循环如何基于 `epoll` 监听文件描述符
- 为什么 `readyRead` 信号发出时 `readAll()` 不会阻塞
- `QRingBuffer` 内部缓冲区的设计原理
- 多线程场景下的线程安全问题
- 高吞吐场景的性能优化策略

### 2、多线程网络架构

对于高并发服务器，可以采用以下架构：

**主线程 + 工作线程池：**
- 主线程：运行 `QTcpServer`，接受连接
- 工作线程：每个客户端 socket 通过 `moveToThread()` 转移到独立线程处理

**One Loop Per Thread：**
- 每个线程运行独立的事件循环
- 使用 `QThreadPool` 管理线程资源

### 3、其他网络类

Qt 还提供了其他网络组件：
- **QUdpSocket**：UDP 协议通信（无连接、不可靠但低延迟）
- **QSslSocket**：基于 SSL/TLS 的加密通信
- **QNetworkAccessManager**：高层 HTTP/HTTPS 客户端
- **QWebSocket**：WebSocket 协议支持

### 4、实战项目建议

1. **聊天室服务器**：多客户端广播消息，实现用户列表和私聊功能
2. **文件传输工具**：实现大文件分块传输和断点续传
3. **RPC 框架**：设计二进制协议，实现远程过程调用
4. **代理服务器**：实现简单的 HTTP/SOCKS 代理

## 九、总结

本文介绍了 Qt 网络编程的基础用法：

1. **QTcpServer**：用于服务器端，监听端口并接受客户端连接
2. **QTcpSocket**：用于数据收发，通过信号槽实现异步 IO
3. **关键信号**：`newConnection`、`connected`、`readyRead`、`disconnected`、`errorOccurred`
4. **粘包处理**：TCP 字节流需要设计应用层协议（如长度前缀）
5. **错误处理**：监听 `errorOccurred` 信号，根据错误类型采取相应措施
6. **断线重连**：使用 `QTimer` 实现自动重连逻辑

Qt 网络模块封装了底层 socket 操作和事件循环集成，使开发者可以专注于业务逻辑而无需关心异步 IO 的复杂细节。掌握这些基础知识后，可以进一步学习底层原理和高级架构设计。

