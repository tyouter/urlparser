import os
import sys
import time

os.environ['KMP_DUPLICATE_LIB_OK'] = 'TRUE'
os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'

TEST_URL = "https://www.bilibili.com/video/BV1d5QvBnENK/"
OUTPUT_DIR = r"D:\projects\claude\urlparser\tests\ES9新车发布会"

def test_funasr_cuda():
    print("=" * 60)
    print("FunASR CUDA 加速转录测试")
    print("=" * 60)

    import torch
    print(f"CUDA available: {torch.cuda.is_available()}")
    if torch.cuda.is_available():
        print(f"GPU: {torch.cuda.get_device_name(0)}")
        print(f"VRAM: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.1f} GB")

    from urlparser.transcriber.funasr import FunASRTranscriber

    transcriber = FunASRTranscriber(device="cuda")
    print(f"Device: {transcriber.device}")

    t0 = time.time()
    result = transcriber.transcribe_from_url(TEST_URL, language="zh")
    elapsed = round(time.time() - t0, 2)

    print(f"\nElapsed: {elapsed}s")
    print(f"Success: {result.success}")
    if result.error:
        print(f"Error: {result.error}")
    if result.text:
        print(f"Text length: {len(result.text)} chars")
        print(f"First 200 chars: {result.text[:200]}")

    if torch.cuda.is_available():
        print(f"\nGPU Memory used: {torch.cuda.max_memory_allocated() / 1024**3:.2f} GB")

    output_path = os.path.join(OUTPUT_DIR, "06_funasr_cuda.md")
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(f"# FunASR CUDA 加速转录测试\n\n")
        f.write(f"> 测试时间: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"> 测试URL: {TEST_URL}\n")
        f.write(f"> 设备: CUDA (RTX 4060 Ti)\n")
        f.write(f"> 耗时: {elapsed}s\n\n")
        f.write(f"## 测试结果\n\n")
        f.write(f"- CUDA 可用: {torch.cuda.is_available()}\n")
        if torch.cuda.is_available():
            f.write(f"- GPU: {torch.cuda.get_device_name(0)}\n")
            f.write(f"- GPU 显存使用: {torch.cuda.max_memory_allocated() / 1024**3:.2f} GB\n")
        f.write(f"- 转录成功: {result.success}\n")
        if result.error:
            f.write(f"- 错误: {result.error}\n")
        if result.text:
            f.write(f"- 文本长度: {len(result.text)} 字符\n\n")
            f.write(f"## 转录文本\n\n{result.text}\n")

    print(f"\nOutput saved to: {output_path}")

if __name__ == "__main__":
    test_funasr_cuda()
