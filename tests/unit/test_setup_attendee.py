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
    # Se compara contra los nombres que YA tiene el archivo (no contra
    # literales): en la rama de un asistente el render.yaml ya viene
    # prefijado por la Action, y la suite debe seguir verde.
    data = yaml.safe_load(RENDER_YAML.read_text(encoding="utf-8"))
    nombre_proyecto = data["projects"][0]["name"]
    nombre_servicio = data["projects"][0]["environments"][0]["services"][0]["name"]
    result = setup_attendee.namespace_blueprint(copy.deepcopy(data), "Ana-Perez")

    project = result["projects"][0]
    assert project["name"] == f"ana-perez-{nombre_proyecto}"

    env = project["environments"][0]
    # El workshop corre sin base de datos (free tier: RAG en memoria).
    assert not env.get("databases")

    service = env["services"][0]
    assert service["name"] == f"ana-perez-{nombre_servicio}"
    assert service["plan"] == "free"


def test_namespacea_tambien_bases_y_fromDatabase():
    """La variante con Postgres del README también debe namespacearse."""
    data = {
        "projects": [{
            "name": "rag-agent-workshop",
            "environments": [{
                "name": "production",
                "databases": [{"name": "support-agent-db", "plan": "free"}],
                "services": [{
                    "type": "web",
                    "name": "support-agent",
                    "envVars": [
                        {"key": "DATABASE_URL",
                         "fromDatabase": {"name": "support-agent-db",
                                          "property": "connectionString"}},
                    ],
                }],
            }],
        }]
    }
    result = setup_attendee.namespace_blueprint(data, "Ana-Perez")
    env = result["projects"][0]["environments"][0]
    assert env["databases"][0]["name"] == "ana-perez-support-agent-db"
    from_db = env["services"][0]["envVars"][0]["fromDatabase"]
    assert from_db["name"] == "ana-perez-support-agent-db"


def test_es_idempotente():
    data = yaml.safe_load(RENDER_YAML.read_text(encoding="utf-8"))
    once = setup_attendee.namespace_blueprint(copy.deepcopy(data), "ana")
    twice = setup_attendee.namespace_blueprint(copy.deepcopy(once), "ana")
    assert once == twice
