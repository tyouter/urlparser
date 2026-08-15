"""
urlparserd 回环 TCP + JSON-lines 私有协议（v4 M1）

每行一个 JSON 对象。请求信封：{"id": "...", "op": "...", "payload": {...}}
响应行类型：result（含 id 回显）/ error / event（进度事件）/ ready（订阅就绪）
"""

import json
from typing import Any, Dict, Optional


def encode_line(obj: Dict[str, Any]) -> bytes:
    return (json.dumps(obj, ensure_ascii=False) + "\n").encode("utf-8")


def parse_line(line: str) -> Optional[Dict[str, Any]]:
    """解析一行 JSON；非法行返回 None（调用方决定忽略或报错）"""
    try:
        obj = json.loads(line)
        return obj if isinstance(obj, dict) else None
    except Exception:
        return None


def make_request(op: str, payload: Optional[Dict[str, Any]] = None, req_id: str = "") -> Dict[str, Any]:
    return {"id": req_id, "op": op, "payload": payload or {}}


def make_result(req_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    return {"type": "result", "id": req_id, "payload": payload}


def make_error(req_id: str, code: str, message: str) -> Dict[str, Any]:
    return {"type": "error", "id": req_id, "error": {"code": code, "message": message}}


def make_event(job_id: str, event: Dict[str, Any]) -> Dict[str, Any]:
    return {"type": "event", "job_id": job_id, "event": event}
