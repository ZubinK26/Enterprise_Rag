from pathlib import Path

from app.ingestion.loader import LoadedDocument, load_markdown_docs


def test_load_markdown_docs_reads_md_and_sets_ids(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "Hello_World.md").write_text("# Title\n\nBody text here.\n", encoding="utf-8")

    loaded = load_markdown_docs(docs)
    assert loaded == [
        LoadedDocument(
            doc_id="hello_world",
            source_file="Hello_World.md",
            text="# Title\n\nBody text here.",
        )
    ]


def test_load_markdown_docs_returns_empty_for_missing_dir(tmp_path: Path) -> None:
    assert load_markdown_docs(tmp_path / "nope") == []
