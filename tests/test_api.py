import tempfile
import unittest
import uuid
from pathlib import Path

from fastapi.testclient import TestClient

import backend.app as api_module


def authenticated_client() -> TestClient:
    client = TestClient(api_module.app)
    suffix = uuid.uuid4().hex[:10]
    response = client.post(
        "/api/auth/register",
        json={
            "username": f"test_{suffix}",
            "name": "Test User",
            "email": f"{suffix}@example.test",
            "password": "test-password-123",
            "confirm_password": "test-password-123",
        },
    )
    if response.status_code == 503:
        raise unittest.SkipTest("Configure DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME for API tests")
    if response.status_code != 201:
        raise AssertionError(response.text)
    return client


class ApiWorkflowTests(unittest.TestCase):
    def test_protected_routes_require_authentication(self) -> None:
        client = TestClient(api_module.app)
        self.assertEqual(client.get("/api/auth/me").status_code, 401)
        self.assertEqual(client.get("/api/repositories").status_code, 401)

    def test_users_are_isolated(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            original_workspace = api_module.WORKSPACE_ROOT
            api_module.WORKSPACE_ROOT = Path(directory) / "workspace"
            try:
                alice = authenticated_client()
                bob = authenticated_client()
                self.assertEqual(alice.post("/api/repositories", json={"name": "private-a"}).status_code, 201)
                self.assertEqual([item["name"] for item in bob.get("/api/repositories").json()], [])
                self.assertEqual(bob.get("/api/repositories/private-a").status_code, 404)
                self.assertEqual(bob.delete("/api/repositories/private-a").status_code, 404)
            finally:
                api_module.WORKSPACE_ROOT = original_workspace

    def test_import_project_preserves_nested_files_and_stages_them(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            original_workspace = api_module.WORKSPACE_ROOT
            api_module.WORKSPACE_ROOT = Path(directory) / "workspace"
            client = authenticated_client()
            files = [
                ("files", ("my-project/src/main.py", b"print('main')\n", "text/plain")),
                ("files", ("my-project/src/utils.py", b"def helper():\n    return 1\n", "text/plain")),
                ("files", ("my-project/assets/test.txt", b"asset\n", "text/plain")),
                ("files", ("my-project/README.md", b"# Imported\n", "text/markdown")),
            ]
            try:
                response = client.post(
                    "/api/repositories/import",
                    data={"name": "test-project", "description": "Imported project"},
                    files=files,
                )
                self.assertEqual(response.status_code, 201)
                root = api_module.WORKSPACE_ROOT / "test-project"
                self.assertEqual((root / "src" / "main.py").read_text(encoding="utf-8"), "print('main')\n")
                self.assertEqual((root / "src" / "utils.py").read_text(encoding="utf-8"), "def helper():\n    return 1\n")
                self.assertEqual((root / "assets" / "test.txt").read_text(encoding="utf-8"), "asset\n")
                payload = response.json()
                self.assertEqual(sorted(payload["files"]), ["README.md", "assets/test.txt", "src/main.py", "src/utils.py"])
                self.assertEqual(sorted(payload["status"]["staged"]), sorted(payload["files"]))
                first = client.post("/api/repositories/test-project/commit", json={"message": "initial import"})
                self.assertEqual(first.status_code, 200)
                (root / "src" / "main.py").write_text("print('changed')\n", encoding="utf-8")
                changed = client.get("/api/repositories/test-project/status").json()
                self.assertEqual(changed["modified"], ["src/main.py"])
                self.assertIn("-print('main')", client.get("/api/repositories/test-project/diff").json()["diff"])
                client.post("/api/repositories/test-project/add", json={"paths": ["src/main.py"]})
                second = client.post("/api/repositories/test-project/commit", json={"message": "update main"})
                self.assertEqual(second.status_code, 200)
                self.assertEqual(len(client.get("/api/repositories/test-project/commits").json()), 2)
                remote = Path(directory) / "remote"
                client.post("/api/repositories/test-project/remote", json={"name": "origin", "location": str(remote)})
                self.assertEqual(client.post("/api/repositories/test-project/push").status_code, 200)
                self.assertEqual(client.post("/api/repositories/test-project/pull").status_code, 200)
                self.assertEqual((root / "src" / "main.py").read_text(encoding="utf-8"), "print('changed')\n")
            finally:
                api_module.WORKSPACE_ROOT = original_workspace

    def test_repository_lifecycle_and_remote(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            original_workspace = api_module.WORKSPACE_ROOT
            api_module.WORKSPACE_ROOT = Path(directory) / "workspace"
            client = authenticated_client()
            try:
                created = client.post("/api/repositories", json={"name": "demo", "description": "Demo repository"})
                self.assertEqual(created.status_code, 201)
                self.assertEqual(created.json()["name"], "demo")
                self.assertEqual([item["name"] for item in client.get("/api/repositories").json()], ["demo"])

                root = api_module.WORKSPACE_ROOT / "demo"
                (root / "src").mkdir()
                (root / "src" / "app.py").write_text("print('one')\n", encoding="utf-8")
                browser = client.get("/api/repositories/demo/files", params={"path": "src"})
                self.assertEqual(browser.status_code, 200)
                self.assertEqual(browser.json()["entries"][0]["path"], "src/app.py")
                self.assertIn("print('one')", client.get("/api/repositories/demo/files", params={"path": "src/app.py"}).json()["content"])
                self.assertEqual(client.get("/api/repositories/demo/files", params={"path": "../"}).status_code, 400)

                staged = client.post("/api/repositories/demo/add", json={"paths": ["src/app.py"]})
                self.assertEqual(staged.status_code, 200)
                self.assertIn("src/app.py", staged.json()["repository"]["status"]["staged"])
                committed = client.post("/api/repositories/demo/commit", json={"message": "feat: add app"})
                self.assertEqual(committed.status_code, 200)
                commit_id = committed.json()["commit"]["id"]
                self.assertEqual(len(client.get("/api/repositories/demo/commits").json()), 1)
                self.assertIn(commit_id, client.get(f"/api/repositories/demo/commits/{commit_id[:7]}").json()["id"])

                (root / "src" / "app.py").write_text("print('two')\n", encoding="utf-8")
                self.assertIn("-print('one')", client.get("/api/repositories/demo/diff").json()["diff"])
                remote = Path(directory) / "remote"
                self.assertEqual(client.post("/api/repositories/demo/remote", json={"name": "origin", "location": str(remote)}).status_code, 200)
                self.assertEqual(client.post("/api/repositories/demo/add", json={"paths": ["."]}).status_code, 200)
                self.assertEqual(client.post("/api/repositories/demo/commit", json={"message": "fix: update app"}).status_code, 200)
                self.assertEqual(client.post("/api/repositories/demo/push").status_code, 200)
                self.assertEqual(client.delete("/api/repositories/demo").status_code, 204)
                self.assertEqual(client.get("/api/repositories/demo").status_code, 404)
            finally:
                api_module.WORKSPACE_ROOT = original_workspace

    def test_diff_handles_binary_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            original_workspace = api_module.WORKSPACE_ROOT
            api_module.WORKSPACE_ROOT = Path(directory) / "workspace"
            client = authenticated_client()
            try:
                self.assertEqual(client.post("/api/repositories", json={"name": "binary-demo"}).status_code, 201)
                root = api_module.WORKSPACE_ROOT / "binary-demo"
                (root / "image.bin").write_bytes(bytes([0, 159, 146, 150]))
                response = client.get("/api/repositories/binary-demo/diff")
                self.assertEqual(response.status_code, 200)
            finally:
                api_module.WORKSPACE_ROOT = original_workspace


if __name__ == "__main__":
    unittest.main()
