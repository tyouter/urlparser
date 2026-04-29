import os, time, json
os.environ['KMP_DUPLICATE_LIB_OK'] = 'TRUE'

from datetime import datetime
from urlparser.comprehension.vlm_engine import OpenVINOEngine
from urlparser.comprehension.models import resolve_model_path

results = []
start = time.time()

model_path = resolve_model_path('qwen3-vl-2b-int4')
print(f'Model path: {model_path}')
print(f'Exists: {os.path.exists(model_path)}')

engine = OpenVINOEngine()

t0 = time.time()
try:
    engine.load_model(model_path, device='GPU')
    results.append({
        'test': '0g_gpu_validation_and_fallback',
        'device_used': engine._device,
        'pass': engine._loaded,
        'time': round(time.time() - t0, 2),
    })
    print(f'Device selected: {engine._device}')
    print(f'Loaded: {engine._loaded}')
except Exception as e:
    results.append({
        'test': '0g_gpu_validation_and_fallback',
        'error': str(e),
        'pass': False,
        'time': round(time.time() - t0, 2),
    })
    print(f'Error: {e}')

if engine._loaded:
    t0 = time.time()
    try:
        test_img = r'd:\projects\claude\urlparser\tests\test_frame.jpg'
        if not os.path.exists(test_img):
            from PIL import Image
            img = Image.new('RGB', (640, 480), color=(73, 109, 137))
            img.save(test_img)

        result_text = engine.analyze_frame(test_img)
        results.append({
            'test': '0h_gpu_frame_analysis',
            'device': engine._device,
            'output': result_text[:200],
            'output_len': len(result_text),
            'pass': len(result_text) > 5,
            'time': round(time.time() - t0, 2),
        })
        print(f'Frame analysis result: {result_text[:200]}')
    except Exception as e:
        results.append({
            'test': '0h_gpu_frame_analysis',
            'error': str(e),
            'pass': False,
            'time': round(time.time() - t0, 2),
        })
        print(f'Frame analysis error: {e}')

lines = ['# VLM GPU 验证与回退测试', '']
now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
total_time = round(time.time() - start, 2)
lines.append(f'> 测试时间: {now_str}')
lines.append(f'> 总耗时: {total_time}s')
lines.append('')

lines.append('## 测试结果')
lines.append('')
lines.append('| # | 测试项 | 结果 | 通过 | 耗时 |')
lines.append('|---|--------|------|------|------|')
for r in results:
    test = r['test']
    result_str = json.dumps({k: v for k, v in r.items() if k not in ('test', 'pass', 'time')}, ensure_ascii=False)
    passed = 'PASS' if r['pass'] else 'FAIL'
    lines.append(f'| {test} | {result_str[:100]} | {passed} | {r["time"]}s |')

lines.append('')
lines.append('```json')
lines.append(json.dumps(results, ensure_ascii=False, indent=2))
lines.append('```')

output_path = r'd:\projects\claude\urlparser\tests\ES9新车发布会\00b_gpu_validation.md'
with open(output_path, 'w', encoding='utf-8') as f:
    f.write('\n'.join(lines))

print(f'\nWritten to {output_path}')
passed_count = sum(1 for r in results if r['pass'])
failed_count = sum(1 for r in results if not r['pass'])
print(f'Total: {len(results)}, Passed: {passed_count}, Failed: {failed_count}')
