"""Mask secrets / PII before any log text leaves the machine (e.g. goes to an LLM)."""

from __future__ import annotations

import re

_PATTERNS = [
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.S), "<private-key>"),
    (re.compile(r"(?i)\b(bearer|basic)\s+[A-Za-z0-9._~+/=\-]{8,}"), r"\1 <redacted>"),
    (re.compile(r"\b(?:sk|pk|ghp|gho|ghs|xox[abp])[-_][A-Za-z0-9\-_]{10,}"), "<token>"),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "<aws-key>"),
    (re.compile(r"\beyJ[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}"), "<jwt>"),
    (re.compile(r"(?i)((?:password|passwd|pwd|secret|token|api[_-]?key|authorization)\s*[=:]\s*)[^\s,;'\"]+"), r"\1<redacted>"),
    (re.compile(r"(?<=://)[^/\s:@]+:[^/\s@]+@"), "<creds>@"),
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"), "<email>"),
]


def redact(text: str, max_len: int = 4000) -> str:
    for pattern, repl in _PATTERNS:
        text = pattern.sub(repl, text)
    if len(text) > max_len:
        half = max_len // 2
        text = text[:half] + "\n...[truncated]...\n" + text[-half:]
    return text
