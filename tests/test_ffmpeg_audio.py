import asyncio
import json
import subprocess
import os

from urlparser.fetcher.bb_browser_fetcher import BbBrowserFetcher


async def test():
    f = BbBrowserFetcher()
    audio_url = await f.get_bilibili_audio_url("BV1KBZkB6EJF", 36121152571)
    if not audio_url:
        print("No audio URL")
        return

    wav_path = r"D:\projects\claude\urlparser\tests\multi_platform\test_audio.wav"

    headers = (
        "Referer: https://www.bilibili.com\r\n"
        "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36"
    )

    cmd = [
        "ffmpeg", "-y",
        "-headers", headers,
        "-i", audio_url,
        "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1",
        wav_path,
    ]

    print("Running ffmpeg...")
    result = subprocess.run(cmd, capture_output=True, timeout=120)
    print(f"Return code: {result.returncode}")
    if result.returncode != 0:
        stderr_text = result.stderr.decode("utf-8", errors="replace")
        print(f"STDERR: {stderr_text[:500]}")
    if os.path.exists(wav_path):
        size_mb = os.path.getsize(wav_path) / 1024 / 1024
        print(f"WAV file: {size_mb:.1f} MB")
    else:
        print("WAV file not created")


asyncio.run(test())
