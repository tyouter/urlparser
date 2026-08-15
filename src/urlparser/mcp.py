"""
python -m urlparser.mcp —— MCP stdio 服务器入口（v4 M2）

实现位于 mcp_server.py；本文件仅为 `python -m` 模块路径。
"""

from .mcp_server import main

if __name__ == "__main__":
    import sys
    sys.exit(main())
