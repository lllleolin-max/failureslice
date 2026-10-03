"""Real Git export regression; no library or mathematical reducer changes."""
import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest
import zipfile

TOOL = Path(__file__).resolve().parents[1] / "tools" / "archive_check.py"


class ArchivePortabilityTests(unittest.TestCase):
    def test_canonical_export_under_crlf_policy_preserves_all_blob_bytes(self):
        spec = importlib.util.spec_from_file_location("failureslice_archive_tool", TOOL)
        tool = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(tool)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = root / "repo"
            repo.mkdir()
            def git(*args):
                return subprocess.run(["git", *args], cwd=repo, check=True,
                                      stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout
            git("init", "--quiet", "--initial-branch=main")
            git("config", "--local", "core.autocrlf", "true")
            git("config", "--local", "core.eol", "crlf")
            fixtures = {"module.py": "first = 1\nsecond = '汉字'\n".encode("utf-8"),
                        "binary.bin": b"\x00\xff\r\n\x01\n",
                        "existing-crlf.txt": b"preserve\r\noriginal-blob\r\n",
                        ".gitattributes": b"existing-crlf.txt -text\n"}
            for name, raw in fixtures.items():
                (repo / name).write_bytes(raw)
            git("add", ".")
            git("-c", "user.name=lllleolin-max", "-c", "user.email=lllleolin-max@users.noreply.github.com",
                "commit", "--quiet", "-m", "Synthetic archive regression fixture")
            sha = git("rev-parse", "HEAD").decode().strip()
            archive = root / "canonical.zip"
            before = {key: git("config", "--local", "--get", key) for key in ("core.autocrlf", "core.eol")}
            self.assertEqual(before["core.autocrlf"].strip(), b"true")
            self.assertEqual(before["core.eol"].strip(), b"crlf")
            tool.archive_canonical(repo, sha, archive)
            with zipfile.ZipFile(archive) as zipped:
                for name, expected in fixtures.items():
                    blob = git("show", f"{sha}:{name}")
                    self.assertEqual(blob, expected)
                    self.assertEqual(zipped.read(name), blob)
            # The correction must not normalize existing CRLF/binary blobs or
            # persistently change repository/global configuration to pass.
            after = {key: git("config", "--local", "--get", key) for key in before}
            self.assertEqual(after, before)
