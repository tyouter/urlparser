import os, sys, time, json
os.environ['KMP_DUPLICATE_LIB_OK'] = 'TRUE'

from datetime import datetime

TEST_URL = 'https://www.bilibili.com/video/BV1d5QvBnENK/'
OUTPUT_DIR = r'd:\projects\claude\urlparser\tests\ES9新车发布会'

start = time.time()

print('=' * 60)
print('Test 1: FunASR Audio Transcription')
print('=' * 60)

from urlparser.transcriber import FunASRTranscriber
from urlparser.dependency_installer import ensure_transcribe_dependencies

if not ensure_transcribe_dependencies(auto_install=True):
    print('FAILED: Dependencies not available')
    sys.exit(1)

transcriber = FunASRTranscriber(model_size='sensevoice', device='cpu')
print(f'Engine: {transcriber.engine_name}')

t0 = time.time()
result = transcriber.transcribe_from_url(TEST_URL, language='zh')
elapsed = round(time.time() - t0, 2)

print(f'Success: {result.success}')
print(f'Engine: {result.engine}')
if result.error:
    print(f'Error: {result.error}')
if result.text:
    print(f'Text length: {len(result.text)}')
    print(f'Text preview: {result.text[:300]}...')
if result.segments:
    print(f'Segments: {len(result.segments)}')

output_file = os.path.join(OUTPUT_DIR, '01_funasr_transcription.md')
lines = ['# FunASR 音频转录测试', '']
now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
lines.append(f'> 测试时间: {now_str}')
lines.append(f'> 测试URL: {TEST_URL}')
lines.append(f'> 引擎: FunASR (SenseVoice)')
lines.append(f'> 耗时: {elapsed}s')
lines.append('')

lines.append('## 测试结果')
lines.append('')
lines.append(f'- 成功: {"是" if result.success else "否"}')
lines.append(f'- 引擎: {result.engine}')
if result.error:
    lines.append(f'- 错误: {result.error}')
lines.append(f'- 文本长度: {len(result.text) if result.text else 0}')
lines.append(f'- 分段数: {len(result.segments) if result.segments else 0}')
lines.append('')

if result.text:
    lines.append('## 转录文本')
    lines.append('')
    lines.append(result.text)

with open(output_file, 'w', encoding='utf-8') as f:
    f.write('\n'.join(lines))

print(f'\nWritten to {output_file}')
