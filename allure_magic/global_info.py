"""Generate / read ``global-info.json`` consumed by the Global Info widget.

Decorations:
  text  - plain text (default, HTML-escaped by the widget)
  link  - ``value`` is an http(s)/mailto URL, ``display_value`` the label
  code  - monospace block (escaped)
  html  - raw HTML, rendered as-is: only use with trusted content
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, List, Optional

DECORATIONS = ("text", "link", "code", "html")
FILE_NAME = "global-info.json"


@dataclass
class GlobalInfoItem:
    name: str
    value: Optional[str] = None
    display_value: Optional[str] = None
    decoration: str = "text"

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("GlobalInfoItem.name must not be empty")
        if self.decoration not in DECORATIONS:
            raise ValueError(
                f"unknown decoration {self.decoration!r}, expected one of {DECORATIONS}"
            )
        if self.decoration == "link" and not self.value:
            raise ValueError("link items need a value (the URL)")

    def to_dict(self) -> dict:
        return {k: v for k, v in asdict(self).items() if v is not None}


def load_global_info(path: Path) -> List[GlobalInfoItem]:
    path = Path(path)
    if not path.exists():
        return []
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError(f"{path}: expected a JSON list")
    return [
        GlobalInfoItem(
            name=r["name"],
            value=r.get("value"),
            display_value=r.get("display_value"),
            decoration=r.get("decoration", "text"),
        )
        for r in raw
    ]


def write_global_info(items: Iterable[GlobalInfoItem], path: Path) -> Path:
    path = Path(path)
    if path.is_dir():
        path = path / FILE_NAME
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps([i.to_dict() for i in items], ensure_ascii=False, indent=4),
        encoding="utf-8",
    )
    return path
