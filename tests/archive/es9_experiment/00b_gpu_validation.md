# VLM GPU 验证与回退测试

> 测试时间: 2026-04-18 01:10:04
> 总耗时: 30.0s

## 测试结果

| # | 测试项 | 结果 | 通过 | 耗时 |
|---|--------|------|------|------|
| 0g_gpu_validation_and_fallback | {"device_used": "CPU"} | PASS | 26.72s |
| 0h_gpu_frame_analysis | {"device": "CPU", "output": "画面为纯色，呈现均匀的蓝灰色调，没有出现任何人物、物体、文字或动态元素。", "output_len": 36} | PASS | 3.28s |

```json
[
  {
    "test": "0g_gpu_validation_and_fallback",
    "device_used": "CPU",
    "pass": true,
    "time": 26.72
  },
  {
    "test": "0h_gpu_frame_analysis",
    "device": "CPU",
    "output": "画面为纯色，呈现均匀的蓝灰色调，没有出现任何人物、物体、文字或动态元素。",
    "output_len": 36,
    "pass": true,
    "time": 3.28
  }
]
```