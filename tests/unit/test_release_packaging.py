import tomllib
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


def test_compose_has_demo_safe_services_healthchecks_and_real_mysql_profile() -> None:
    compose = yaml.safe_load((ROOT / "docker-compose.yml").read_text(encoding="utf-8"))
    services = compose["services"]
    assert set(services) == {"backend", "frontend", "mysql"}
    assert services["mysql"]["profiles"] == ["real"]
    assert services["backend"]["depends_on"]["mysql"]["required"] is False
    assert services["frontend"]["depends_on"]["backend"]["condition"] == "service_healthy"
    assert "HEALTHCHECK" in (ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert "HEALTHCHECK" in (ROOT / "ui" / "Dockerfile").read_text(encoding="utf-8")
    nginx = (ROOT / "ui" / "nginx.conf").read_text(encoding="utf-8")
    assert "location = /health" in nginx
    assert "proxy_pass http://backend:8000/health" in nginx
    frontend_dockerignore = (ROOT / "ui" / ".dockerignore").read_text(encoding="utf-8")
    assert "node_modules" in frontend_dockerignore
    assert "dist" in frontend_dockerignore
    assert ".env" in frontend_dockerignore


def test_env_example_contains_only_empty_secret_placeholders() -> None:
    values: dict[str, str] = {}
    for line in (ROOT / ".env.example").read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key] = value
    for key in (
        "OPENAI_API_KEY",
        "TAVILY_API_KEY",
        "MYSQL_PASSWORD",
        "MYSQL_ROOT_PASSWORD",
        "RAGFLOW_API_KEY",
    ):
        assert values[key] == ""


def test_runtime_dependency_manifests_are_synchronized() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    requirements = {
        line.strip()
        for line in (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    }
    assert set(pyproject["project"]["dependencies"]) == requirements
