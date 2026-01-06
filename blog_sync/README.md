# 博客同步工具

将Jekyll博客文章同步到CSDN和博客园的命令行工具。

## 功能特性

- ✅ 支持同步到博客园（使用MetaWeblog API）
- ✅ 支持同步到CSDN（使用Selenium自动化）
- ✅ 自动解析Jekyll格式的Markdown文件
- ✅ 支持文章标题、内容、标签、分类
- ✅ 命令行操作，简单易用

## 环境要求

- Python 3.6+
- Chrome浏览器（用于CSDN同步）
- ChromeDriver（与Chrome版本匹配）

## 安装步骤

### 1. 安装Python依赖

```bash
pip install selenium
```

注意：博客园使用的xmlrpc.client是Python标准库，无需额外安装。

### 2. 安装ChromeDriver

**Ubuntu/Debian:**
```bash
sudo apt-get install chromium-chromedriver
```

**macOS:**
```bash
brew install chromedriver
```

**Windows:**
从 [ChromeDriver官网](https://chromedriver.chromium.org/) 下载对应版本，并添加到PATH。

### 3. 配置账号信息

复制配置文件模板并填写你的账号信息：

```bash
cd blog_sync
cp config.example.json config.json
```

编辑 `config.json`，填写你的账号信息：

```json
{
  "cnblogs": {
    "enabled": true,
    "username": "你的博客园用户名",
    "password": "你的博客园密码"
  },
  "csdn": {
    "enabled": true,
    "username": "你的CSDN用户名",
    "password": "你的CSDN密码",
    "headless": false
  }
}
```

**配置说明：**
- `enabled`: 是否启用该平台的同步
- `headless`: (仅CSDN) 是否使用无头模式（不显示浏览器窗口）

## 使用方法

### 基本用法

同步单篇文章到所有平台：

```bash
python3 blog_sync/sync.py _posts/2025-12-10-gnuradio-custom-module.md
```

### 高级选项

**仅同步到博客园：**
```bash
python3 blog_sync/sync.py _posts/your-article.md --cnblogs-only
```

**仅同步到CSDN：**
```bash
python3 blog_sync/sync.py _posts/your-article.md --csdn-only
```

**使用自定义配置文件：**
```bash
python3 blog_sync/sync.py _posts/your-article.md --config my-config.json
```

## 工作流程

### 博客园同步流程

1. 工具自动解析Jekyll格式的Markdown文件
2. 提取标题、内容、标签、分类
3. 通过MetaWeblog API自动发布到博客园
4. 显示发布结果和文章ID

### CSDN同步流程

1. 工具自动打开Chrome浏览器
2. 自动填写用户名和密码
3. **需要手动完成验证码验证**
4. 登录成功后自动打开写文章页面
5. 自动填写标题和内容
6. **需要手动添加标签、选择分类并点击发布**

## 注意事项

1. **博客园配置**：首次使用前需要在博客园后台开启MetaWeblog API访问权限
2. **CSDN验证码**：由于CSDN有验证码保护，需要手动完成验证
3. **密码安全**：config.json包含敏感信息，请勿提交到Git仓库
4. **ChromeDriver版本**：确保ChromeDriver版本与Chrome浏览器版本匹配

## 项目结构

```
blog_sync/
├── parser.py              # Jekyll文章解析器
├── cnblogs_publisher.py   # 博客园发布器
├── csdn_publisher.py      # CSDN发布器
├── sync.py                # 命令行入口脚本
├── config.example.json    # 配置文件模板
├── config.json            # 实际配置文件（需自行创建）
└── README.md              # 使用文档
```

## 常见问题

**Q: 博客园提示"MetaWeblog访问令牌错误"？**
A: 请到博客园后台 -> 设置 -> 开启MetaWeblog访问权限

**Q: CSDN登录后无法自动填写内容？**
A: 可能是CSDN页面结构变化，请检查浏览器控制台错误信息

**Q: ChromeDriver版本不匹配？**
A: 运行 `chrome --version` 查看Chrome版本，下载对应的ChromeDriver

**Q: 如何禁用某个平台的同步？**
A: 在config.json中将对应平台的`enabled`设置为`false`

## 许可证

MIT License
