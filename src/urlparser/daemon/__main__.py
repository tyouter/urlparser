"""
python -m urlparser.daemon —— 启动 urlparserd（v4 M1 任务 E）

用法:
    python -m urlparser.daemon [--port 47611] [--host 127.0.0.1] [--db PATH] [--foreground]
"""

import argparse
import asyncio
import logging
import sys

from .client import DEFAULT_PORT
from .server import DaemonServer


async def _run(server: DaemonServer) -> None:
    await server.start()
    print(f"urlparserd ready on {server.host}:{server.port}", flush=True)
    await server.serve_forever()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="urlparser.daemon")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--db", default=None, help="作业库路径（默认 ~/.urlparser/daemon/jobs.db）")
    parser.add_argument("--foreground", action="store_true", help="前台运行（默认即前台，由调用方决定窗口）")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    server = DaemonServer(host=args.host, port=args.port, db_path=args.db)
    try:
        asyncio.run(_run(server))
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
