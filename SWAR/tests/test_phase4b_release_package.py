from pathlib import Path


def test_release_docs_exist():
    root = Path(__file__).resolve().parents[1]
    for name in [
        "README.md",
        "INSTALL.md",
        "USER_GUIDE.md",
        "SCRIPT_MARKUP_SPEC.md",
        "RELEASE_NOTES.md",
        "requirements.txt",
        "current.emoji",
        "SWAR.udata",
    ]:
        assert (root / name).exists(), name


def test_gitignore_blocks_common_generated_files():
    root = Path(__file__).resolve().parents[1]
    text = (root / ".gitignore").read_text(encoding="utf-8")
    assert "venv/" in text
    assert "__pycache__/" in text
    assert "*_preview.html" in text
