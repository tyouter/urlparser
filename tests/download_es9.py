import os
os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'
import yt_dlp

out_dir = os.path.join(os.path.dirname(__file__), 'ES9新车发布会')
os.makedirs(out_dir, exist_ok=True)

ydl_opts = {
    'quiet': False,
    'no_warnings': False,
    'format': 'bestaudio/best',
    'outtmpl': os.path.join(out_dir, 'es9_audio.%(ext)s'),
    'cookiesfrombrowser': ('chrome',),
}

try:
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info('https://www.bilibili.com/video/BV1d5QvBnENK/', download=True)
        title = info.get('title', 'N/A')
        duration = info.get('duration', 0)
        fname = ydl.prepare_filename(info)
        print(f'Title: {title}')
        print(f'Duration: {duration}s')
        print(f'File: {fname}')
        if os.path.exists(fname):
            size_mb = os.path.getsize(fname) / 1024 / 1024
            print(f'Size: {size_mb:.1f} MB')
except Exception as e:
    print(f'Chrome cookies failed: {e}')
    print('\nTrying with Wbi sign compatibility...')
    ydl_opts2 = {
        'quiet': False,
        'no_warnings': False,
        'format': 'bestaudio/best',
        'outtmpl': os.path.join(out_dir, 'es9_audio.%(ext)s'),
        'extractor_args': {'bilibili': {'wbi_sign': True}},
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts2) as ydl:
            info = ydl.extract_info('https://www.bilibili.com/video/BV1d5QvBnENK/', download=True)
            fname = ydl.prepare_filename(info)
            print(f'File: {fname}')
            if os.path.exists(fname):
                size_mb = os.path.getsize(fname) / 1024 / 1024
                print(f'Size: {size_mb:.1f} MB')
    except Exception as e2:
        print(f'Wbi sign also failed: {e2}')
