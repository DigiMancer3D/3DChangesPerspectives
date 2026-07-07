from pathlib import Path


def test_phase6_version_and_handoff_files_exist():
    root = Path(__file__).resolve().parents[1]
    assert (root / "VERSION").read_text(encoding="utf-8").strip() == "0.6.0-rc1-r2"
    assert (root / "FINAL_HANDOFF_GUIDE.md").exists()
    assert (root / "docs" / "RELEASE_CANDIDATE_CHECKLIST.md").exists()


def test_phase6_release_helpers_exist_and_are_shell_scripts():
    root = Path(__file__).resolve().parents[1]
    for rel in ["tools/build_github_upload.sh", "tools/desktop_launcher_doctor.sh"]:
        text = (root / rel).read_text(encoding="utf-8")
        assert text.startswith("#!/usr/bin/env bash")
