from pathlib import Path

import pytest

from utils.config import Settings
from utils.path_utils import safe_join
from utils.security import (
    SecurityError,
    sanitize_filename,
    validate_readonly_sql,
    validate_thread_id,
)


def test_settings_parse_comma_separated_cors(tmp_path: Path) -> None:
    settings = Settings(
        project_root=tmp_path,
        cors_origins="http://localhost:5173, https://example.test/",  # type: ignore[arg-type]
    )
    assert settings.cors_origins == ["http://localhost:5173", "https://example.test"]


def test_settings_parse_cors_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "CORS_ORIGINS",
        "http://localhost:5173, http://127.0.0.1:5173/",
    )
    settings = Settings(_env_file=None)
    assert settings.cors_origins == [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]


@pytest.mark.parametrize(
    "origins",
    [
        "https://user:password@example.test",
        "https://example.test/path",
        "*,https://example.test",
    ],
)
def test_settings_reject_dangerous_cors_origins(origins: str) -> None:
    with pytest.raises(ValueError):
        Settings(_env_file=None, cors_origins=origins)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("openai_base_url", "https://user:secret@example.test/v1"),
        ("openai_base_url", "https://example.test/v1?api_key=secret"),
        ("ragflow_api_url", "https://user:secret@example.test"),
        ("ragflow_api_url", "https://example.test/api#secret"),
    ],
)
def test_settings_reject_credentials_and_secrets_in_provider_urls(
    field: str, value: str
) -> None:
    with pytest.raises(ValueError):
        Settings(_env_file=None, **{field: value})


@pytest.mark.parametrize("value", ["abc", "abc-123_X", "0"])
def test_valid_thread_ids(value: str) -> None:
    assert validate_thread_id(value) == value


@pytest.mark.parametrize("value", ["", "../x", "a/b", "C:\\x", "space here", "x" * 65])
def test_invalid_thread_ids(value: str) -> None:
    with pytest.raises(SecurityError):
        validate_thread_id(value)


def test_filename_is_sanitized_and_extension_checked() -> None:
    assert sanitize_filename("研究 report (final).PDF") == "研究_report_final_.PDF"
    with pytest.raises(SecurityError):
        sanitize_filename("payload.exe")
    with pytest.raises(SecurityError):
        sanitize_filename("%2e%2e%2f.env")
    with pytest.raises(SecurityError):
        sanitize_filename("CON.txt")


@pytest.mark.parametrize(
    "value",
    [
        "../.env",
        "..\\.env",
        "%2e%2e%2f.env",
        "%252e%252e%255c.env",
        "C:\\Windows\\x",
        "/etc/passwd",
    ],
)
def test_safe_join_rejects_traversal(tmp_path: Path, value: str) -> None:
    with pytest.raises(SecurityError):
        safe_join(tmp_path, value)


def test_safe_join_rejects_symlink_escape(tmp_path: Path) -> None:
    outside = tmp_path.parent / "outside-test.txt"
    outside.write_text("secret", encoding="utf-8")
    link = tmp_path / "link.txt"
    try:
        link.symlink_to(outside)
    except OSError:
        pytest.skip("symlink creation is unavailable")
    with pytest.raises(SecurityError):
        safe_join(tmp_path, "link.txt", must_exist=True)
    outside.unlink()


@pytest.mark.parametrize(
    "query",
    [
        "SELECT * FROM products",
        "SHOW TABLES",
        "DESCRIBE products",
        "DESC products",
        "EXPLAIN SELECT * FROM products",
        "SELECT 1;",
    ],
)
def test_readonly_sql_allows_supported_statements(query: str) -> None:
    assert validate_readonly_sql(query)


@pytest.mark.parametrize(
    "query",
    [
        "DELETE FROM products",
        "DROP TABLE products",
        "UPDATE products SET name='x'",
        "INSERT INTO products VALUES (1)",
        "TRUNCATE TABLE products",
        "CREATE TABLE copied AS SELECT * FROM products",
        "ALTER TABLE products DROP COLUMN name",
        "EXPLAIN DELETE FROM products",
        "SELECT 1; SELECT 2",
        "SELECT LOAD_FILE('/etc/passwd')",
        "SELECT 1 INTO OUTFILE '/tmp/result'",
        "SELECT 1 INTO DUMPFILE '/tmp/result'",
        "SELECT SLEEP(10)",
        "SELECT BENCHMARK(1000, SHA2('x', 256))",
        "SELECT GET_LOCK('x', 10)",
        "SELECT 1 -- bypass",
        "SELECT 1 # bypass",
        "SELECT 1 /* bypass */",
    ],
)
def test_readonly_sql_rejects_unsafe_statements(query: str) -> None:
    with pytest.raises(SecurityError):
        validate_readonly_sql(query)
