from app.ingestion.chunker import chunk_document


def test_chunk_document_respects_max_length_for_body_chunks() -> None:
    paragraph = "abcdefghij " * 60
    text = "\n\n".join(paragraph for _ in range(30))
    chunks = chunk_document(text)
    assert len(chunks) >= 3
    for c in chunks[:-1]:
        assert 500 <= len(c) <= 800


def test_short_text_yields_single_chunk() -> None:
    text = "hello " * 40
    chunks = chunk_document(text)
    assert len(chunks) == 1


def test_overlap_links_adjacent_chunks_when_multiple() -> None:
    word = "telemetry"
    big = ("word " * 200 + word + " suffix ") * 80
    chunks = chunk_document(big)
    if len(chunks) < 2:
        raise AssertionError("expected multiple chunks for overlap assertion")
    overlap_found = any(
        chunks[i][-min(120, len(chunks[i])) :] in chunks[i + 1] for i in range(len(chunks) - 1)
    )
    assert overlap_found


def test_chunk_document_empty_input() -> None:
    assert chunk_document("") == []
