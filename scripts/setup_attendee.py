#!/usr/bin/env python3
"""Namespacea el render.yaml con tu usuario de GitHub.

En un workshop, decenas de asistentes despliegan este Blueprint en la MISMA
organización de Render; sin prefijo, los nombres de proyecto/servicio/BD
colisionan. Este script prefija todos los `name` (y las referencias
`fromDatabase`) con el username normalizado.

Uso:
    python scripts/setup_attendee.py <github-username> [ruta/al/render.yaml]

La Action .github/workflows/setup-attendee.yml lo corre por ti con tu usuario
y commitea el resultado al fork.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml


def normalize_username(username: str) -> str:
    """Minúsculas y solo [a-z0-9-]: es lo que Render acepta en nombres."""
    slug = re.sub(r"[^a-z0-9-]+", "-", username.strip().lower())
    slug = re.sub(r"-{2,}", "-", slug).strip("-")
    if not slug:
        raise ValueError(f"username inválido: {username!r}")
    return slug


def _prefix(prefix: str, name: str) -> str:
    return name if name.startswith(f"{prefix}-") else f"{prefix}-{name}"


def _namespace_resources(prefix: str, databases: list, services: list) -> None:
    for db in databases or []:
        if db.get("name"):
            db["name"] = _prefix(prefix, db["name"])
    for svc in services or []:
        if svc.get("name"):
            svc["name"] = _prefix(prefix, svc["name"])
        for env_var in svc.get("envVars") or []:
            from_db = env_var.get("fromDatabase")
            if from_db and from_db.get("name"):
                from_db["name"] = _prefix(prefix, from_db["name"])


def namespace_blueprint(data: dict, username: str) -> dict:
    prefix = normalize_username(username)
    for project in data.get("projects") or []:
        if project.get("name"):
            project["name"] = _prefix(prefix, project["name"])
        for environment in project.get("environments") or []:
            _namespace_resources(
                prefix, environment.get("databases"), environment.get("services")
            )
    # Soporta también blueprints planos (sin bloque projects).
    _namespace_resources(prefix, data.get("databases"), data.get("services"))
    return data


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        raise SystemExit(1)
    username = sys.argv[1]
    path = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("render.yaml")

    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    namespace_blueprint(data, username)
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
    print(f"render.yaml namespaceado con el prefijo '{normalize_username(username)}-'")


if __name__ == "__main__":
    main()
