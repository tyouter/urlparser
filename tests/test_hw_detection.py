import os, time, json
os.environ['KMP_DUPLICATE_LIB_OK'] = 'TRUE'

from datetime import datetime
from urlparser.comprehension.models import (
    detect_hardware, select_model, resolve_model_path,
    HardwareProfile, VLMBackend, ComprehensionConfig
)

results = []
start = time.time()

t0 = time.time()
hw = detect_hardware()
results.append({
    'test': '0a_detect_hardware',
    'result': hw.name,
    'value': hw.value,
    'expected': 'One of INTEL_NPU, INTEL_IGPU, CPU_HIGH, CPU_LOW',
    'pass': hw in list(HardwareProfile),
    'time': round(time.time() - t0, 2),
})

t0 = time.time()
model_id, backend, device = select_model(hw)
results.append({
    'test': '0b_select_model_auto',
    'result': {'model_id': model_id, 'backend': backend.value, 'device': device},
    'pass': model_id is not None and backend in list(VLMBackend),
    'time': round(time.time() - t0, 2),
})

t0 = time.time()
config_ov = ComprehensionConfig(engine='openvino')
model_id2, backend2, device2 = select_model(hw, config_ov)
results.append({
    'test': '0c_select_model_openvino',
    'result': {'model_id': model_id2, 'backend': backend2.value, 'device': device2},
    'expected': 'backend=OPENVINO',
    'pass': backend2 == VLMBackend.OPENVINO,
    'time': round(time.time() - t0, 2),
})

t0 = time.time()
config_ll = ComprehensionConfig(engine='llamacpp')
model_id3, backend3, device3 = select_model(hw, config_ll)
results.append({
    'test': '0d_select_model_llamacpp',
    'result': {'model_id': model_id3, 'backend': backend3.value, 'device': device3},
    'expected': 'backend=LLAMACPP',
    'pass': backend3 == VLMBackend.LLAMACPP,
    'time': round(time.time() - t0, 2),
})

for mid, label in [(model_id2, 'openvino'), (model_id3, 'llamacpp')]:
    t0 = time.time()
    path = resolve_model_path(mid)
    exists = os.path.exists(path)
    results.append({
        'test': f'0e_resolve_model_path_{label}',
        'model_id': mid,
        'path': path,
        'exists': exists,
        'pass': exists,
        'time': round(time.time() - t0, 2),
    })

try:
    import openvino as ov
    core = ov.Core()
    devices = core.available_devices
    results.append({
        'test': '0f_openvino_devices',
        'result': devices,
        'pass': len(devices) > 0,
        'time': 0,
    })
except ImportError:
    results.append({
        'test': '0f_openvino_devices',
        'result': 'OpenVINO not installed',
        'pass': False,
        'time': 0,
    })

lines = ['# 硬件检测与动态模型选择测试', '']
now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
total_time = round(time.time() - start, 2)
lines.append(f'> 测试时间: {now_str}')
lines.append(f'> 总耗时: {total_time}s')
lines.append('')

lines.append('## 测试结果汇总')
lines.append('')
lines.append('| # | 测试项 | 结果 | 通过 | 耗时 |')
lines.append('|---|--------|------|------|------|')
for r in results:
    test = r['test']
    result_val = r.get('result', r.get('path', r.get('model_id', '')))
    if isinstance(result_val, (dict, list)):
        result_str = json.dumps(result_val, ensure_ascii=False)
    else:
        result_str = str(result_val)
    passed = 'PASS' if r['pass'] else 'FAIL'
    lines.append(f'| {test} | {result_str[:80]} | {passed} | {r["time"]}s |')

lines.append('')
lines.append('## 详细结果')
lines.append('')
lines.append('```json')
lines.append(json.dumps(results, ensure_ascii=False, indent=2))
lines.append('```')

output_path = r'd:\projects\claude\urlparser\tests\ES9新车发布会\00_hardware_detection.md'
with open(output_path, 'w', encoding='utf-8') as f:
    f.write('\n'.join(lines))

print(f'Written to {output_path}')
passed_count = sum(1 for r in results if r['pass'])
failed_count = sum(1 for r in results if not r['pass'])
print(f'Total tests: {len(results)}, Passed: {passed_count}, Failed: {failed_count}')
