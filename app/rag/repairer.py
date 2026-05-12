from __future__ import annotations


def build_repair_user_prompt(*, errors: list[str], context: str, bad_output: str) -> str:
    joined = "\n".join(f"- {e}" for e in errors) if errors else "(none)"
    return (
        "Your previous answer failed validation.\n\n"
        f"Validation errors:\n{joined}\n\n"
        f"Retrieved context:\n{context}\n\n"
        f"Previous answer:\n{bad_output}\n\n"
        "Return corrected JSON only.\n"
        "Do not invent sources.\n"
        "Use only exact quotes from retrieved chunks."
    )
