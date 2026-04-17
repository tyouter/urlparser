# Video Comprehension Module - Status Report

**Date**: 2026-04-17
**Last updated**: After VLM model download & pipeline testing

## Overall Status: Mostly Complete, 1 Open Issue

The comprehension module is ~90% implemented. All code is in place, model is downloaded, pipeline runs end-to-end. One remaining VLM output formatting issue needs fixing.

## What's Done

| Item | Status | Notes |
|------|--------|-------|
| `comprehension/models.py` - enums, config, hardware detection, model selection | Done | `resolve_model_path()` added |
| `comprehension/frame_extractor.py` - ffmpeg scdet, keyframe extraction | Done | Works with imageio-ffmpeg bundled ffmpeg |
| `comprehension/vlm_engine.py` - OpenVINOEngine + LlamaCppEngine | Partial | ChatHistory API updated, but GPU output garbled |
| `comprehension/pipeline.py` - full orchestration | Done | Download → scdet → extract → VLM → merge works |
| `comprehension/writer.py` - timeline Markdown output | Done | |
| `config.py` - ComprehensionConfig, ParseConfig integration | Done | |
| `models.py` - ComprehensionResult, VisualFrameResult, to_dict, to_markdown | Done | |
| `core.py` - _run_comprehension() wired into _do_parse() | Done | |
| `cli.py` - --comprehension, --comp-engine, --comp-max-frames flags | Done | |
| `pyproject.toml` - [comprehension] optional deps, version 3.3.0 | Done | |
| `dependency_installer.py` - ensure_comprehension_dependencies() | Done | |
| `__init__.py` - exports | Done | |
| `skill/SKILL.md` - comprehension docs | Done | |
| `tests/test_comprehension.py` - 30 unit tests | Done | |
| Qwen3-VL-2B INT4 OpenVINO model downloaded | Done | `models/qwen3-vl-2b-int4/` (~1.7GB) |
| OpenVINO 2026.1 + openvino-genai installed | Done | |
| End-to-end pipeline runs (download, scdet, frames, VLM) | Done | 5 frames analyzed on Bilibili test URL |
| Unit tests (88 existing + 30 comprehension) | Done | No regressions |

## Known Issues

### 1. VLM GPU Output Garbled (HIGH PRIORITY)
- **Symptom**: When running via CLI with `--comprehension video`, VLM returns garbled binary-looking output (e.g. `. 2000000000...`) instead of Chinese text descriptions
- **Isolated test works**: Direct `VLMPipeline` with CPU device + ChatHistory returns correct Chinese text ("这是一张纯蓝色的图片...")
- **Suspected cause**: GPU device (`device='GPU'`) may have different output format, or there's an issue with how `result.texts[0]` is decoded on iGPU
- **Next step**: Test `device='GPU'` directly to confirm, then fix decoding or fall back to CPU

### 2. Model Selection Defaults to NPU Device (RESOLVED)
- Hardware detection returns `INTEL_NPU`, which previously selected non-existent `phi-4-multimodal-int4` model
- **Fix**: Updated `_select_openvino_model()` to always return `qwen3-vl-2b-int4` with `device='GPU'`
- **Note**: NPU device fails with `Accessing out-of-range dimension` error on this hardware

### 3. Model Path Resolution
- **Was**: Resolved to `src/models/` (wrong)
- **Fix**: Updated `resolve_model_path()` to check `parent/package_root/models/` first

### 4. llama-cpp-python Not Installed
- **Status**: Known limitation - Windows lacks MSVC compiler for build
- **Impact**: CPU fallback (`--comp-engine llamacpp`) not available
- **Workaround**: Can install pre-built wheels if needed, but OpenVINO is recommended for Intel hardware

### 5. VLMPipeline API Differences from Expected
- `generate()` with `image=` PIL object not supported - requires `ov.Tensor`
- `generate()` without ChatHistory returns garbled output on some configs
- **Fix**: Added `_load_image_tensor()` helper + ChatHistory usage

## Architecture Summary

```
yt-dlp (Python API)  →  Video .mp4
                         ├──▶ FrameExtractor.detect_scenes() → scene times
                         └──▶ FrameExtractor.extract_keyframes() → JPEG files
                                                        │
                                                        ▼
                                              OpenVINOEngine (Qwen3-VL-2B INT4)
                                              VLMPipeline.generate(ChatHistory, images=...)
                                                        │
                                                        ▼
                                              ComprehensionResult (visual frames + timeline)
```

## Model Files Location

- `C:\projects\urlparser-lib\models\qwen3-vl-2b-int4\` (~1.7GB, 24 files)
- Source: `shawnxhong/Qwen3-VL-2B-Instruct-ov-int4` from HuggingFace

## Pending Tasks

See `TODOS.md` in root folder.
