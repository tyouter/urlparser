"""
urlparser CLI 接口

命令行工具，提供 URL 解析、转录、缓存管理、状态检查等能力

使用方式:
    # 解析单个 URL
    python -m urlparser parse https://www.zhihu.com/question/xxx

    # 批量解析（从文件读取 URL）
    python -m urlparser parse-batch urls.txt

    # 解析视频并转录
    python -m urlparser parse https://www.bilibili.com/video/BVxxx --transcribe

    # 使用 Cookie
    python -m urlparser parse https://zhuanlan.zhihu.com/p/xxx --cookies cookies.json

    # 使用用户 Chrome
    python -m urlparser parse https://xiaohongshu.com/xxx --user-chrome

    # 在线解析（LLM API，无需浏览器/yt-dlp）
    python -m urlparser parse https://www.bilibili.com/video/BVxxx --parse-mode online

    # 缓存管理
    python -m urlparser cache stats
    python -m urlparser cache clear

    # 状态检查
    python -m urlparser status check https://www.zhihu.com/question/xxx
    python -m urlparser status validate

    # 视频信息提取
    python -m urlparser video-info https://www.bilibili.com/video/BVxxx

    # 音频转录
    python -m urlparser transcribe audio.mp3
    python -m urlparser transcribe https://www.bilibili.com/video/BVxxx --engine funasr

    # 批量转录文件夹
    python -m urlparser transcribe-folder ./videos --preview
    python -m urlparser transcribe-folder ./videos --engine funasr
    python -m urlparser transcribe-folder ./videos --force --no-confirm

    # 安装 Claude Code Skill
    python -m urlparser install-skill
    python -m urlparser install-skill --symlink
    python -m urlparser install-skill --project
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import List, Optional


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog='urlparser',
        description='通用 URL 资源解析器 - 解析、转录、缓存一体化工具',
    )

    subparsers = parser.add_subparsers(dest='command', help='可用命令')

    _add_parse_parser(subparsers)
    _add_parse_batch_parser(subparsers)
    _add_cache_parser(subparsers)
    _add_status_parser(subparsers)
    _add_video_info_parser(subparsers)
    _add_transcribe_parser(subparsers)
    _add_transcribe_folder_parser(subparsers)
    _add_install_deps_parser(subparsers)
    _add_install_skill_parser(subparsers)

    return parser


def _add_parse_parser(subparsers):
    p = subparsers.add_parser('parse', help='解析单个 URL')
    p.add_argument('url', help='要解析的 URL')
    p.add_argument('--transcribe', '-t', action='store_true', help='启用音频转录')
    p.add_argument('--engine', default='auto', choices=['auto', 'funasr', 'whisper'], help='转录引擎')
    p.add_argument('--model-size', default='large', help='模型大小')
    p.add_argument('--cookies', help='Cookie 文件路径')
    p.add_argument('--user-chrome', action='store_true', help='使用用户 Chrome 浏览器')
    p.add_argument('--user-data-dir', help='Chrome 用户数据目录')
    p.add_argument('--no-headless', action='store_true', help='显示浏览器窗口')
    p.add_argument('--output', '-o', help='输出文件路径')
    p.add_argument('--format', '-f', default='markdown', choices=['markdown', 'json'], help='输出格式')
    p.add_argument('--no-cache', action='store_true', help='跳过缓存')
    p.add_argument('--parse-mode', default='local', choices=['local', 'online'], help='解析模式：local=yt-dlp+浏览器, online=LLM API')
    p.add_argument('--comprehension', '-c', choices=['audio', 'video', 'audio_video'],
                   help='视频理解模式')
    p.add_argument('--comp-engine', default='auto',
                   choices=['auto', 'openvino', 'llamacpp'], help='VLM 引擎')
    p.add_argument('--comp-max-frames', type=int, default=50, help='最大分析帧数')


def _add_parse_batch_parser(subparsers):
    p = subparsers.add_parser('parse-batch', help='批量解析 URL')
    p.add_argument('file', help='包含 URL 的文件路径（每行一个 URL，或 Markdown 链接格式）')
    p.add_argument('--transcribe', '-t', action='store_true', help='启用音频转录')
    p.add_argument('--engine', default='auto', choices=['auto', 'funasr', 'whisper'], help='转录引擎')
    p.add_argument('--cookies', help='Cookie 文件路径')
    p.add_argument('--user-chrome', action='store_true', help='使用用户 Chrome 浏览器')
    p.add_argument('--output-dir', '-o', default='./parsed_results', help='输出目录')
    p.add_argument('--concurrent', '-c', type=int, default=3, help='并发数')
    p.add_argument('--no-cache', action='store_true', help='跳过缓存')
    p.add_argument('--parse-mode', default='local', choices=['local', 'online'], help='解析模式')


def _add_cache_parser(subparsers):
    p = subparsers.add_parser('cache', help='缓存管理')
    cache_sub = p.add_subparsers(dest='cache_command', help='缓存子命令')

    stats_p = cache_sub.add_parser('stats', help='查看缓存统计')
    stats_p.add_argument('--cache-dir', default='./parser_cache', help='缓存目录')

    clear_p = cache_sub.add_parser('clear', help='清空缓存')
    clear_p.add_argument('--cache-dir', default='./parser_cache', help='缓存目录')

    get_p = cache_sub.add_parser('get', help='查看缓存的解析结果')
    get_p.add_argument('url', help='URL')
    get_p.add_argument('--cache-dir', default='./parser_cache', help='缓存目录')

    del_p = cache_sub.add_parser('delete', help='删除指定 URL 的缓存')
    del_p.add_argument('url', help='URL')
    del_p.add_argument('--cache-dir', default='./parser_cache', help='缓存目录')


def _add_status_parser(subparsers):
    p = subparsers.add_parser('status', help='状态检查')
    status_sub = p.add_subparsers(dest='status_command', help='状态子命令')

    check_p = status_sub.add_parser('check', help='检查单个资源状态')
    check_p.add_argument('url', help='URL')
    check_p.add_argument('--data-dir', default='data', help='数据目录')

    validate_p = status_sub.add_parser('validate', help='验证数据完整性')
    validate_p.add_argument('--data-dir', default='data', help='数据目录')

    stats_p = status_sub.add_parser('stats', help='查看统计信息')
    stats_p.add_argument('--data-dir', default='data', help='数据目录')


def _add_video_info_parser(subparsers):
    p = subparsers.add_parser('video-info', help='提取视频信息')
    p.add_argument('url', help='视频 URL')
    p.add_argument('--output', '-o', help='输出文件路径')
    p.add_argument('--format', '-f', default='json', choices=['json', 'markdown'], help='输出格式')


def _add_transcribe_parser(subparsers):
    p = subparsers.add_parser('transcribe', help='音频转录')
    p.add_argument('input', help='音频文件路径或视频 URL')
    p.add_argument('--engine', default='auto', choices=['auto', 'funasr', 'whisper'], help='转录引擎')
    p.add_argument('--model-size', default='large', help='模型大小')
    p.add_argument('--language', default='zh', help='语言')
    p.add_argument('--device', default='auto', choices=['auto', 'cuda', 'cpu'], help='计算设备')
    p.add_argument('--output', '-o', help='输出文件路径（文本格式）')
    p.add_argument('--output-dir', help='输出目录（保存 Markdown 文件）')


def _add_transcribe_folder_parser(subparsers):
    """添加批量转录文件夹命令"""
    p = subparsers.add_parser(
        'transcribe-folder',
        help='批量转录本地文件夹内的音视频文件'
    )
    p.add_argument('directory', help='要扫描的文件夹路径')
    p.add_argument('--engine', default='auto',
                   choices=['auto', 'funasr', 'whisper'],
                   help='转录引擎 (auto=根据语言自动选择)')
    p.add_argument('--model-size', default='large',
                   choices=['small', 'base', 'large', 'sensevoice'],
                   help='模型大小')
    p.add_argument('--language', default='zh',
                   help='语言代码 (zh, en, ja 等)')
    p.add_argument('--recursive', '-r', action='store_true', default=True,
                   help='递归扫描子文件夹')
    p.add_argument('--no-recursive', action='store_true',
                   help='不递归扫描子文件夹')
    p.add_argument('--skip-existing', action='store_true', default=True,
                   help='跳过已有 .md 转录文件的音视频')
    p.add_argument('--force', '-f', action='store_true',
                   help='强制转录所有文件，包括已有转录的')
    p.add_argument('--preview', action='store_true',
                   help='仅预览扫描结果，不执行转录')
    p.add_argument('--segment-threshold', type=int, default=30,
                   help='分段时长阈值（分钟），超过此时长的大文件将分段处理')
    p.add_argument('--max-size', type=int, default=500,
                   help='最大文件大小阈值（MB），超过此大小的大文件将分段处理')
    p.add_argument('--no-confirm', action='store_true',
                   help='跳过开始前的确认提示')
    p.add_argument('--device', default='auto',
                   choices=['auto', 'cuda', 'cpu'],
                   help='计算设备')
    p.add_argument('--skip-dep-check', action='store_true',
                   help='跳过依赖检查')
    p.add_argument('--output-dir', '-o',
                   help='输出目录（保存 Markdown 文件，默认保存到源文件同目录）')


def _add_install_deps_parser(subparsers):
    """添加依赖安装命令"""
    p = subparsers.add_parser(
        'install-deps',
        help='检查并安装依赖'
    )
    p.add_argument('--transcribe', '-t', action='store_true',
                   help='仅安装转录相关依赖')
    p.add_argument('--core', '-c', action='store_true',
                   help='仅安装核心依赖')
    p.add_argument('--dry-run', action='store_true',
                   help='仅检查，不安装')


def _add_install_skill_parser(subparsers):
    """添加 Skill 安装命令"""
    p = subparsers.add_parser(
        'install-skill',
        help='安装 urlparser Skill 到 Claude Code'
    )
    p.add_argument('--symlink', '-s', action='store_true',
                   help='使用符号链接（推荐，代码更新自动同步）')
    p.add_argument('--project', '-p', action='store_true',
                   help='安装到当前项目 .claude/skills/ 而非全局 ~/.claude/skills/')
    p.add_argument('--force', '-f', action='store_true',
                   help='强制覆盖已存在的 Skill')
    p.add_argument('--dry-run', action='store_true',
                   help='仅显示将要执行的操作，不实际安装')


async def cmd_parse(args):
    from .core import UrlParser
    from .config import ParseConfig, TranscribeConfig, BrowserConfig, ComprehensionConfig

    comp_config = None
    if args.comprehension:
        mode_map = {'audio': 'audio_only', 'video': 'video_only', 'audio_video': 'audio_video'}
        comp_config = ComprehensionConfig(
            enabled=True,
            mode=mode_map.get(args.comprehension, 'audio_video'),
            engine=args.comp_engine,
            max_frames=args.comp_max_frames,
        )

    config = ParseConfig(
        transcribe=TranscribeConfig(
            enabled=args.transcribe,
            engine=args.engine,
            model_size=args.model_size,
        ),
        browser=BrowserConfig(
            cookies_file=args.cookies,
            use_user_chrome=args.user_chrome,
            user_data_dir=args.user_data_dir,
            headless=not args.no_headless,
        ),
        parse_mode=args.parse_mode,
        comprehension=comp_config or ComprehensionConfig(),
    )

    async with UrlParser(config) as parser:
        result = await parser.parse(args.url, force_refresh=args.no_cache)

        if args.format == 'json':
            output = json.dumps(result.to_dict(), ensure_ascii=False, indent=2)
        else:
            output = result.to_markdown()

        if args.output:
            Path(args.output).write_text(output, encoding='utf-8')
            print(f"已保存到: {args.output}")
        else:
            print(output)


async def cmd_parse_batch(args):
    from .core import UrlParser
    from .config import ParseConfig, TranscribeConfig, BrowserConfig
    from .utils.file_utils import ensure_dir

    urls = _extract_urls_from_file(args.file)
    if not urls:
        print(f"未找到 URL，请检查文件: {args.file}")
        return

    print(f"找到 {len(urls)} 个 URL")

    config = ParseConfig(
        transcribe=TranscribeConfig(
            enabled=args.transcribe,
            engine=args.engine,
        ),
        browser=BrowserConfig(
            cookies_file=args.cookies,
            use_user_chrome=args.user_chrome,
        ),
        parse_mode=args.parse_mode,
    )

    output_dir = ensure_dir(args.output_dir)

    async with UrlParser(config) as parser:
        results = await parser.parse_batch(
            urls,
            concurrent=args.concurrent,
        )

        success_count = sum(1 for r in results if r.fetch_success)
        print(f"\n完成: {success_count}/{len(results)} 成功")

        for result in results:
            if result.fetch_success:
                file_path = output_dir / f"{result.platform}_{result.title[:30]}.md"
                file_path.write_text(result.to_markdown(), encoding='utf-8')
                print(f"  [OK] {result.title[:50]} -> {file_path}")
            else:
                print(f"  [FAIL] {result.url[:50]}: {result.error}")


async def cmd_cache(args):
    from .storage import ResultCache

    if args.cache_command == 'stats':
        cache = ResultCache(cache_dir=args.cache_dir)
        stats = await cache.stats()
        print(json.dumps(stats, indent=2, ensure_ascii=False))

    elif args.cache_command == 'clear':
        cache = ResultCache(cache_dir=args.cache_dir)
        await cache.clear()
        print("缓存已清空")

    elif args.cache_command == 'get':
        cache = ResultCache(cache_dir=args.cache_dir)
        result = await cache.get(args.url)
        if result:
            print(json.dumps(result, indent=2, ensure_ascii=False))
        else:
            print("未找到缓存")

    elif args.cache_command == 'delete':
        cache = ResultCache(cache_dir=args.cache_dir)
        await cache.delete(args.url)
        print("缓存已删除")

    else:
        print("请指定缓存子命令: stats, clear, get, delete")


async def cmd_status(args):
    from .storage import StateManager

    if args.status_command == 'check':
        manager = StateManager(data_dir=args.data_dir)
        state = manager.check_resource_state(args.url)
        status = manager.get_process_status(args.url)

        print(f"URL: {state.url}")
        print(f"状态: {status.value}")
        print(f"已处理: {state.processed}")
        print(f"源文件存在: {state.source_exists}")
        print(f"已分析: {state.analyzed}")

    elif args.status_command == 'validate':
        manager = StateManager(data_dir=args.data_dir)
        report = manager.validate_integrity()

        if report['valid']:
            print("数据完整性验证通过")
        else:
            print("发现数据完整性问题:")
            for issue in report['issues']:
                print(f"  - {issue['type']}: {issue['count']}")

        print(f"\n统计: {json.dumps(report['summary'], indent=2, ensure_ascii=False)}")

    elif args.status_command == 'stats':
        manager = StateManager(data_dir=args.data_dir)
        states = manager.check_all_resources()

        status_counts = {}
        for state in states:
            status = manager.get_process_status(state.url)
            status_counts[status.value] = status_counts.get(status.value, 0) + 1

        print(f"总资源数: {len(states)}")
        for status, count in status_counts.items():
            print(f"  {status}: {count}")

    else:
        print("请指定状态子命令: check, validate, stats")


async def cmd_video_info(args):
    from .transcriber import extract_video_info

    info = extract_video_info(args.url)

    if args.format == 'json':
        output = json.dumps(info, ensure_ascii=False, indent=2)
    else:
        lines = [f"# {info.get('title', 'Untitled')}", ""]
        for key, value in info.items():
            if value and key not in ('url', 'raw_text'):
                lines.append(f"- **{key}**: {value}")
        output = '\n'.join(lines)

    if args.output:
        Path(args.output).write_text(output, encoding='utf-8')
        print(f"已保存到: {args.output}")
    else:
        print(output)


async def cmd_transcribe(args):
    from .transcriber import FunASRTranscriber, WhisperTranscriber
    from .dependency_installer import ensure_transcribe_dependencies
    from .utils.media_utils import is_video_file
    from .batch_transcriber.writer import TranscriptionWriter

    # 检查依赖
    if not ensure_transcribe_dependencies(auto_install=True):
        print("\n错误: 转录依赖不完整，无法继续")
        print("请使用 'urlparser install-deps --transcribe' 安装依赖")
        return

    engine = args.engine
    if engine == 'auto':
        engine = 'funasr' if args.language == 'zh' else 'whisper'

    if engine == 'funasr':
        transcriber = FunASRTranscriber(model_size=args.model_size, device=args.device)
    else:
        transcriber = WhisperTranscriber(model_size=args.model_size, device=args.device)

    input_path = args.input

    if input_path.startswith('http'):
        result = transcriber.transcribe_from_url(input_path, language=args.language)
    elif is_video_file(input_path):
        # 本地视频文件需要先提取音频
        result = transcriber.transcribe_from_local_video(
            input_path,
            language=args.language,
            extract_audio_only=True
        )
    else:
        result = transcriber.transcribe(input_path, language=args.language)

    if result.success:
        output_text = result.text

        # 如果指定了 output_dir，保存为 Markdown 格式
        if args.output_dir:
            output_dir = Path(args.output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)
            writer = TranscriptionWriter(output_dir=output_dir)
            media_path = Path(input_path)
            md_path = writer.write(media_path, result)
            print(f"转录完成，Markdown 文件已保存到: {md_path}")

        elif args.output:
            # 指定了输出文件路径（纯文本）
            Path(args.output).write_text(output_text, encoding='utf-8')
            print(f"转录完成，已保存到: {args.output}")
        else:
            # 默认直接输出文本
            print(output_text)
    else:
        print(f"转录失败: {result.error}")


async def cmd_transcribe_folder(args):
    """批量转录文件夹命令"""
    from .batch_transcriber import (
        BatchTranscriber, BatchTranscribeConfig,
        format_batch_result_summary, generate_preview_text
    )
    from .dependency_installer import ensure_transcribe_dependencies

    # 检查依赖（除非用户跳过）
    if not args.skip_dep_check:
        if not ensure_transcribe_dependencies(auto_install=True):
            print("\n错误: 转录依赖不完整，无法继续")
            print("请使用 'urlparser install-deps --transcribe' 安装依赖")
            return

    # 创建配置
    config = BatchTranscribeConfig(
        engine=args.engine,
        model_size=args.model_size,
        device=args.device,
        language=args.language,
        recursive=args.recursive and not args.no_recursive,
        skip_existing=args.skip_existing and not args.force,
        segment_threshold_min=args.segment_threshold,
        max_file_size_mb=args.max_size,
        confirm_before_start=not args.no_confirm,
        output_dir=args.output_dir,
    )

    processor = BatchTranscriber(config)

    # 扫描目录
    print(f"正在扫描目录: {args.directory}")
    print()

    try:
        scan_result, preview_text = processor.scan_and_preview(args.directory)
    except Exception as e:
        print(f"扫描失败: {e}")
        return

    print(preview_text)
    print()

    # 仅预览模式
    if args.preview:
        print("预览模式，未执行转录")
        return

    # 检查是否有待处理文件
    pending_files = processor.filter_files_to_process(scan_result)

    if not pending_files:
        print("没有待处理的文件（所有文件可能已有转录）")
        return

    print(f"待处理文件: {len(pending_files)} 个")
    print()

    # 确认开始
    if config.confirm_before_start:
        print("是否开始转录？ [y/N]")
        try:
            response = input().strip().lower()
            if response not in ('y', 'yes'):
                print("已取消")
                return
        except EOFError:
            print("已取消")
            return

    print()
    print("=" * 60)
    print("开始转录...")
    print("=" * 60)
    print()

    # 执行转录
    try:
        # 进度回调
        def progress_callback(current, total, file_result, batch_result):
            status = "OK" if file_result.success else "FAIL"
            segmented = " (分段)" if file_result.segmented else ""
            print(f"[{current}/{total}] [{status}] {file_result.file_info.filename}{segmented}")
            if not file_result.success:
                print(f"  错误: {file_result.error}")
            if file_result.md_path:
                print(f"  输出: {file_result.md_path}")

        batch_result = processor.transcribe_all(pending_files, progress_callback)

        print()
        print(format_batch_result_summary(batch_result))

    except KeyboardInterrupt:
        print()
        print("用户中断转录")
    except Exception as e:
        print(f"转录失败: {e}")
        import traceback
        traceback.print_exc()


def _extract_urls_from_file(file_path: str) -> List[str]:
    import re

    p = Path(file_path)
    if not p.exists():
        print(f"文件不存在: {file_path}")
        return []

    content = p.read_text(encoding='utf-8')
    urls = []

    link_pattern = re.compile(r'\[([^\]]+)\]\((https?://[^\)]+)\)')
    for match in link_pattern.finditer(content):
        urls.append(match.group(2))

    if not urls:
        for line in content.split('\n'):
            line = line.strip()
            if line.startswith('http'):
                urls.append(line)

    return list(dict.fromkeys(urls))


async def cmd_install_deps(args):
    """CLI 命令: 安装依赖"""
    from .dependency_installer import ensure_all_dependencies, ensure_transcribe_dependencies, ensure_core_dependencies

    auto_install = not args.dry_run

    if args.transcribe:
        ensure_transcribe_dependencies(auto_install=auto_install)
    elif args.core:
        ensure_core_dependencies(auto_install=auto_install)
    else:
        ensure_all_dependencies(auto_install=auto_install)


def cmd_install_skill(args):
    """CLI 命令: 安装 Skill 到 Claude Code"""
    import shutil
    import urlparser

    # 显示信息
    print("=" * 60)
    print("urlparser Skill 安装")
    print("=" * 60)
    print()

    # 显示安装前提
    pkg_path = Path(urlparser.__path__[0])
    pkg_version = urlparser.__version__

    print(f"urlparser 已安装: v{pkg_version}")
    print(f"安装路径: {pkg_path}")
    print()

    # 检查是 pip 安装还是本地开发安装
    is_editable = 'site-packages' not in str(pkg_path).lower()
    if is_editable:
        print("安装模式: 本地开发 (-e editable)")
        print("  → Skill 将链接到源码目录，代码更新自动同步")
    else:
        print("安装模式: pip 安装 (site-packages)")
        print("  → Skill 依赖 pip 安装的包，更新 urlparser 需重新 pip install")

    print()

    # 获取 skill 源目录
    skill_src = Path(urlparser.__path__[0]) / 'skill'

    if not skill_src.exists():
        print(f"错误: Skill 目录不存在: {skill_src}")
        return

    # 确定目标目录
    if args.project:
        # 项目级安装
        skill_dst = Path.cwd() / '.claude' / 'skills' / 'urlparser'
    else:
        # 全局安装
        skill_dst = Path.home() / '.claude' / 'skills' / 'urlparser'

    # 确保父目录存在
    skill_dst.parent.mkdir(parents=True, exist_ok=True)

    print(f"Skill 源目录: {skill_src}")
    print(f"Skill 目标目录: {skill_dst}")
    print(f"链接方式: {'符号链接' if args.symlink else '复制'}")
    print(f"安装范围: {'项目级' if args.project else '全局'}")
    print()

    # 检查目标是否已存在
    if skill_dst.exists():
        if args.dry_run:
            print(f"[DRY-RUN] 将删除现有: {skill_dst}")
        elif args.force:
            print(f"删除现有 Skill: {skill_dst}")
            # Windows Junction/符号链接需要特殊处理
            if sys.platform == 'win32':
                # Windows: Junction 是目录链接，需要用 rmdir 或 os.rmdir
                import subprocess
                try:
                    subprocess.run(['cmd', '/c', 'rmdir', str(skill_dst)], check=True, capture_output=True)
                except subprocess.CalledProcessError:
                    # 如果不是 Junction，尝试普通删除
                    if skill_dst.is_symlink():
                        skill_dst.unlink()
                    else:
                        shutil.rmtree(skill_dst)
            else:
                # Linux/macOS
                if skill_dst.is_symlink() or skill_dst.is_dir():
                    skill_dst.unlink() if skill_dst.is_symlink() else shutil.rmtree(skill_dst)
        else:
            print(f"目标已存在: {skill_dst}")
            print("使用 --force 强制覆盖，或先手动删除")
            return

    if args.dry_run:
        if args.symlink:
            print(f"[DRY-RUN] 将创建符号链接: {skill_dst} -> {skill_src}")
        else:
            print(f"[DRY-RUN] 将复制目录: {skill_src} -> {skill_dst}")
        print()
        print("[DRY-RUN] 未执行实际安装")
        return

    # 执行安装
    try:
        if args.symlink:
            # 符号链接模式
            # Windows 需要处理权限问题
            if sys.platform == 'win32':
                # Windows: 使用目录 Junction 或符号链接
                # Junction 不需要管理员权限
                import subprocess
                try:
                    # 尝试创建符号链接（需要管理员权限或开发者模式）
                    skill_dst.symlink_to(skill_src)
                    print("符号链接创建成功")
                except OSError as e:
                    print(f"符号链接失败: {e}")
                    print("尝试使用 Junction (Windows 目录链接)...")

                    # 使用 Junction 作为备选
                    # Junction 可以在不需要管理员权限的情况下创建目录链接
                    subprocess.run(
                        ['cmd', '/c', 'mklink', '/J',
                         str(skill_dst), str(skill_src)],
                        check=True,
                        capture_output=True
                    )
                    print(f"Junction 创建成功: {skill_dst} <-> {skill_src}")
            else:
                # Linux/macOS: 直接创建符号链接
                skill_dst.symlink_to(skill_src)
                print(f"符号链接创建成功: {skill_dst} -> {skill_src}")

        else:
            # 复制模式
            shutil.copytree(skill_src, skill_dst)
            print(f"Skill 复制完成: {skill_dst}")

        print()
        print("=" * 60)
        print("安装成功!")
        print("=" * 60)
        print()

        # 验证安装
        skill_md = skill_dst / 'SKILL.md'
        if skill_md.exists():
            print(f"Skill 定义文件: {skill_md}")
            print()

            # 验证 import 能否正常工作
            print("验证 import urlparser...")
            try:
                # 测试 import 是否能正常工作
                import subprocess
                result = subprocess.run(
                    [sys.executable, '-c', 'from urlparser import parse; print("OK")'],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                if result.returncode == 0 and 'OK' in result.stdout:
                    print("  ✓ import urlparser 正常")
                else:
                    print("  ⚠ import urlparser 可能有问题")
                    if result.stderr:
                        print(f"    错误: {result.stderr[:200]}")
            except Exception as e:
                print(f"  ⚠ 验证失败: {e}")

            print()

            # 提示使用方式
            if args.project:
                print("项目级 Skill 已安装，Claude Code 将在当前项目自动发现。")
            else:
                print("全局 Skill 已安装，Claude Code 将自动发现 urlparser Skill。")
            print()
            print("触发方式:")
            print("  - 自然语言: '帮我解析这个知乎链接 https://...' ")
            print("  - 显式调用: /urlparser parse <url>")
            print()
            print("注意事项:")
            if is_editable:
                print("  - 本地开发模式，代码更新自动同步到 Skill")
                print("  - Skill 脚本依赖本地 urlparser 包")
            else:
                print("  - pip 安装模式，Skill 依赖 site-packages 中的 urlparser")
                print("  - 更新 urlparser 后需重新 pip install urlparser")
                print("  - Skill 目录只包含入口脚本，不含核心代码")
            print()
            print("卸载方式:")
            print(f"  删除目录: {skill_dst}")

        else:
            print(f"警告: SKILL.md 不存在，Skill 可能不完整")

    except Exception as e:
        print(f"安装失败: {e}")
        import traceback
        traceback.print_exc()


def main():
    # Windows 控制台编码处理
    if sys.platform == 'win32':
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')

    parser = create_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    command_map = {
        'parse': cmd_parse,
        'parse-batch': cmd_parse_batch,
        'cache': cmd_cache,
        'status': cmd_status,
        'video-info': cmd_video_info,
        'transcribe': cmd_transcribe,
        'transcribe-folder': cmd_transcribe_folder,
        'install-deps': cmd_install_deps,
        'install-skill': cmd_install_skill,
    }

    handler = command_map.get(args.command)
    if handler:
        # install-skill 是同步命令，不需要 asyncio
        if args.command == 'install-skill':
            handler(args)
        else:
            asyncio.run(handler(args))
    else:
        parser.print_help()


if __name__ == '__main__':
    main()