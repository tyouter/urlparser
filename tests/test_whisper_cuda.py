import os
import sys
import time
import tempfile

os.environ['KMP_DUPLICATE_LIB_OK'] = 'TRUE'
os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'

OUTPUT_DIR = r"D:\projects\claude\urlparser\tests\ES9新车发布会"

def test_whisper_cuda_with_url():
    print("=" * 60)
    print("Whisper CUDA 加速转录测试")
    print("=" * 60)

    import torch
    print(f"CUDA available: {torch.cuda.is_available()}")
    if torch.cuda.is_available():
        print(f"GPU: {torch.cuda.get_device_name(0)}")

    from urlparser.transcriber.whisper import WhisperTranscriber

    transcriber = WhisperTranscriber(device="cuda")
    print(f"Device: {transcriber.device}")

    test_urls = [
        "https://www.bilibili.com/video/BV1d5QvBnENK/",
    ]

    for url in test_urls:
        print(f"\n--- Testing URL: {url} ---")
        t0 = time.time()
        result = transcriber.transcribe_from_url(url, language="zh")
        elapsed = round(time.time() - t0, 2)

        print(f"Elapsed: {elapsed}s")
        print(f"Success: {result.success}")
        if result.error:
            print(f"Error: {result.error[:200]}")
        if result.text:
            print(f"Text length: {len(result.text)} chars")

        if result.success:
            output_path = os.path.join(OUTPUT_DIR, "07_whisper_cuda.md")
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(f"# Whisper CUDA 加速转录测试\n\n")
                f.write(f"> 测试时间: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"> 测试URL: {url}\n")
                f.write(f"> 设备: CUDA (RTX 4060 Ti)\n")
                f.write(f"> 耗时: {elapsed}s\n\n")
                f.write(f"## 测试结果\n\n")
                f.write(f"- CUDA 可用: {torch.cuda.is_available()}\n")
                if torch.cuda.is_available():
                    f.write(f"- GPU: {torch.cuda.get_device_name(0)}\n")
                    f.write(f"- GPU 显存使用: {torch.cuda.max_memory_allocated() / 1024**3:.2f} GB\n")
                f.write(f"- 转录成功: {result.success}\n")
                if result.text:
                    f.write(f"- 文本长度: {len(result.text)} 字符\n")
                if result.duration:
                    f.write(f"- 音频时长: {result.duration:.1f}s\n\n")
                    f.write(f"## 转录文本\n\n{result.text}\n")
            print(f"Output saved to: {output_path}")
            break

    if not result.success:
        print("\nB站下载失败，尝试用本地文件测试...")
        local_files = []
        for root, dirs, files in os.walk(r"D:\PCN\UT"):
            for f in files:
                if f.lower().endswith(('.m4a', '.mp3', '.wav', '.mp4', '.mkv')):
                    local_files.append(os.path.join(root, f))
                    if len(local_files) >= 1:
                        break
            if local_files:
                break

        if local_files:
            test_file = local_files[0]
            print(f"Testing with local file: {test_file}")
            torch.cuda.reset_peak_memory_stats()
            t0 = time.time()
            result = transcriber.transcribe(test_file, language="zh")
            elapsed = round(time.time() - t0, 2)

            print(f"Elapsed: {elapsed}s")
            print(f"Success: {result.success}")
            if result.error:
                print(f"Error: {result.error[:200]}")
            if result.text:
                print(f"Text length: {len(result.text)} chars")

            output_path = os.path.join(OUTPUT_DIR, "07_whisper_cuda.md")
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(f"# Whisper CUDA 加速转录测试\n\n")
                f.write(f"> 测试时间: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"> 本地文件: {test_file}\n")
                f.write(f"> 设备: CUDA (RTX 4060 Ti)\n")
                f.write(f"> 耗时: {elapsed}s\n\n")
                f.write(f"## 测试结果\n\n")
                f.write(f"- CUDA 可用: {torch.cuda.is_available()}\n")
                if torch.cuda.is_available():
                    f.write(f"- GPU: {torch.cuda.get_device_name(0)}\n")
                    f.write(f"- GPU 显存使用: {torch.cuda.max_memory_allocated() / 1024**3:.2f} GB\n")
                f.write(f"- 转录成功: {result.success}\n")
                if result.text:
                    f.write(f"- 文本长度: {len(result.text)} 字符\n\n")
                    f.write(f"## 转录文本\n\n{result.text}\n")
            print(f"Output saved to: {output_path}")
        else:
            print("No local test files found either.")

if __name__ == "__main__":
    test_whisper_cuda_with_url()
