#!/usr/bin/env python3
"""
批量同步博文到博客园
"""
import json
import sys
import time
from pathlib import Path

from parser import JekyllParser
from cnblogs_publisher import CnblogsPublisher


def load_config(config_path: str = "config.json") -> dict:
    """加载配置文件"""
    config_file = Path(__file__).parent / config_path

    if not config_file.exists():
        print(f"错误: 配置文件不存在: {config_file}")
        sys.exit(1)

    with open(config_file, 'r', encoding='utf-8') as f:
        return json.load(f)


def sync_file(file_path: Path, publisher: CnblogsPublisher) -> tuple:
    """
    同步单个文件
    返回: (状态, 消息)
    状态: 'success', 'skip', 'failed'
    """
    try:
        parser = JekyllParser(str(file_path))
        if not parser.parse():
            return ('failed', '解析失败')

        result = publisher.publish(
            title=parser.get_title(),
            content=parser.get_content(),
            tags=parser.get_tags(),
            categories=parser.get_categories()
        )

        if result is not None:
            return ('success', '同步成功')
        else:
            return ('failed', '发布失败')

    except Exception as e:
        error_msg = str(e)
        if '相同标题的博文已存在' in error_msg:
            return ('skip', '已存在，跳过')
        return ('failed', f'同步失败: {e}')


def main():
    """主函数"""
    # 加载配置
    config = load_config()
    cnblogs_config = config.get('cnblogs', {})

    if not cnblogs_config.get('enabled', False):
        print("博客园同步已禁用")
        sys.exit(1)

    # 初始化发布器
    publisher = CnblogsPublisher(
        blog_name=cnblogs_config['blog_name'],
        username=cnblogs_config['username'],
        token=cnblogs_config['token']
    )

    # 获取所有博文
    posts_dir = Path(__file__).parent.parent / "_posts"
    md_files = sorted(posts_dir.glob("*.md"))

    if not md_files:
        print("未找到任何博文")
        sys.exit(0)

    print(f"找到 {len(md_files)} 篇博文")
    print("="*60)

    # 批量同步
    success_count = 0
    skip_count = 0
    failed_files = []

    for i, file_path in enumerate(md_files, 1):
        print(f"\n[{i}/{len(md_files)}] {file_path.name}")

        status, message = sync_file(file_path, publisher)

        if status == 'success':
            success_count += 1
            print(f"  ✓ {message}")
            # 每成功同步15篇暂停65秒，避免触发博客园限流
            if success_count % 15 == 0 and i < len(md_files):
                print(f"\n⏸ 已成功同步 {success_count} 篇，暂停 65 秒避免限流...")
                time.sleep(65)
        elif status == 'skip':
            skip_count += 1
            print(f"  ⊘ {message}")
        else:
            failed_files.append(file_path.name)
            print(f"  ✗ {message}")

    # 输出统计
    print("\n" + "="*60)
    print(f"同步完成: 成功 {success_count} | 跳过 {skip_count} | 失败 {len(failed_files)} | 总计 {len(md_files)}")

    if failed_files:
        print(f"\n失败的文件 ({len(failed_files)}):")
        for filename in failed_files:
            print(f"  - {filename}")

    print("="*60)


if __name__ == '__main__':
    main()
