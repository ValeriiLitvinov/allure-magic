"""Read Allure ``*-result.json`` files and group failures by fingerprint."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List

FAILED_STATUSES = ("failed", "broken")

_NOISE = [
    (re.compile(r"0x[0-9a-fA-F]+"), "<addr>"),
    (re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"), "<uuid>"),
    (re.compile(r"line \d+"), "line <n>"),
    (re.compile(r":\d+(?=[:\s]|$)"), ":<n>"),
    (re.compile(r"\d+"), "<n>"),
    (re.compile(r"[A-Za-z]:\\[^\s'\"]+|/[\w.\-/]+"), "<path>"),
]


@dataclass
class FailedResult:
    uuid: str
    name: str
    status: str
    message: str
    trace: str

    @property
    def exception_type(self) -> str:
        """Best-effort exception class from the message, e.g. ``ZeroDivisionError``."""
        m = re.match(r"\s*([A-Za-z_][\w.]*(?:Error|Exception|Timeout|Failure))\b", self.message)
        if m:
            return m.group(1).split(".")[-1]
        m = re.search(r"^E\s+([A-Za-z_][\w.]*(?:Error|Exception))\b", self.trace, re.M)
        return m.group(1).split(".")[-1] if m else ""


@dataclass
class FailureGroup:
    fingerprint: str
    members: List[FailedResult] = field(default_factory=list)

    @property
    def representative(self) -> FailedResult:
        return self.members[0]

    @property
    def size(self) -> int:
        return len(self.members)


def normalize(text: str) -> str:
    """Strip volatile bits (numbers, ids, paths) so equal failures hash equally."""
    for pattern, repl in _NOISE:
        text = pattern.sub(repl, text)
    return re.sub(r"\s+", " ", text).strip()


def fingerprint(result: FailedResult) -> str:
    first_msg_line = result.message.strip().splitlines()[0] if result.message.strip() else ""
    last_trace_line = result.trace.strip().splitlines()[-1] if result.trace.strip() else ""
    key = normalize(first_msg_line) + "|" + normalize(last_trace_line)
    return hashlib.sha1(key.encode("utf-8")).hexdigest()[:12]


def load_failures(results_dir: Path) -> List[FailedResult]:
    out: List[FailedResult] = []
    for path in sorted(Path(results_dir).glob("*-result.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue  # a half-written result must not break the report
        status = data.get("status")
        if status not in FAILED_STATUSES:
            continue
        details = data.get("statusDetails") or {}
        out.append(
            FailedResult(
                uuid=data.get("uuid") or path.stem,
                name=data.get("name") or data.get("fullName") or path.stem,
                status=status,
                message=details.get("message") or "",
                trace=details.get("trace") or "",
            )
        )
    return out


def group_failures(failures: List[FailedResult]) -> List[FailureGroup]:
    groups: Dict[str, FailureGroup] = {}
    for f in failures:
        groups.setdefault(fingerprint(f), FailureGroup(fingerprint(f))).members.append(f)
    return sorted(groups.values(), key=lambda g: (-g.size, g.fingerprint))
