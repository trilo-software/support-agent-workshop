#!/usr/bin/env python3
"""Mantiene despiertos los servicios free de los asistentes durante el workshop.

Un web service en plan free de Render se duerme tras 15 minutos sin tráfico y
tarda ~1 minuto en despertar. Este script hace GET /healthz a cada servicio
cada N segundos (default 600 = 10 min) para que nadie se tope con el arranque
en frío en medio de un ejercicio, sobre todo al volver del break.

Uso (lo corre el facilitador en su máquina, en una terminal aparte):

    uv run python scripts/keep_alive.py asistentes.txt
    uv run python scripts/keep_alive.py asistentes.txt --interval 300
    uv run python scripts/keep_alive.py asistentes.txt --once   # una sola ronda

asistentes.txt: una línea por asistente con su usuario de GitHub (se convierte
a la URL https://<usuario>-support-agent.onrender.com) o una URL completa
(p. ej. la de tu deploy de referencia). Líneas vacías y con # se ignoran.

Solo usa la biblioteca estándar: no depende del venv del proyecto.
"""

from __future__ import annotations

import argparse
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from setup_attendee import normalize_username  # noqa: E402

SERVICE_SUFFIX = "support-agent"
TIMEOUT_S = 90  # un despertar en frío puede tardar ~60 s


def url_for(line: str) -> str:
    """Convierte una línea del archivo en la URL de /healthz."""
    line = line.strip()
    if line.startswith(("http://", "https://")):
        return line.rstrip("/") + ("" if line.rstrip("/").endswith("/healthz") else "/healthz")
    slug = normalize_username(line)
    return f"https://{slug}-{SERVICE_SUFFIX}.onrender.com/healthz"


def load_targets(path: Path) -> list[str]:
    targets = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        if line:
            targets.append(url_for(line))
    return targets


def ping(url: str) -> tuple[str, str, float]:
    """Devuelve (url, estado legible, segundos)."""
    start = time.monotonic()
    try:
        with urllib.request.urlopen(url, timeout=TIMEOUT_S) as res:
            status = f"{res.status}"
    except urllib.error.HTTPError as exc:
        status = f"HTTP {exc.code}"
        if exc.code == 404:
            status += " (no existe ese servicio)"
    except Exception as exc:  # timeout, DNS, conexión rechazada…
        status = f"error: {type(exc).__name__}"
    elapsed = time.monotonic() - start
    if status == "200" and elapsed > 20:
        status = "200 (estaba dormido)"
    return url, status, elapsed


def run_round(targets: list[str]) -> None:
    stamp = time.strftime("%H:%M:%S")
    with ThreadPoolExecutor(max_workers=min(16, len(targets))) as pool:
        results = list(pool.map(ping, targets))
    width = max(len(u) for u in targets)
    print(f"\n[{stamp}] ronda de keep-alive · {len(targets)} servicios")
    for url, status, elapsed in results:
        mark = "✓" if status.startswith("200") else "✗"
        print(f"  {mark} {url:<{width}}  {status:<24} {elapsed:5.1f}s")
    ok = sum(1 for _, s, _ in results if s.startswith("200"))
    print(f"  {ok}/{len(targets)} respondieron 200")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("archivo", type=Path, help="lista de asistentes (usuario de GitHub o URL por línea)")
    parser.add_argument("--interval", type=int, default=600, help="segundos entre rondas (default 600)")
    parser.add_argument("--once", action="store_true", help="una sola ronda y salir")
    args = parser.parse_args()

    targets = load_targets(args.archivo)
    if not targets:
        raise SystemExit(f"{args.archivo}: no hay asistentes (una línea por usuario o URL)")

    while True:
        run_round(targets)
        if args.once:
            return
        try:
            time.sleep(args.interval)
        except KeyboardInterrupt:
            print("\nlisto, hasta aquí el keep-alive.")
            return


if __name__ == "__main__":
    main()
