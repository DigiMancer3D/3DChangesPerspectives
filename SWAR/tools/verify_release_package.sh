#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

missing=0
for path in \
  swar.py swar README.md INSTALL.md USER_GUIDE.md SCRIPT_MARKUP_SPEC.md \
  RELEASE_NOTES.md DEVELOPMENT_NOTES.md FINAL_HANDOFF_GUIDE.md \
  requirements.txt SWAR.udata current.emoji VERSION pytest.ini \
  tools/build_github_upload.sh tools/desktop_launcher_doctor.sh \
  docs/GITHUB_UPLOAD_CHECKLIST.md docs/RELEASE_CANDIDATE_CHECKLIST.md; do
  if [ ! -e "$path" ]; then
    echo "MISSING: $path"
    missing=1
  fi
done

if [ "$missing" -ne 0 ]; then
  exit 1
fi

# Remove local caches before checking. Local venv folders are allowed after install_kubuntu.sh.
find . -type d \( -name '__pycache__' -o -name '.pytest_cache' \) -prune -exec rm -rf {} +
find . -name '*.pyc' -delete

PYTHON="python3"
if [ -x "venv/bin/python" ]; then
  PYTHON="venv/bin/python"
elif [ -x ".venv/bin/python" ]; then
  PYTHON=".venv/bin/python"
fi

# Test only the release root tests. GITHUB_UPLOAD has its own copy of tests and must not be collected together.
"$PYTHON" -m pytest -q tests

# If a bundled GITHUB_UPLOAD exists, smoke-check its structure without mixing duplicate test modules.
if [ -d "GITHUB_UPLOAD" ]; then
  for path in swar.py swar README.md INSTALL.md USER_GUIDE.md SCRIPT_MARKUP_SPEC.md \
    RELEASE_NOTES.md DEVELOPMENT_NOTES.md FINAL_HANDOFF_GUIDE.md \
    requirements.txt SWAR.udata current.emoji VERSION pytest.ini; do
    if [ ! -e "GITHUB_UPLOAD/$path" ]; then
      echo "GITHUB_UPLOAD MISSING: $path"
      exit 1
    fi
  done
fi

# Clean cache artifacts created by pytest.
find . -type d \( -name '__pycache__' -o -name '.pytest_cache' \) -prune -exec rm -rf {} +
find . -name '*.pyc' -delete

echo "Release package verification passed."
