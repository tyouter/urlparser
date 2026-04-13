import os
import sys
import time
import gc
import traceback
from pathlib import Path
from dataclasses import dataclass
from datetime import datetime

os.environ['KMP_DUPLICATE_LIB_OK'] = 'TRUE'
os.environ['MODELSCOPE_CACHE'] = str(Path.home() / '.cache' / 'modelscope')
os.environ['HF_HOME'] = str(Path.home() / '.cache' / 'huggingface')
os.environ['HUGGINGFACE_HUB_CACHE'] = str(Path.home() / '.cache' / 'huggingface' / 'hub')

SRC_DIR = Path(r'D:\PCN\UT')
OUT_DIR = Path(r'D:\PCN\UT transcribe')

AUDIO_EXTS = {'.mp3', '.wav', '.flac', '.aac', '.ogg', '.m4a', '.wma', '.opus'}
VIDEO_EXTS = {'.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm', '.m4v'}
MEDIA_EXTS = AUDIO_EXTS | VIDEO_EXTS

MAX_RETRIES = 3
RETRY_DELAY = 15


@dataclass
class MediaFile:
    src_path: Path
    rel_path: Path
    out_md_path: Path
    is_video: bool
    size_mb: float

    @property
    def already_done(self) -> bool:
        return self.out_md_path.exists()


def scan_media_files() -> list:
    files = []
    for f in sorted(SRC_DIR.rglob('*')):
        if f.is_file() and f.suffix.lower() in MEDIA_EXTS:
            rel = f.relative_to(SRC_DIR)
            out_md = OUT_DIR / rel.with_suffix('.md')
            size_mb = f.stat().st_size / (1024 * 1024)
            is_video = f.suffix.lower() in VIDEO_EXTS
            files.append(MediaFile(
                src_path=f,
                rel_path=rel,
                out_md_path=out_md,
                is_video=is_video,
                size_mb=size_mb,
            ))
    return files


def ensure_out_dir(md_path: Path):
    md_path.parent.mkdir(parents=True, exist_ok=True)


def write_empty_transcription(md_path: Path, src_path: Path, reason: str = ""):
    ensure_out_dir(md_path)
    lines = [
        f"# {src_path.stem}",
        "",
        "## 文件信息",
        "",
        f"- **类型**: {'视频' if src_path.suffix.lower() in VIDEO_EXTS else '音频'}",
        f"- **文件名**: {src_path.name}",
        f"- **源路径**: {src_path}",
        "",
        "## 转录正文",
        "",
        "（无转录内容 - 该文件无人声或转录失败）",
        "",
    ]
    if reason:
        lines.append(f"**备注**: {reason}")
        lines.append("")
    lines.append("---")
    lines.append("")
    lines.append(f"*生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*")
    md_path.write_text("\n".join(lines), encoding='utf-8')


