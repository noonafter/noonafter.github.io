"""
CSDN发布器
使用Selenium自动化浏览器发布文章到CSDN
"""
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
import time
import subprocess
import shutil
import json
import os
from pathlib import Path


class CsdnPublisher:
    """CSDN文章发布器"""

    def __init__(self, headless: bool = False):
        """
        初始化CSDN发布器

        Args:
            headless: 是否使用无头模式（不显示浏览器窗口）
        """
        self.headless = headless
        self.driver = None
        self.cookie_file = Path(__file__).parent / "csdn_cookies.json"

    def _save_cookies(self):
        """保存Cookie到文件"""
        try:
            cookies = self.driver.get_cookies()
            with open(self.cookie_file, 'w') as f:
                json.dump(cookies, f)
            print(f"✓ Cookie已保存到: {self.cookie_file}")
        except Exception as e:
            print(f"保存Cookie失败: {e}")

    def _load_cookies(self):
        """从文件加载Cookie"""
        try:
            if not self.cookie_file.exists():
                return False

            with open(self.cookie_file, 'r') as f:
                cookies = json.load(f)

            for cookie in cookies:
                self.driver.add_cookie(cookie)

            print("✓ Cookie已加载")
            return True
        except Exception as e:
            print(f"加载Cookie失败: {e}")
            return False

    def _find_chrome_binary(self):
        """查找Chrome浏览器路径"""
        import os

        possible_paths = [
            '/opt/google/chrome/google-chrome',
            '/usr/bin/google-chrome-stable',
            '/usr/bin/google-chrome',
            '/usr/bin/chromium-browser',
            '/usr/bin/chromium',
            '/snap/bin/chromium',
        ]

        for path in possible_paths:
            if os.path.isfile(path) and os.access(path, os.X_OK):
                return path

        # 尝试使用which命令
        for cmd in ['google-chrome', 'google-chrome-stable', 'chromium-browser', 'chromium']:
            path = shutil.which(cmd)
            if path:
                # 解析符号链接获取实际路径
                real_path = subprocess.run(['readlink', '-f', path],
                                          capture_output=True, text=True).stdout.strip()
                if real_path and os.path.isfile(real_path):
                    return real_path

        return None

    def _init_driver(self):
        """初始化浏览器驱动"""
        chrome_options = Options()

        # 查找Chrome浏览器
        chrome_binary = self._find_chrome_binary()
        if chrome_binary:
            chrome_options.binary_location = chrome_binary
            print(f"使用Chrome浏览器: {chrome_binary}")

        if self.headless:
            chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')

        # 使用Selenium Manager自动管理ChromeDriver
        # 不指定service，让Selenium自动下载匹配的驱动
        try:
            self.driver = webdriver.Chrome(options=chrome_options)
            self.driver.implicitly_wait(10)
        except Exception as e:
            print(f"初始化浏览器失败: {e}")
            print("提示：Selenium会自动下载匹配的ChromeDriver")
            raise

    def login(self, username: str, password: str) -> bool:
        """
        登录CSDN账号（支持Cookie自动登录）

        Args:
            username: CSDN用户名（未使用，保留参数兼容性）
            password: CSDN密码（未使用，保留参数兼容性）

        Returns:
            登录是否成功
        """
        try:
            if not self.driver:
                self._init_driver()

            # 尝试使用Cookie自动登录
            if self.cookie_file.exists():
                print("检测到已保存的Cookie，尝试自动登录...")
                self.driver.get("https://www.csdn.net")
                time.sleep(2)

                # 加载Cookie
                if self._load_cookies():
                    # 刷新页面验证登录状态
                    self.driver.refresh()
                    time.sleep(3)

                    # 检查是否登录成功
                    try:
                        # 尝试访问个人中心，如果能访问说明已登录
                        self.driver.get("https://mp.csdn.net/mp_blog/creation/editor")
                        time.sleep(3)

                        if "passport.csdn.net/login" not in self.driver.current_url:
                            print("✓ Cookie自动登录成功!")
                            return True
                        else:
                            print("Cookie已过期，需要重新登录")
                    except:
                        print("Cookie验证失败，需要重新登录")

            print("正在打开CSDN登录页面...")
            self.driver.get("https://passport.csdn.net/login")
            time.sleep(3)

            print("\n" + "="*60)
            print("请在浏览器中手动完成登录：")
            print("  1. 可以使用扫码登录（推荐）")
            print("  2. 或切换到密码登录")
            print("  3. 登录完成后，按Enter键继续...")
            print("="*60)

            input("\n按Enter键继续...")

            # 检查是否登录成功
            if "passport.csdn.net/login" not in self.driver.current_url:
                print("✓ 登录成功!")
                # 保存Cookie供下次使用
                self._save_cookies()
                return True
            else:
                print("✗ 登录失败，请重试")
                return False

        except Exception as e:
            print(f"✗ 登录失败: {e}")
            return False

    def publish(self, title: str, content: str, tags: list = None) -> bool:
        """
        发布文章到CSDN

        Args:
            title: 文章标题
            content: 文章内容（Markdown格式）
            tags: 标签列表（最多3个）

        Returns:
            发布是否成功
        """
        try:
            if not self.driver:
                print("错误: 请先登录")
                return False

            print("正在打开CSDN Markdown编辑器...")
            self.driver.get("https://editor.csdn.net/md/")
            time.sleep(5)

            # 处理可能的安全弹窗
            print("\n如果出现安全弹窗，请手动关闭...")
            print("等待页面加载完成...")
            time.sleep(3)

            return self._fill_article(title, content, tags)

        except Exception as e:
            print(f"✗ CSDN发布失败: {e}")
            return False

    def _fill_article(self, title: str, content: str, tags: list = None) -> bool:
        """填写文章内容（Markdown编辑器）"""
        try:
            print("\n正在自动填写文章...")

            # 等待页面完全加载
            time.sleep(3)

            # 1. 填写标题
            print("正在填写标题...")
            try:
                # Markdown编辑器的标题选择器
                title_selectors = [
                    "input.article-bar__title",  # Markdown编辑器
                    "input.article-bar__title--input",
                    "#txtTitle",  # 富文本编辑器
                    "input[placeholder*='请输入文章标题']"
                ]

                title_input = None
                for selector in title_selectors:
                    try:
                        title_input = WebDriverWait(self.driver, 5).until(
                            EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                        )
                        print(f"找到标题输入框: {selector}")
                        break
                    except:
                        continue

                if title_input:
                    title_input.clear()
                    title_input.send_keys(title)
                    print(f"✓ 标题已填写: {title}")
                    time.sleep(1)
                else:
                    print("✗ 无法找到标题输入框，请手动填写")
            except Exception as e:
                print(f"填写标题失败: {e}")
                print("请手动填写标题")

            time.sleep(1)

            # 2. 填写内容
            print("正在填写内容...")
            try:
                content_filled = False

                # 方法1: CSDN Markdown编辑器 (contenteditable pre)
                try:
                    editor = self.driver.find_element(By.CSS_SELECTOR, "pre.editor__inner[contenteditable='true']")
                    # 清空默认内容
                    self.driver.execute_script("arguments[0].innerHTML = '';", editor)
                    # 设置新内容（纯文本）
                    self.driver.execute_script("arguments[0].textContent = arguments[1];", editor, content)
                    content_filled = True
                    print("✓ 内容已填写（CSDN Markdown编辑器）")
                except Exception as e:
                    print(f"CSDN Markdown编辑器方法失败: {e}")

                # 方法2: 尝试Monaco编辑器
                if not content_filled:
                    try:
                        self.driver.execute_script("""
                            if (window.monaco && window.monaco.editor) {
                                var editors = window.monaco.editor.getEditors();
                                if (editors && editors.length > 0) {
                                    editors[0].setValue(arguments[0]);
                                }
                            }
                        """, content)
                        content_filled = True
                        print("✓ 内容已填写（Monaco编辑器）")
                    except:
                        pass

                # 方法3: 尝试普通textarea
                if not content_filled:
                    try:
                        textarea = self.driver.find_element(By.CSS_SELECTOR, "textarea.editor-content")
                        textarea.clear()
                        textarea.send_keys(content)
                        content_filled = True
                        print("✓ 内容已填写（Textarea）")
                    except:
                        pass

                if not content_filled:
                    print("✗ 无法自动填写内容，请手动粘贴")

            except Exception as e:
                print(f"填写内容失败: {e}")
                print("请手动粘贴内容")

            time.sleep(2)

            # 3. 提示用户完成剩余操作
            print("\n" + "="*60)
            print("文章标题和内容已自动填写")
            print("请在浏览器中完成以下操作：")
            print("  1. 检查标题和内容是否正确")
            print("  2. 添加文章标签")
            print("  3. 选择文章分类")
            print("  4. 点击'发布文章'按钮")
            print("\n完成后按Enter键关闭浏览器...")
            print("="*60)

            input("\n按Enter键继续...")

            print("✓ CSDN文章发布流程完成!")
            return True

        except Exception as e:
            print(f"处理文章时出错: {e}")
            return False

    def close(self):
        """关闭浏览器"""
        if self.driver:
            self.driver.quit()
            self.driver = None
