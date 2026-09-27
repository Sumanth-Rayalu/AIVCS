import copy
import importlib.util
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException


BACKEND_APP_PATH = Path(__file__).resolve().parents[1] / "backend" / "app.py"
BACKEND_SPEC = importlib.util.spec_from_file_location("aivcs_backend_app", BACKEND_APP_PATH)
backend = importlib.util.module_from_spec(BACKEND_SPEC)
BACKEND_SPEC.loader.exec_module(backend)


class FakeAccountCollection:
    def __init__(self, document):
        self.document = copy.deepcopy(document)

    def find_one(self, query):
        if all(self.document.get(key) == value for key, value in query.items()):
            return copy.deepcopy(self.document)
        return None

    def update_one(self, query, update):
        if self.document.get("_id") != query.get("_id"):
            return
        self.document.update(copy.deepcopy(update["$set"]))
        for key in update.get("$unset", {}):
            self.document.pop(key, None)

    def insert_one(self, document):
        self.document = copy.deepcopy(document)


class UserDataRemoteTests(unittest.TestCase):
    def setUp(self):
        self.collection = FakeAccountCollection({
            "_id": "account-1",
            "username": "bob",
            "email": "bob@example.com",
            "createdAt": "2026-09-24T13:00:00+00:00",
            "userData": {
                "username": "bob",
                "email": "bob@example.com",
                "repositories": [
                    {
                        "repositoryId": "demo",
                        "repositoryName": "AIVCS-project",
                        "description": "Keep this metadata",
                        "branches": [{
                            "branchName": "main",
                            "headCommitId": "main-1",
                            "commits": [{"commitId": "main-1"}],
                        }],
                    },
                    {
                        "repositoryId": "another-repo",
                        "repositoryName": "another-repo",
                        "branches": [],
                    },
                ],
            },
        })

    def test_registration_stores_profile_fields_at_document_root(self):
        with (
            patch.object(backend, "account_collection", return_value=self.collection),
            patch.object(backend, "_ensure_demo_accounts"),
            patch.object(backend, "_account_response", side_effect=lambda account: account),
        ):
            result = backend.register(backend.RegisterRequest(
                username="new-user",
                email="new@example.com",
                password="password123",
            ))

        self.assertEqual(result["username"], "new-user")
        self.assertEqual(result["noOfRepositories"], 0)
        self.assertNotIn("userData", self.collection.document)

    def test_frontend_update_flattens_legacy_nested_profile(self):
        data = backend._user_data(self.collection.document)

        with patch.object(backend, "account_collection", return_value=self.collection):
            result = backend.update_user_data(
                {"userData": data}, self.collection.document
            )

        self.assertEqual(result["userData"]["noOfRepositories"], 2)
        self.assertEqual(self.collection.document["repositories"], data["repositories"])
        self.assertEqual(self.collection.document["noOfCommits"], 1)
        self.assertNotIn("userData", self.collection.document)

    def test_push_upserts_one_branch_without_replacing_user_repositories(self):
        payload = {
            "username": "bob",
            "email": "BOB@example.com",
            "repository": {
                "repositoryId": "demo",
                "branches": [{
                    "branchName": "feature",
                    "headCommitId": "feature-1",
                    "commits": [{"commitId": "feature-1"}],
                }],
            },
        }

        with patch.object(backend, "account_collection", return_value=self.collection):
            result = backend.push_repository("demo", payload)

        self.assertEqual(result["repositoryId"], "demo")
        repositories = self.collection.document["repositories"]
        demo = next(item for item in repositories if item["repositoryId"] == "demo")
        self.assertEqual({branch["branchName"] for branch in demo["branches"]}, {"main", "feature"})
        self.assertEqual(demo["repositoryName"], "AIVCS-project")
        self.assertIn("another-repo", {item["repositoryId"] for item in repositories})
        self.assertNotIn("userData", self.collection.document)

    def test_clone_returns_all_branches_from_user_data(self):
        with patch.object(backend, "account_collection", return_value=self.collection):
            result = backend.clone_repository("demo", "bob", "bob@example.com")

        self.assertEqual([branch["branchName"] for branch in result["branches"]], ["main"])
        self.assertEqual(result["repositoryName"], "AIVCS-project")

    def test_push_creates_repository_when_repo_id_is_new(self):
        payload = {
            "username": "bob",
            "email": "bob@example.com",
            "repository": {
                "repositoryId": "new-demo",
                "branches": [{
                    "branchName": "feature",
                    "headCommitId": "feature-1",
                    "commits": [{"commitId": "feature-1"}],
                }],
            },
        }

        with patch.object(backend, "account_collection", return_value=self.collection):
            backend.push_repository("new-demo", payload)

        repositories = self.collection.document["repositories"]
        created = next(item for item in repositories if item["repositoryId"] == "new-demo")
        self.assertEqual(created["repositoryName"], "new-demo")
        self.assertEqual(created["description"], "")
        self.assertEqual(created["branches"][0]["branchName"], "feature")
        self.assertEqual(self.collection.document["noOfRepositories"], 3)

    def test_push_replaces_existing_branch_snapshot(self):
        payload = {
            "username": "bob",
            "email": "bob@example.com",
            "repository": {
                "repositoryId": "demo",
                "branches": [{
                    "branchName": "main",
                    "headCommitId": "main-2",
                    "commits": [{"commitId": "main-2"}],
                }],
            },
        }

        with patch.object(backend, "account_collection", return_value=self.collection):
            backend.push_repository("demo", payload)

        repositories = self.collection.document["repositories"]
        demo = next(item for item in repositories if item["repositoryId"] == "demo")
        self.assertEqual(len(demo["branches"]), 1)
        self.assertEqual(demo["branches"][0]["headCommitId"], "main-2")
        self.assertEqual(demo["repositoryName"], "AIVCS-project")
        self.assertNotIn("userData", self.collection.document)

    def test_push_requires_matching_username_and_email(self):
        payload = {
            "username": "bob",
            "email": "wrong@example.com",
            "repository": {"branches": []},
        }
        with patch.object(backend, "account_collection", return_value=self.collection):
            with self.assertRaises(HTTPException) as error:
                backend.push_repository("demo", payload)
        self.assertEqual(error.exception.status_code, 404)


if __name__ == "__main__":
    unittest.main()