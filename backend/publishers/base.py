from dataclasses import dataclass
from typing import Optional


@dataclass
class PublishResult:
    ok: bool
    error: Optional[str] = None
    message_id: Optional[str] = None
    url: Optional[str] = None