def fmt_time(s):
    h = int(s // 3600)
    m = int((s % 3600) // 60)
    sec = int(s % 60)
    if h > 0:
        return f"{h:02d}:{m:02d}:{sec:02d}"
    return f"{m:02d}:{sec:02d}"


def write_transcription(md_path: Path, src_path: Path, result):
    ensure_out_dir(md_path)

    lines = [
        f"# {src_path.stem}",
        "",
        "## 文件信息",
        "",
        f"- **类型**: {'视频' if src_path.suffix.lower() in VIDEO_EXTS else '音频'}",
        f"- **文件名**: {src_path.name}",
        f"- **源路径**: {src_path}",
        "",
    ]

    if result.duration and result.duration > 0:
        from urlparser.utils.media_utils import format_duration_detailed
        lines.append(f"- **时长**: {format_duration_detailed(result.duration)}")

    if result.language:
        lines.append(f"- **语言**: {result.language}")

    lines.append("")
    lines.append("## 转录正文")
    lines.append("")

    if result.text and result.text.strip():
        lines.append(result.text.strip())
    else:
        lines.append("（无转录内容 - 该文件无人声）")

    lines.append("")

    if result.segments:
        lines.append(f"## 时间戳分段 ({len(result.segments)} 段)")
        lines.append("")
        for seg in result.segments[:200]:
            start = seg.get('start', 0)
            end = seg.get('end', 0)
            text = seg.get('text', '').strip()
            if text:
                lines.append(f"**[{fmt_time(start)} - {fmt_time(end)}]** {text}")
                lines.append("")

    lines.append("---")
    lines.append("")
    lines.append(f"*生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*")
    lines.append(f"*转录引擎: {result.engine}*")

    md_path.write_text("\n".join(lines), encoding='utf-8')


def transcribe_file(media: MediaFile, transcriber) -> bool:
    if media.already_done:
        print(f"  [SKIP] {media.rel_path} (already transcribed)")
        return True

    print(f"  [PROC] {media.rel_path} ({media.size_mb:.1f} MB)")

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            result = transcriber.transcribe(
                str(media.src_path),
                language="zh",
            )

            if result.success:
                write_transcription(media.out_md_path, media.src_path, result)
                text_preview = (result.text[:80] + "...") if result.text and len(result.text) > 80 else (result.text or "(empty)")
                print(f"  [OK] {media.rel_path} -> {text_preview}")
                return True
            else:
                error_msg = result.error or "unknown error"
                if attempt < MAX_RETRIES:
                    print(f"  [RETRY {attempt}/{MAX_RETRIES}] {media.rel_path}: {error_msg}")
                    time.sleep(RETRY_DELAY)
                else:
                    print(f"  [FAIL] {media.rel_path}: {error_msg}")
                    write_empty_transcription(media.out_md_path, media.src_path, f"转录失败: {error_msg}")
                    return True

        except Exception as e:
            error_msg = str(e)
            if attempt < MAX_RETRIES:
                print(f"  [RETRY {attempt}/{MAX_RETRIES}] {media.rel_path}: {error_msg}")
                time.sleep(RETRY_DELAY)
            else:
                print(f"  [ERROR] {media.rel_path}: {error_msg}")
                traceback.print_exc()
                write_empty_transcription(media.out_md_path, media.src_path, f"转录异常: {error_msg}")
                return True
        finally:
            gc.collect()

    return False


def main():
    print("=" * 70)
    print("批量音视频转录")
    print(f"  源目录: {SRC_DIR}")
    print(f"  输出目录: {OUT_DIR}")
    print(f"  时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    media_files = scan_media_files()
    audio_count = sum(1 for m in media_files if not m.is_video)
    video_count = sum(1 for m in media_files if m.is_video)

    print(f"\n扫描结果: {len(media_files)} 个文件 ({audio_count} 音频, {video_count} 视频)")

    already_done = sum(1 for m in media_files if m.already_done)
    pending = [m for m in media_files if not m.already_done]
    print(f"已完成: {already_done}, 待处理: {len(pending)}")

    if not pending:
        print("\n所有文件已完成转录!")
        verify()
        return

    print(f"\n初始化 FunASR 转录引擎...")
    from urlparser.transcriber import FunASRTranscriber
    transcriber = FunASRTranscriber(model_size="large", device="auto")

    print(f"\n开始转录 {len(pending)} 个文件...\n")

    start_time = time.time()
    success_count = 0
    fail_count = 0

    for i, media in enumerate(pending, 1):
        elapsed = time.time() - start_time
        if i > 1:
            avg_per_file = elapsed / (i - 1)
            eta = avg_per_file * (len(pending) - i + 1)
            eta_str = fmt_time(eta)
        else:
            eta_str = "unknown"

        print(f"\n[{i}/{len(pending)}] ETA: {eta_str}")
        ok = transcribe_file(media, transcriber)
        if ok:
            success_count += 1
        else:
            fail_count += 1

    elapsed = time.time() - start_time

    print("\n" + "=" * 70)
    print("转录完成!")
    print(f"  成功: {success_count}")
    print(f"  失败: {fail_count}")
    print(f"  耗时: {fmt_time(elapsed)}")
    print("=" * 70)

    verify()


def verify() -> bool:
    media_files = scan_media_files()
    missing = [m for m in media_files if not m.already_done]
    if missing:
        print(f"\n缺少转录文件的音视频: {len(missing)} 个")
        for m in missing[:30]:
            print(f"  {m.rel_path}")
        if len(missing) > 30:
            print(f"  ... 还有 {len(missing) - 30} 个")
        return False
    print(f"\n验证通过: 全部 {len(media_files)} 个音视频文件都有对应的转录文件")
    return True


if __name__ == '__main__':
    main()
