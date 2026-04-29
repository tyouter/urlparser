# 硬件检测与动态模型选择测试

> 测试时间: 2026-04-18 01:08:30
> 总耗时: 0.21s

## 测试结果汇总

| # | 测试项 | 结果 | 通过 | 耗时 |
|---|--------|------|------|------|
| 0a_detect_hardware | INTEL_IGPU | PASS | 0.19s |
| 0b_select_model_auto | {"model_id": "qwen3-vl-2b-int4", "backend": "openvino", "device": "GPU"} | PASS | 0.0s |
| 0c_select_model_openvino | {"model_id": "qwen3-vl-2b-int4", "backend": "openvino", "device": "GPU"} | PASS | 0.0s |
| 0d_select_model_llamacpp | {"model_id": "smolvlm-2.2b-gguf-q4", "backend": "llamacpp", "device": "CPU"} | PASS | 0.0s |
| 0e_resolve_model_path_openvino | D:\projects\claude\urlparser\models\qwen3-vl-2b-int4 | PASS | 0.0s |
| 0e_resolve_model_path_llamacpp | D:\projects\claude\urlparser\models\smolvlm-2.2b-gguf-q4 | FAIL | 0.0s |
| 0f_openvino_devices | ["CPU", "GPU"] | PASS | 0s |

## 详细结果

```json
[
  {
    "test": "0a_detect_hardware",
    "result": "INTEL_IGPU",
    "value": "intel_igpu",
    "expected": "One of INTEL_NPU, INTEL_IGPU, CPU_HIGH, CPU_LOW",
    "pass": true,
    "time": 0.19
  },
  {
    "test": "0b_select_model_auto",
    "result": {
      "model_id": "qwen3-vl-2b-int4",
      "backend": "openvino",
      "device": "GPU"
    },
    "pass": true,
    "time": 0.0
  },
  {
    "test": "0c_select_model_openvino",
    "result": {
      "model_id": "qwen3-vl-2b-int4",
      "backend": "openvino",
      "device": "GPU"
    },
    "expected": "backend=OPENVINO",
    "pass": true,
    "time": 0.0
  },
  {
    "test": "0d_select_model_llamacpp",
    "result": {
      "model_id": "smolvlm-2.2b-gguf-q4",
      "backend": "llamacpp",
      "device": "CPU"
    },
    "expected": "backend=LLAMACPP",
    "pass": true,
    "time": 0.0
  },
  {
    "test": "0e_resolve_model_path_openvino",
    "model_id": "qwen3-vl-2b-int4",
    "path": "D:\\projects\\claude\\urlparser\\models\\qwen3-vl-2b-int4",
    "exists": true,
    "pass": true,
    "time": 0.0
  },
  {
    "test": "0e_resolve_model_path_llamacpp",
    "model_id": "smolvlm-2.2b-gguf-q4",
    "path": "D:\\projects\\claude\\urlparser\\models\\smolvlm-2.2b-gguf-q4",
    "exists": false,
    "pass": false,
    "time": 0.0
  },
  {
    "test": "0f_openvino_devices",
    "result": [
      "CPU",
      "GPU"
    ],
    "pass": true,
    "time": 0
  }
]
```