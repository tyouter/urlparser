import os, sys, time, asyncio
os.environ['KMP_DUPLICATE_LIB_OK'] = 'TRUE'

from datetime import datetime

TEST_URL = 'https://www.bilibili.com/video/BV1d5QvBnENK/'
OUTPUT_DIR = r'd:\projects\claude\urlparser\tests\ES9新车发布会'

start = time.time()

print('=' * 60)
print('Test 5: parse command full workflow')
print('=' * 60)

from urlparser.core import UrlParser
from urlparser.config import ParseConfig, TranscribeConfig, BrowserConfig, ComprehensionConfig

comp_config = ComprehensionConfig(
    enabled=True,
    mode='audio_video',
    engine='auto',
    max_frames=20,
)

config = ParseConfig(
    transcribe=TranscribeConfig(
        enabled=True,
        engine='funasr',
        model_size='sensevoice',
    ),
    browser=BrowserConfig(
        headless=True,
    ),
    comprehension=comp_config,
)

async def run_test():
    t0 = time.time()
    try:
        async with UrlParser(config) as parser:
            result = await parser.parse(TEST_URL)

        elapsed = round(time.time() - t0, 2)

        print(f'Success: {result.success if hasattr(result, "success") else "N/A"}')
        print(f'Type: {type(result).__name__}')

        if hasattr(result, 'transcription') and result.transcription:
            print(f'Transcription: success={result.transcription.success}')
            if result.transcription.text:
                print(f'Transcription text length: {len(result.transcription.text)}')

        if hasattr(result, 'comprehension') and result.comprehension:
            print(f'Comprehension: success={result.comprehension.success}')
            if result.comprehension.visual_frames:
                print(f'Visual frames: {len(result.comprehension.visual_frames)}')
            if result.comprehension.merged_text:
                print(f'Merged text length: {len(result.comprehension.merged_text)}')

        output_file = os.path.join(OUTPUT_DIR, '05_full_pipeline.md')
        lines = ['# parse 命令全流程测试', '']
        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        lines.append(f'> 测试时间: {now_str}')
        lines.append(f'> 测试URL: {TEST_URL}')
        lines.append(f'> 耗时: {elapsed}s')
        lines.append('')

        lines.append('## 测试结果')
        lines.append('')

        if hasattr(result, 'success'):
            lines.append(f'- 成功: {"是" if result.success else "否"}')

        if hasattr(result, 'error') and result.error:
            lines.append(f'- 错误: {result.error}')

        if hasattr(result, 'transcription') and result.transcription:
            t = result.transcription
            lines.append(f'- 转录成功: {"是" if t.success else "否"}')
            if t.text:
                lines.append(f'- 转录文本长度: {len(t.text)}')
            lines.append('')
            lines.append('## 转录文本')
            lines.append('')
            if t.text:
                lines.append(t.text)

        if hasattr(result, 'comprehension') and result.comprehension:
            c = result.comprehension
            lines.append('')
            lines.append('## 视频理解')
            lines.append('')
            lines.append(f'- 成功: {"是" if c.success else "否"}')
            if c.visual_frames:
                lines.append(f'- 分析帧数: {len(c.visual_frames)}')
                for i, frame in enumerate(c.visual_frames):
                    ts = frame.timestamp
                    h = int(ts // 3600)
                    m = int((ts % 3600) // 60)
                    s = int(ts % 60)
                    lines.append(f'  - [{h:02d}:{m:02d}:{s:02d}] {frame.description[:80]}...' if len(frame.description) > 80 else f'  - [{h:02d}:{m:02d}:{s:02d}] {frame.description}')
            if c.merged_text:
                lines.append('')
                lines.append('## 合并时间轴')
                lines.append('')
                lines.append(c.merged_text)

        with open(output_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))

        print(f'\nWritten to {output_file}')

    except Exception as e:
        elapsed = round(time.time() - t0, 2)
        print(f'Error: {e}')
        import traceback
        traceback.print_exc()

        output_file = os.path.join(OUTPUT_DIR, '05_full_pipeline.md')
        lines = ['# parse 命令全流程测试', '']
        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        lines.append(f'> 测试时间: {now_str}')
        lines.append(f'> 耗时: {elapsed}s')
        lines.append('')
        lines.append('## 测试结果')
        lines.append('')
        lines.append('- 成功: 否')
        lines.append(f'- 错误: {str(e)}')

        with open(output_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))

        print(f'\nWritten to {output_file}')

asyncio.run(run_test())
