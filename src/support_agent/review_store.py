"""Cola temporal de expedientes del piloto que requieren revisión humana.

Solo contiene los casos escalados. Vive en RAM como los tickets existentes y
se purga al vencer el plazo o al reiniciar el proceso.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass

TTL_SECONDS = 60 * 60
MAX_CASES = 3
MAX_TOTAL_BYTES = 24 * 1024 * 1024


@dataclass
class ReviewCase:
    created_at: float
    files: dict[str, tuple[bytes, str]]
    report: dict


_cases: dict[int, ReviewCase] = {}
_lock = threading.Lock()


def _purge() -> None:
    now = time.time()
    for case_id in list(_cases):
        if now - _cases[case_id].created_at > TTL_SECONDS:
            del _cases[case_id]


def save_case(case_id: int, files: dict[str, tuple[bytes, str]], report: dict) -> None:
    with _lock:
        _purge()
        incoming = sum(len(data) for data, _ in files.values())
        while _cases and (len(_cases) >= MAX_CASES or
                          incoming + sum(
                              len(data) for case in _cases.values()
                              for data, _ in case.files.values()
                          ) > MAX_TOTAL_BYTES):
            oldest = min(_cases, key=lambda key: _cases[key].created_at)
            del _cases[oldest]
        _cases[case_id] = ReviewCase(time.time(), files, report)


def get_case(case_id: int) -> ReviewCase | None:
    with _lock:
        _purge()
        return _cases.get(case_id)


def list_cases() -> list[dict]:
    with _lock:
        _purge()
        return [
            {"ticket_id": case_id, "created_at": case.created_at,
             "resultado": case.report["resultado"], "expira_en_segundos": max(
                 0, int(TTL_SECONDS - (time.time() - case.created_at))
             )}
            for case_id, case in sorted(_cases.items())
        ]


def delete_case(case_id: int) -> bool:
    with _lock:
        _purge()
        return _cases.pop(case_id, None) is not None
