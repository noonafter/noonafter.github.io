"""
Jekyll博客文章解析器
解析Jekyll格式的Markdown文件，提取front matter和正文内容
"""
import re
from typing import Dict, Optional
from pathlib import Path


class JekyllParser:
    """Jekyll格式博客文章解析器"""

    def __init__(self, file_path: str):
        self.file_path = Path(file_path)
        self.front_matter: Dict[str, str] = {}
        self.content: str = ""
        self.title: str = ""
        self.tags: list = []

    def parse(self) -> bool:
        """解析文章文件"""
        if not self.file_path.exists():
            print(f"错误: 文件不存在 {self.file_path}")
            return False

        try:
            with open(self.file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # 解析front matter
            pattern = r'^---\s*\n(.*?)\n---\s*\n(.*)$'
            match = re.match(pattern, content, re.DOTALL)

            if not match:
                print("错误: 无法解析front matter")
                return False

            front_matter_text = match.group(1)
            self.content = match.group(2).strip()

            # 解析front matter字段
            self._parse_front_matter(front_matter_text)

            return True

        except Exception as e:
            print(f"解析文件时出错: {e}")
            return False

    def _parse_front_matter(self, text: str):
        """解析front matter内容"""
        for line in text.split('\n'):
            line = line.strip()
            if ':' in line:
                key, value = line.split(':', 1)
                key = key.strip()
                value = value.strip()
                self.front_matter[key] = value

                # 提取常用字段
                if key == 'title':
                    self.title = value
                elif key == 'tags':
                    # 支持多种tags格式
                    if value.startswith('['):
                        # 数组格式: [tag1, tag2]
                        self.tags = [t.strip() for t in value.strip('[]').split(',')]
                    else:
                        # 单个tag
                        self.tags = [value]

    def get_title(self) -> str:
        """获取文章标题"""
        return self.title

    def get_content(self) -> str:
        """获取文章正文"""
        return self.content

    def get_tags(self) -> list:
        """获取文章标签"""
        return self.tags

    def get_categories(self) -> list:
        """获取文章分类"""
        categories = self.front_matter.get('categories', '')
        if categories:
            if categories.startswith('['):
                return [c.strip() for c in categories.strip('[]').split(',')]
            return [categories]
        return []
