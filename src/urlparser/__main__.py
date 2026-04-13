"""
urlparser CLI 入口

使用方式:
    python -m urlparser parse https://www.zhihu.com/question/xxx
    python -m urlparser parse-batch urls.txt --transcribe
    python -m urlparser cache stats
    python -m urlparser status validate
"""

from .cli import main

if __name__ == '__main__':
    main()