"""
urlparser CLI 接口

命令行工具，提供 URL 解析、转录、缓存管理、状态检查等能力

使用方式:
    # 解析单个 URL
    python -m urlparser parse https://www.zhihu.com/question/xxx

    # 批量解析（从文件读取 URL）
    python -m urlparser parse-batch urls.txt

    # 解析视频（自动转录）
    python -m urlparser parse https://www.bilibili.com/video/BVxxx

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
    python -m urlparser transcribe https://www.bilibili.com/video/BVxxx

    # 批量转录文件夹
    python -m urlparser transcribe-folder ./videos --preview
    python -m urlparser transcribe-folder ./videos --force --no-confirm
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
    _add_daemon_parser(subparsers)
    _add_job_parser(subparsers)
    _add_doctor_parser(subparsers)
    _add_discover_parser(subparsers)
    _add_extract_parser(subparsers)

    return parser


def _add_parse_parser(subparsers):
    p = subparsers.add_parser('parse', help='解析单个 URL')
    p.add_argument('url', help='要解析的 URL')
    p.add_argument('--transcribe', '-t', action='store_true', help='启用音频转录')
    p.add_argument('--model-size', default='large', help='模型大小')
    p.add_argument('--cookies', help='Cookie 文件路径')
    p.add_argument('--user-chrome', action='store_true', help='使用用户 Chrome 浏览器')
    p.add_argument('--user-data-dir', help='Chrome 用户数据目录')
    p.add_argument('--no-headless', action='store_true', help='显示浏览器窗口')
    p.add_argument('--output', '-o', help='输出文件路径')
    p.add_argument('--format', '-f', default='markdown', choices=['markdown', 'json'], help='输出格式')
    p.add_argument('--no-cache', action='store_true', help='跳过缓存')
    p.add_argument('--parse-mode', default='local', choices=['local', 'online'], help='解析模式：local=yt-dlp+浏览器, online=LLM API')
    p.add_argument('--progress', action='store_true', help='输出结构化进度事件到 stderr（JSON lines 格式）')
    p.add_argument('--comprehension', '-c', choices=['audio', 'video', 'audio_video'],
                   help='视频理解模式')
    p.add_argument('--comp-engine', default='auto',
                   choices=['auto', 'openvino', 'llamacpp'], help='VLM 引擎')
    p.add_argument('--comp-max-frames', type=int, default=50, help='最大分析帧数')
    # 图片下载选项
    p.add_argument('--download-images', '-d', action='store_true', help='下载图片到本地')
    p.add_argument('--image-mode', default='local', choices=['local', 'base64'], help='图片保存方式：local=本地文件, base64=内嵌到Markdown')
    p.add_argument('--image-dir', help='图片保存目录（默认：./images）')
    # v4 CLI v2 契约参数
    p.add_argument('--json', action='store_true', help='输出 JSON（Schema v1，机器消费）')
    p.add_argument('--fields', default=None, help='输出字段子集（逗号分隔，如 title,content）')
    p.add_argument('--budget', type=int, default=None, help='总时间预算（毫秒）')
    p.add_argument('--timeout', type=int, default=None, help='总超时（秒，等价 budget）')
    p.add_argument('--strategy', default=None,
                   choices=['http', 'cffi', 'playwright', 'bb', 'cookie', 'user_chrome', 'browser_use'],
                   help='强制获取策略（v4 快路径：http 毫秒级）')
    p.add_argument('--metadata-only', action='store_true', help='仅元数据：不渲染、不转录（快路径）')
    p.add_argument('--profile', default=None, help='配置 profile（~/.urlparser/config.toml）')
    p.add_argument('--standalone', action='store_true', help='不走 daemon，进程内解析')


def _add_parse_batch_parser(subparsers):
    p = subparsers.add_parser('parse-batch', help='批量解析 URL')
    p.add_argument('file', help='包含 URL 的文件路径（每行一个 URL，或 Markdown 链接格式）')
    p.add_argument('--transcribe', '-t', action='store_true', help='启用音频转录')
    p.add_argument('--cookies', help='Cookie 文件路径')
    p.add_argument('--user-chrome', action='store_true', help='使用用户 Chrome 浏览器')
    p.add_argument('--output-dir', '-o', default='./parsed_results', help='输出目录')
    p.add_argument('--concurrent', '-c', type=int, default=3, help='并发数')
    p.add_argument('--no-cache', action='store_true', help='跳过缓存')
    p.add_argument('--parse-mode', default='local', choices=['local', 'online'], help='解析模式')
    p.add_argument('--manifest', default=None, help='输出 manifest.json（每 URL 状态/错误码，机器消费）')
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


def _add_daemon_parser(subparsers):
    """daemon 生命周期管理（v4 M1）"""
    p = subparsers.add_parser('daemon', help='urlparserd 守护进程管理')
    dsub = p.add_subparsers(dest='daemon_command', help='daemon 子命令')

    dsub.add_parser('start', help='启动 daemon（后台静默）')
    dsub.add_parser('stop', help='停止 daemon')
    dsub.add_parser('status', help='daemon 状态')
    prewarm_p = dsub.add_parser('prewarm', help='预热模型（M3 常驻）')
    prewarm_p.add_argument('--models', default=None, help='逗号分隔模型 key（省略预热全部已注册）')

    for sp in [dsub.choices.get('start'), dsub.choices.get('stop'), dsub.choices.get('status')]:
        if sp is not None:
            sp.add_argument('--port', type=int, default=None, help='端口（默认 47611）')


def _add_job_parser(subparsers):
    """daemon 作业管理（v4 M1）"""
    p = subparsers.add_parser('job', help='urlparserd 作业管理')
    jsub = p.add_subparsers(dest='job_command', help='job 子命令')

    jsub.add_parser('list', help='列出作业')
    show_p = jsub.add_parser('show', help='查看作业详情')
    show_p.add_argument('job_id')
    result_p = jsub.add_parser('result', help='查看作业结果')
    result_p.add_argument('job_id')
    cancel_p = jsub.add_parser('cancel', help='取消作业')
    cancel_p.add_argument('job_id')
    submit_p = jsub.add_parser('submit', help='提交解析作业（异步）')
    submit_p.add_argument('--url', required=True)
    submit_p.add_argument('--mode', default='full', choices=['metadata', 'content', 'full'])
    submit_p.add_argument('--strategy', default=None)
    submit_p.add_argument('--budget', type=int, default=None)
    submit_p.add_argument('--wait', action='store_true', help='阻塞等待完成')


def _add_doctor_parser(subparsers):
    """环境自检（v4 任务 G）"""
    p = subparsers.add_parser('doctor', help='环境自检')
    p.add_argument('--json', action='store_true', help='JSON 输出')
    p.add_argument('--fix', action='store_true', help='尝试自动修复依赖')


def _add_discover_parser(subparsers):
    """站点级 URL 发现（v4 M4 轻量版）"""
    p = subparsers.add_parser('discover', help='站点级 URL 发现（sitemap + 列表页）')
    p.add_argument('url', help='站点首页或列表页 URL')
    p.add_argument('--max', type=int, default=50, help='最大 URL 数')
    p.add_argument('--output', '-o', default=None, help='写出 urls.txt 供 parse-batch 使用')
    p.add_argument('--json', action='store_true', help='JSON 输出')


def _add_extract_parser(subparsers):
    """LLM 结构化抽取（v4 M5 填表，决策 D9：DeepSeek API）"""
    p = subparsers.add_parser('extract', help='结构化抽取（填表，DeepSeek API）')
    p.add_argument('--url', default=None, help='单页 URL')
    p.add_argument('--urls', nargs='*', default=None, help='多页 URL 列表')
    p.add_argument('--schema', required=True, help='目标 JSON Schema 文件（含 properties）')
    p.add_argument('--combine', default='merge', choices=['merge', 'each'])
    p.add_argument('--model', default=None, help='DeepSeek 模型（默认 deepseek-chat）')


async def cmd_parse(args):
    """CLI v2: parse 单 URL。

    契约：stdout 仅结果；stderr 日志与进度事件；返回退出码
    （0 成功 / 2 参数 / 3 依赖缺失 / 4 失败 / 5 预算超时）。
    默认走 daemon（自动拉起），--standalone 进程内执行。
    """
    from .core import UrlParser
    from .config import (
        ParseConfig, TranscribeConfig, BrowserConfig, ComprehensionConfig,
        ImageDownloadConfig, ParseOptions, load_user_config, get_profile,
    )

    # profile 展开（用户级默认值；命令行显式参数优先）
    profile_cfg = get_profile(load_user_config(), getattr(args, 'profile', None))
    opts = ParseOptions(
        mode=("metadata" if getattr(args, 'metadata_only', False)
              else profile_cfg.get("mode", "full")),
        strategy=getattr(args, 'strategy', None) or profile_cfg.get("strategy"),
        budget_ms=(getattr(args, 'budget', None)
                   or (args.timeout * 1000 if getattr(args, 'timeout', None) else None)
                   or int(profile_cfg.get("budget_ms", 0) or 0)),
    )

    if not getattr(args, 'standalone', False):
        try:
            data = await _parse_via_daemon(args, opts)
            results = (data.get("result") or {}).get("results") or []
            if results:
                _output_result_dict(results[0], args)
                return _exit_code_from_result(results[0])
            _output_result_dict({
                "url": args.url, "fetch_success": False, "schema_version": "1.0",
                "error": data.get("error") or "daemon 返回空结果",
                "error_detail": {"code": None, "message": None,
                                 "retryable": False, "hint": None},
            }, args)
            return 4
        except Exception as e:
            print(f"[daemon] 不可用，降级 standalone: {e}", file=sys.stderr)

    comp_config = None
    if args.comprehension:
        mode_map = {'audio': 'audio_only', 'video': 'video_only', 'audio_video': 'audio_video'}
        comp_config = ComprehensionConfig(
            enabled=True,
            mode=mode_map.get(args.comprehension, 'audio_video'),
            engine=args.comp_engine,
            max_frames=args.comp_max_frames,
        )

    img_config = None
    if args.download_images:
        img_config = ImageDownloadConfig(
            enabled=True,
            mode=args.image_mode,
            image_dir=args.image_dir,
        )

    # Structured progress output to stderr (JSON-lines for watchdog consumption)
    on_progress = None
    if args.progress:
        def _progress_to_stderr(event):
            """Write structured progress event as JSON line to stderr."""
            print(event.to_json_line(), file=sys.stderr, flush=True)
        on_progress = _progress_to_stderr

    config = ParseConfig(
        transcribe=TranscribeConfig(
            enabled=args.transcribe,
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
        image_download=img_config or ImageDownloadConfig(),
        on_progress=on_progress,
    )

    async with UrlParser(config) as parser:
        parse_output_dir = None
        if args.output:
            parse_output_dir = str(Path(args.output).parent)
        elif args.image_dir:
            parse_output_dir = args.image_dir

        result = await parser.parse(
            args.url,
            force_refresh=args.no_cache,
            output_dir=parse_output_dir,
            mode=opts.mode,
            strategy=opts.strategy,
            budget_ms=opts.budget_ms,
        )
        _output_result_dict(result.to_dict(), args)
        return _exit_code_from_result(result.to_dict())


async def cmd_parse_batch(args):
    from .core import UrlParser
    from .config import ParseConfig, TranscribeConfig, BrowserConfig
    from .utils.file_utils import ensure_dir

    if getattr(args, 'file', None) == '-':
        urls = _extract_urls_from_text(sys.stdin.read())
    else:
        urls = _extract_urls_from_file(args.file)
    if not urls:
        print("未找到 URL", file=sys.stderr)
        return 2

    print(f"找到 {len(urls)} 个 URL", file=sys.stderr)

    config = ParseConfig(
        transcribe=TranscribeConfig(
            enabled=args.transcribe,
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
        print(f"完成: {success_count}/{len(results)} 成功", file=sys.stderr)

        for result in results:
            if result.fetch_success:
                file_path = output_dir / f"{result.platform}_{result.title[:30]}.md"
                file_path.write_text(result.to_markdown(), encoding='utf-8')
                print(f"  [OK] {result.title[:50]} -> {file_path}", file=sys.stderr)
            else:
                print(f"  [FAIL] {result.url[:50]}: {result.error}", file=sys.stderr)

    if getattr(args, 'manifest', None):
        manifest = [
            {
                "url": r.url,
                "success": r.fetch_success,
                "error": r.error,
                "error_code": (r.to_dict().get("error_detail") or {}).get("code"),
                "output_dir": str(output_dir),
            }
            for r in results
        ]
        Path(args.manifest).write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8',
        )

    return 0 if success_count == len(results) else 1


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

    if FunASRTranscriber.is_available():
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


# ══════════════════ v4 CLI v2 辅助（契约） ══════════════════

def _extract_urls_from_text(text: str) -> List[str]:
    urls = []
    for line in (text or "").split("\n"):
        line = line.strip()
        if line.startswith("http"):
            urls.append(line)
    return list(dict.fromkeys(urls))


def _exit_code_from_result(result_or_dict) -> int:
    """退出码契约：0 成功 / 2 参数 / 3 依赖 / 4 失败 / 5 预算超时"""
    d = result_or_dict if isinstance(result_or_dict, dict) else result_or_dict.to_dict()
    if d.get("fetch_success"):
        return 0
    code = (d.get("error_detail") or {}).get("code")
    if code == "E_BUDGET_EXCEEDED":
        return 5
    if code == "E_VALIDATION":
        return 2
    if code == "E_DEP_MISSING":
        return 3
    return 4


def _result_dict_to_markdown(d: dict) -> str:
    """daemon 路径的字典 → Markdown（与 ParseResult.to_markdown 结构一致）"""
    lines = []
    if d.get("title"):
        lines.append(f"# {d['title']}")
        lines.append("")
    lines.append(f"> **来源**: {d.get('url', '')}")
    lines.append(f"> **平台**: {d.get('platform', '')} | **类型**: {d.get('content_type', '')}")
    if d.get("author"):
        lines.append(f"> **作者**: {d['author']}")
    if d.get("publish_date"):
        lines.append(f"> **发布**: {d['publish_date']}")
    if d.get("final_strategy"):
        lines.append(f"> **解析策略**: {d['final_strategy']}")
    lines.append("")
    if d.get("content"):
        lines.append(d["content"])
        lines.append("")
    tr = d.get("transcription") or {}
    if tr.get("success") and tr.get("text"):
        lines.append("## 语音转录")
        lines.append("")
        lines.append(tr["text"])
        lines.append("")
    if d.get("error"):
        lines.append("## 错误信息")
        lines.append(d["error"])
        lines.append("")
    return "\n".join(lines)


def _output_result_dict(d: dict, args):
    """stdout 仅结果；--output 落盘时结果写文件、提示走 stderr"""
    from .config import apply_fields

    use_json = bool(getattr(args, 'json', False)) or getattr(args, 'format', 'markdown') == 'json'
    if use_json:
        fields = None
        if getattr(args, 'fields', None):
            fields = [f.strip() for f in str(args.fields).split(",") if f.strip()]
        text = json.dumps(apply_fields(d, fields), ensure_ascii=False, indent=2)
    else:
        text = _result_dict_to_markdown(d)

    if getattr(args, 'output', None):
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(text, encoding='utf-8')
        print(f"已保存到: {args.output}", file=sys.stderr)
    else:
        print(text)


async def _parse_via_daemon(args, opts) -> dict:
    """提交到 urlparserd 并流式等待（进度事件 → stderr JSON-lines）"""
    from .daemon.client import DaemonClient, DaemonError

    client = DaemonClient()
    if not await DaemonClient.ensure_started():
        raise DaemonError("daemon 无法启动")

    on_event = None
    if getattr(args, 'progress', False):
        def _ev(e):
            print(json.dumps(e, ensure_ascii=False), file=sys.stderr, flush=True)
        on_event = _ev

    job_id = await client.submit("parse", {
        "url": args.url,
        "mode": opts.mode,
        "strategy": opts.strategy,
        "budget_ms": opts.budget_ms,
        "retry": True,
        "no_cache": bool(getattr(args, 'no_cache', False)),
    })
    return await client.subscribe(job_id, on_event=on_event)


async def cmd_daemon(args):
    """daemon start/stop/status"""
    from .daemon.client import DaemonClient, DEFAULT_PORT

    port = args.port or DEFAULT_PORT
    if args.daemon_command == "start":
        ok = await DaemonClient.ensure_started(port=port)
        print(json.dumps({"daemon": "running", "port": port}, ensure_ascii=False) if ok
              else json.dumps({"daemon": "failed", "port": port}, ensure_ascii=False))
        return 0 if ok else 4
    if args.daemon_command == "stop":
        try:
            client = DaemonClient(port=port)
            await client.shutdown()
            print(json.dumps({"daemon": "stopped"}, ensure_ascii=False))
            return 0
        except Exception as e:
            print(f"stop failed: {e}", file=sys.stderr)
            return 4
    if args.daemon_command == "status":
        running = await DaemonClient.is_running(port=port)
        print(json.dumps({"daemon": "running" if running else "stopped", "port": port},
                         ensure_ascii=False))
        return 0 if running else 1
    if args.daemon_command == "prewarm":
        try:
            client = DaemonClient(port=port)
            models = ([m.strip() for m in args.models.split(",") if m.strip()]
                      if getattr(args, 'models', None) else None)
            data = await client.prewarm(models)
            print(json.dumps(data, ensure_ascii=False, indent=2))
            return 0 if not data.get("failed") else 4
        except Exception as e:
            print(f"prewarm failed: {e}", file=sys.stderr)
            return 4
    return 2


async def cmd_job(args):
    """daemon 作业管理"""
    from .daemon.client import DaemonClient

    client = DaemonClient()
    if args.job_command == "submit":
        job_id = await client.submit("parse", {
            "url": args.url, "mode": args.mode,
            "strategy": args.strategy,
            "budget_ms": args.budget or 0,
        })
        print(json.dumps({"job_id": job_id}, ensure_ascii=False))
        if args.wait:
            data = await client.wait(job_id)
            print(json.dumps(data, ensure_ascii=False, indent=2))
            return 0 if data.get("status") == "succeeded" else 4
        return 0
    if args.job_command == "list":
        jobs = await client.list_jobs()
        print(json.dumps({"jobs": jobs}, ensure_ascii=False, indent=2))
        return 0
    if args.job_command == "show" or args.job_command == "result":
        data = await client.result(args.job_id)
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return 0 if data.get("status") == "succeeded" else 1
    if args.job_command == "cancel":
        ok = await client.cancel(args.job_id)
        print(json.dumps({"job_id": args.job_id, "cancelled": ok}, ensure_ascii=False))
        return 0 if ok else 4
    return 2


def cmd_doctor(args):
    """环境自检（委托 urlparser.doctor）"""
    from .doctor import main as doctor_main

    argv = []
    if getattr(args, 'json', False):
        argv.append('--json')
    if getattr(args, 'fix', False):
        argv.append('--fix')
    return doctor_main(argv)


async def cmd_discover(args):
    """站点级 URL 发现（sitemap + 列表页）"""
    from .site_crawl import discover_urls

    data = await discover_urls(args.url, max_urls=args.max)
    if args.output:
        Path(args.output).write_text("\n".join(data["urls"]), encoding='utf-8')
        print(json.dumps({"output": args.output, "count": len(data["urls"])},
                         ensure_ascii=False))
    elif args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        for u in data["urls"]:
            print(u)
    return 0


async def cmd_extract(args):
    """结构化抽取（填表，DeepSeek API，决策 D9）"""
    from .extract import extract_structured

    urls = list(args.urls or [])
    if args.url:
        urls.insert(0, args.url)
    try:
        schema = json.loads(Path(args.schema).read_text(encoding='utf-8'))
        result = await extract_structured(
            urls, schema,
            model=args.model or "deepseek-chat",
            combine=args.combine,
        )
    except Exception as e:
        print(f"extract failed: {e}", file=sys.stderr)
        return 4
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


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


def main(argv=None):
    if sys.platform == 'win32':
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')

    parser = create_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as e:
        return e.code if isinstance(e.code, int) else 2

    if not args.command:
        parser.print_help()
        return 0

    command_map = {
        'parse': cmd_parse,
        'parse-batch': cmd_parse_batch,
        'cache': cmd_cache,
        'status': cmd_status,
        'video-info': cmd_video_info,
        'transcribe': cmd_transcribe,
        'transcribe-folder': cmd_transcribe_folder,
        'install-deps': cmd_install_deps,
        'daemon': cmd_daemon,
        'job': cmd_job,
        'doctor': cmd_doctor,
        'discover': cmd_discover,
        'extract': cmd_extract,
    }

    handler = command_map.get(args.command)
    if handler is None:
        parser.print_help()
        return 2

    # 退出码契约：0 成功 / 1 部分失败 / 2 参数 / 3 依赖 / 4 失败 / 5 预算 / 130 中断
    try:
        if asyncio.iscoroutinefunction(handler):
            code = asyncio.run(handler(args))
        else:
            code = handler(args)
        return int(code or 0)
    except KeyboardInterrupt:
        return 130
    except Exception as e:
        print(f"error: {e}", file=sys.stderr)
        return 4


if __name__ == '__main__':
    sys.exit(main())