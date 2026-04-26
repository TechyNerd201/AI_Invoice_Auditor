from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()

def add_event(events: List[Dict[str, Any]], step: str, type_: str, message: str, data: Optional[Dict[str, Any]] = None):
    events.append({
        "ts": utc_now(),
        "step": step,
        "type": type_,
        "message": message,
        "data": data or {},
    })

def add_warning(warnings: List[Dict[str, Any]], code: str, message: str, data: Optional[Dict[str, Any]] = None):
    warnings.append({
        "ts": utc_now(),
        "code": code,
        "message": message,
        "data": data or {},
    })
    