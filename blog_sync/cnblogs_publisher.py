"""
博客园发布器
使用MetaWeblog API发布文章到博客园
"""
import xmlrpc.client
from typing import Optional


class CnblogsPublisher:
    """博客园文章发布器"""

    def __init__(self, blog_name: str, username: str, token: str):
        """
        初始化博客园发布器

        Args:
            blog_name: 博客名称（MetaWeblog访问地址中的名称）
            username: MetaWeblog登录名
            token: MetaWeblog访问令牌
        """
        self.blog_name = blog_name
        self.username = username
        self.token = token
        self.api_url = f"https://rpc.cnblogs.com/metaweblog/{blog_name}"
        self.server = xmlrpc.client.ServerProxy(self.api_url)
        self.blog_id = None

    def _get_blog_id(self) -> Optional[str]:
        """获取博客ID"""
        try:
            blogs = self.server.blogger.getUsersBlogs('', self.username, self.token)
            if blogs and len(blogs) > 0:
                self.blog_id = blogs[0]['blogid']
                return self.blog_id
            return None
        except Exception as e:
            print(f"获取博客ID失败: {e}")
            return None

    def publish(self, title: str, content: str, tags: list = None,
                categories: list = None, publish: bool = True) -> Optional[str]:
        """
        发布文章到博客园

        Args:
            title: 文章标题
            content: 文章内容（Markdown格式）
            tags: 标签列表
            categories: 分类列表
            publish: 是否立即发布（True）或保存为草稿（False）

        Returns:
            文章ID，失败返回None
        """
        try:
            # 先获取博客ID
            if not self.blog_id:
                print("正在获取博客ID...")
                if not self._get_blog_id():
                    print("✗ 无法获取博客ID，请检查：")
                    print("  1. 用户名和密码是否正确")
                    print("  2. 是否已在博客园后台开启MetaWeblog访问")
                    print("     路径：博客园后台 -> 设置 -> 允许MetaWeblog博客客户端访问")
                    return None
                print(f"✓ 博客ID: {self.blog_id}")

            # 构建文章结构
            post = {
                'title': title,
                'description': content,
                'categories': categories or [],
                'mt_keywords': ','.join(tags) if tags else '',
            }

            print("正在发布文章...")
            # 调用MetaWeblog API发布文章
            post_id = self.server.metaWeblog.newPost(
                self.blog_id,
                self.username,
                self.token,
                post,
                publish
            )

            print(f"✓ 博客园发布成功! 文章ID: {post_id}")
            return post_id

        except xmlrpc.client.ProtocolError as e:
            print(f"✗ 博客园API协议错误: {e}")
            print("  可能原因：")
            print("  1. MetaWeblog API未开启")
            print("  2. 用户名或密码错误")
            print("  3. 网络连接问题")
            return None
        except Exception as e:
            print(f"✗ 博客园发布失败: {e}")
            return None
