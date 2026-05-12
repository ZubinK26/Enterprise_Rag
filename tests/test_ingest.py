from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.config import Settings


def test_ingest_returns_400_when_no_documents(tmp_path: Path) -> None:
    import app.main as main

    empty_docs = tmp_path / "docs"
    empty_docs.mkdir()

    fake = Settings(
        docs_dir=empty_docs,
        vector_store_dir=tmp_path / "vs",
        logs_db_path=tmp_path / "logs.db",
        llm_api_key="",
    )

    with (
        patch.object(main, "get_settings", lambda: fake),
        TestClient(main.app) as client,
    ):
        response = client.post("/ingest")

    assert response.status_code == 400
    assert "No markdown" in response.json()["detail"]
