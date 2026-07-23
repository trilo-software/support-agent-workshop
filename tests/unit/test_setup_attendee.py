import copy
import importlib.util
import sys
from pathlib import Path

import yaml

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "setup_attendee.py"
spec = importlib.util.spec_from_file_location("setup_attendee", SCRIPT)
setup_attendee = importlib.util.module_from_spec(spec)
sys.modules["setup_attendee"] = setup_attendee
spec.loader.exec_module(setup_attendee)

RENDER_YAML = Path(__file__).resolve().parents[2] / "render.yaml"


def test_normalize_username():
    assert setup_attendee.normalize_username("Ana_Perez.99") == "ana-perez-99"
    assert setup_attendee.normalize_username("robertogonzalez") == "robertogonzalez"


def test_namespacea_el_render_yaml_real():
    data = yaml.safe_load(RENDER_YAML.read_text(encoding="utf-8"))
    result = setup_attendee.namespace_blueprint(copy.deepcopy(data), "Ana-Perez")

    project = result["projects"][0]
    assert project["name"] == "ana-perez-rag-agent-workshop"

    env = project["environments"][0]
    assert env["databases"][0]["name"] == "ana-perez-support-agent-db"

    service = env["services"][0]
    assert service["name"] == "ana-perez-support-agent"

    from_db = next(
        e["fromDatabase"] for e in service["envVars"] if e.get("fromDatabase")
    )
    assert from_db["name"] == "ana-perez-support-agent-db"


def test_es_idempotente():
    data = yaml.safe_load(RENDER_YAML.read_text(encoding="utf-8"))
    once = setup_attendee.namespace_blueprint(copy.deepcopy(data), "ana")
    twice = setup_attendee.namespace_blueprint(copy.deepcopy(once), "ana")
    assert once == twice
