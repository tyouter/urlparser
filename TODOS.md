# TODOs - Video Comprehension Module

## High Priority

(none - all high priority items completed)

## Medium Priority

- [ ] **Install MSVC / Visual C++ Build Tools** (optional) - Required for `llama-cpp-python` compilation. Alternative: find pre-built Windows wheels. Provides CPU fallback when OpenVINO GPU is unavailable.
- [ ] **Download phi-4-multimodal-int4 model** (optional) - For NPU inference. Current NPU plugin crashes with "Accessing out-of-range dimension" — may need model update or OpenVINO version fix.
- [ ] **Performance benchmark** - Measure inference time per frame on CPU vs GPU for Qwen3-VL-2B INT4.
- [ ] **Fix GPU clBuildProgram failure** - Intel iGPU OpenVINO clBuildProgram fails. Root cause: OpenCL compiler issue. CPU fallback works fine.

## Low Priority

- [ ] **Add `--comp-device` CLI flag** - Allow manual device override (CPU/GPU/NPU).
- [ ] **Streaming output** - Add streamer callback to `generate()` for real-time frame descriptions.
- [ ] **Model auto-download** - Detect missing models in `resolve_model_path()` and offer to download from HuggingFace.
- [ ] **Clean up test files** - Remove `tests/test_comprehension_v*.json` files and `test_frame.jpg`, `test_red_frame.jpg` from root.

## Completed

- [x] Download Qwen3-VL-2B INT4 OpenVINO model (~1.7GB)
- [x] Fix `VLMPipeline` API: use `ov.Tensor` instead of PIL Image
- [x] Fix `VLMPipeline` API: use ChatHistory for proper text output (CPU)
- [x] Fix model path resolution (`src/models/` → project root `models/`)
- [x] Fix model selection: phi-4 → qwen3-vl-2b (phi-4 not deployed)
- [x] Fix NPU → GPU device (NPU crashes on this hardware)
- [x] Add `resolve_model_path()` to model registry
- [x] End-to-end pipeline test on Bilibili URL (5 frames, 954s total)
- [x] Unit tests: 30 comprehension tests + 88 existing (no regressions)
- [x] Install OpenVINO 2026.1 + openvino-genai + openvino-tokenizers
- [x] Implement all comprehension module files (models, frame_extractor, vlm_engine, pipeline, writer)
- [x] Wire comprehension into `core.py` `_do_parse()`
- [x] Add CLI flags (`--comprehension`, `--comp-engine`, `--comp-max-frames`)
- [x] Update `SKILL.md` and `CLAUDE.md` with comprehension docs
- [x] **Fix VLM GPU output garbled** - Added `_validate_gpu_or_fallback()` in `vlm_engine.py`, GPU test fails → auto fallback to CPU
- [x] **Add GPU device validation** - Test `VLMPipeline` on GPU during `load_model()` and fall back to CPU if output is invalid
- [x] **Audio+Video mode end-to-end test** - Tested `--comprehension audio_video` with FunASR transcription + VLM timeline merge
- [x] **Full test suite with Bilibili URL** - All 6 test categories passed (hardware detection, FunASR, Whisper, VLM video_only, VLM audio_video, parse full pipeline)
- [x] **Export `resolve_model_path` from comprehension __init__.py**
