import os
import sys
import tempfile
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
# Test fixtures drop tables and create/delete media. Never point them at saved app data.
_test_data = tempfile.TemporaryDirectory(prefix="smartcricket-tests-")
TEST_ROOT = Path(_test_data.name)
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_ROOT / 'test.db'}"
os.environ["UPLOAD_DIR"] = str(TEST_ROOT / "uploads")
os.environ["OUTPUT_DIR"] = str(TEST_ROOT / "outputs")
os.environ["MODEL_DIR"] = str(TEST_ROOT / "models")
os.environ["LLM_API_KEY"] = ""
# Reuse installed pose assets without downloading or modifying the app's models.
(TEST_ROOT / "models").mkdir()
for asset in (ROOT / "models").glob("*.task"):
    shutil.copy2(asset, TEST_ROOT / "models" / asset.name)
