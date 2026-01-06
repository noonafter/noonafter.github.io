#!/usr/bin/env python3
"""
博客同步工具 - 命令行入口
将Jekyll博客文章同步到CSDN和博客园
"""
import argparse
import json
import sys
from pathlib import Path

from parser import JekyllParser
from cnblogs_publisher import CnblogsPublisher
from csdn_publisher import CsdnPublisher


def load_config(config_path: str = "config.json") -> dict:
    """加载配置文件"""
    config_file = Path(__file__).parent / config_path

    if not config_file.exists():
        print(f"错误: 配置文件不存在: {config_file}")
        print("请复制 config.example.json 为 config.json 并填写你的账号信息")
        sys.exit(1)

    with open(config_file, 'r', encoding='utf-8') as f:
        return json.load(f)


def sync_to_cnblogs(parser: JekyllParser, config: dict) -> bool:
    """同步到博客园"""
    if not config.get('enabled', False):
        print("博客园同步已禁用")
        return True

    print("\n" + "="*50)
    print("开始同步到博客园...")
    print("="*50)

    publisher = CnblogsPublisher(
        blog_name=config['blog_name'],
        username=config['username'],
        token=config['token']
    )

    result = publisher.publish(
        title=parser.get_title(),
        content=parser.get_content(),
        tags=parser.get_tags(),
        categories=parser.get_categories()
    )

    return result is not None


def sync_to_csdn(parser: JekyllParser, config: dict) -> bool:
    """同步到CSDN"""
    if not config.get('enabled', False):
        print("CSDN同步已禁用")
        return True

    print("\n" + "="*50)
    print("开始同步到CSDN...")
    print("="*50)

    publisher = CsdnPublisher(headless=config.get('headless', False))

    try:
        # 登录
        if not publisher.login(config['username'], config['password']):
            return False

        # 发布文章
        result = publisher.publish(
            title=parser.get_title(),
            content=parser.get_content(),
            tags=parser.get_tags()
        )

        return result

    finally:
        publisher.close()


def main():
    """主函数"""
    parser_arg = argparse.ArgumentParser(
        description='将Jekyll博客文章同步到CSDN和博客园'
    )
    parser_arg.add_argument(
        'file',
        help='要同步的Markdown文件路径'
    )
    parser_arg.add_argument(
        '--cnblogs-only',
        action='store_true',
        help='仅同步到博客园'
    )
    parser_arg.add_argument(
        '--csdn-only',
        action='store_true',
        help='仅同步到CSDN'
    )
    parser_arg.add_argument(
        '--config',
        default='config.json',
        help='配置文件路径（默认: config.json）'
    )

    args = parser_arg.parse_args()

    # 加载配置
    config = load_config(args.config)

    # 解析文章
    print("正在解析文章...")
    parser = JekyllParser(args.file)
    if not parser.parse():
        print("解析文章失败")
        sys.exit(1)

    print(f"文章标题: {parser.get_title()}")
    print(f"文章标签: {', '.join(parser.get_tags())}")
    print()

    # 同步到各平台
    success = True

    if not args.csdn_only:
        if not sync_to_cnblogs(parser, config.get('cnblogs', {})):
            success = False

    if not args.cnblogs_only:
        if not sync_to_csdn(parser, config.get('csdn', {})):
            success = False

    # 输出结果
    print("\n" + "="*50)
    if success:
        print("✓ 同步完成!")
    else:
        print("✗ 同步过程中出现错误")
    print("="*50)

    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
