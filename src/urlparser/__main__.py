"""
urlparser CLI 入口

使用方式:
    python -m urlparser parse https://www.zhihu.com/question/xxx
    python -m urlparser parse-batch urls.txt --transcribe
    python -m urlparser cache stats
    python -m urlparser status validate
"""

# Set cache directories BEFORE any imports to prevent re-downloading models
import os
from pathlib import Path

# ModelScope cache for FunASR models
_modelscope_cache = Path.home() / '.cache' / 'modelscope'
_modelscope_cache.mkdir(parents=True, exist_ok=True)
os.environ['MODELSCOPE_CACHE'] = str(_modelscope_cache)

# HuggingFace cache for Whisper models
_hf_cache = Path.home() / '.cache' / 'huggingface'
_hf_cache.mkdir(parents=True, exist_ok=True)
os.environ['HF_HOME'] = str(_hf_cache)
os.environ['HUGGINGFACE_HUB_CACHE'] = str(_hf_cache / 'hub')

# OpenMP workaround for Windows
os.environ['KMP_DUPLICATE_LIB_OK'] = 'TRUE'

from .cli import main

if __name__ == '__main__':
    main()