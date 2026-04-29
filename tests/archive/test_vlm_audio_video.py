import os, sys, time
os.environ['KMP_DUPLICATE_LIB_OK'] = 'TRUE'

from datetime import datetime
from urlparser.comprehension import (
    ComprehensionPipeline, ComprehensionConfig,
    detect_hardware, select_model, resolve_model_path,
)
from urlparser.transcriber import FunASRTranscriber

TEST_URL = 'https://www.bilibili.com/video/BV1d5QvBnENK/'
OUTPUT_DIR = r'd:\projects\claude\urlparser\tests\ES9新车发布会'

start = time.time()

print('=' * 60)
print('Test 4: VLM Video Comprehension - audio_video mode')
print('=' * 60)

hw = detect_hardware()
model_id, backend, device = select_model(hw)
model_path = resolve_model_path(model_id)

print(f'Hardware: {hw.name}')
print(f'Model: {model_id}, Backend: {backend.value}, Device: {device}')

print('\nStep 1: Audio transcription with FunASR...')
transcriber = FunASRTranscriber(model_size='sensevoice', device='cpu')
transcription_result = transcriber.transcribe_from_url(TEST_URL, language='zh')
print(f'Audio transcription: success={transcription_result.success}, text_len={len(transcription_result.text) if transcription_result.text else 0}')

print('\nStep 2: Video comprehension with audio_video mode...')
config = ComprehensionConfig(
    mode='audio_video',
    engine='auto',
    max_frames=20,
)

pipeline = ComprehensionPipeline(config)

t0 = time.time()
try:
    result = pipeline.comprehend_from_url(TEST_URL, transcription_result=transcription_result)
    elapsed = round(time.time() - t0, 2)

    print(f'Success: {result.success}')
    if result.error:
        print(f'Error: {result.error}')
    if result.visual_frames:
        print(f'Frames analyzed: {len(result.visual_frames)}')
    if result.timeline_summary:
        print(f'Timeline summary length: {len(result.timeline_summary)}')
    if result.merged_text:
        print(f'Merged text length: {len(result.merged_text)}')
        print(f'Merged preview: {result.merged_text[:300]}...')

    output_file = os.path.join(OUTPUT_DIR, '04_vlm_audio_video.md')
    lines = ['# VLM 视频理解测试 - audio_video 模式', '']
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    lines.append(f'> 测试时间: {now_str}')
    lines.append(f'> 测试URL: {TEST_URL}')
    lines.append(f'> 硬件: {hw.name}')
    lines.append(f'> 模型: {model_id} ({backend.value})')
    lines.append(f'> 设备: {device}')
    lines.append(f'> 耗时: {elapsed}s')
    lines.append('')

    lines.append('## 测试结果')
    lines.append('')
    lines.append(f'- 成功: {"是" if result.success else "否"}')
    if result.error:
        lines.append(f'- 错误: {result.error}')
    lines.append(f'- 分析帧数: {len(result.visual_frames) if result.visual_frames else 0}')
    lines.append(f'- 引擎: {result.engine}')
    lines.append('')

    if result.visual_frames:
        lines.append('## 帧分析结果')
        lines.append('')
        for i, frame in enumerate(result.visual_frames):
            ts = frame.timestamp
            h = int(ts // 3600)
            m = int((ts % 3600) // 60)
            s = int(ts % 60)
            lines.append(f'### 帧 {i+1} [{h:02d}:{m:02d}:{s:02d}]')
            lines.append('')
            lines.append(frame.description)
            lines.append('')

    if result.timeline_summary:
        lines.append('## 时间轴摘要')
        lines.append('')
        lines.append(result.timeline_summary)

    if result.merged_text:
        lines.append('## 合并时间轴（音频+画面）')
        lines.append('')
        lines.append(result.merged_text)

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))

    print(f'\nWritten to {output_file}')

except Exception as e:
    elapsed = round(time.time() - t0, 2)
    print(f'Error: {e}')
    import traceback
    traceback.print_exc()

    output_file = os.path.join(OUTPUT_DIR, '04_vlm_audio_video.md')
    lines = ['# VLM 视频理解测试 - audio_video 模式', '']
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
