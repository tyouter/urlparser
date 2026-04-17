# TODOs - Video Comprehension Module

## High Priority

- [ ] **Fix VLM GPU output garbled** - `VLMPipeline` with `device='GPU'` returns binary-looking text instead of Chinese descriptions. CPU works fine. Need to test GPU directly and fix decoding, or use `device='CPU'` as default for now.

## Medium Priority

- [ ] **Install MSVC / Visual C++ Build Tools** (optional) - Required for `llama-cpp-python` compilation. Alternative: find pre-built Windows wheels. Provides CPU fallback when OpenVINO GPU is unavailable.
- [ ] **Download phi-4-multimodal-int4 model** (optional) - For NPU inference. Current NPU plugin crashes with "Accessing out-of-range dimension" — may need model update or OpenVINO version fix.
- [ ] **Add GPU device validation** - Test `VLMPipeline` on GPU during `load_model()` and fall back to CPU if output is invalid.
- [ ] **Performance benchmark** - Measure inference time per frame on CPU vs GPU for Qwen3-VL-2B INT4.

## Low Priority

- [ ] **Add `--comp-device` CLI flag** - Allow manual device override (CPU/GPU/NPU).
- [ ] **Streaming output** - Add streamer callback to `generate()` for real-time frame descriptions.
- [ ] **Model auto-download** - Detect missing models in `resolve_model_path()` and offer to download from HuggingFace.
- [ ] **Audio+Video mode end-to-end test** - Test `--comprehension audio_video` with FunASR transcription + VLM timeline merge.
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
