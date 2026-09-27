import hashlib
import os
import re
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field
from pymongo import MongoClient
from pymongo.errors import DuplicateKeyError


BACKEND_DIR = Path(__file__).resolve().parent
load_dotenv(BACKEND_DIR / "atlas-credentials.env", override=False)
load_dotenv(BACKEND_DIR / ".env", override=False)

app = FastAPI(title="AIVCS backend")
app.add_middleware(
	CORSMiddleware,
	allow_origins=[
		origin.strip()
		for origin in os.environ.get(
			"AIVCS_CORS_ORIGINS", "http://localhost:5173,http://localhost:4173"
		).split(",")
		if origin.strip()
	],
	allow_credentials=True,
	allow_methods=["*"],
	allow_headers=["*"],
)
_client: MongoClient | None = None
_security = HTTPBearer(auto_error=False)
_SESSION_DAYS = 14


class RegisterRequest(BaseModel):
	username: str = Field(min_length=1, max_length=64)
	email: str = Field(min_length=3, max_length=254)
	password: str = Field(min_length=6, max_length=256)


class LoginRequest(BaseModel):
	email: str = Field(min_length=3, max_length=254)
	password: str = Field(min_length=1, max_length=256)


def _database():
	global _client
	uri = os.environ.get("MONGODB_URI")
	if not uri:
		raise HTTPException(status_code=500, detail="MONGODB_URI is not configured")
	if _client is None:
		_client = MongoClient(uri, serverSelectionTimeoutMS=5000)
	database_name = os.environ.get("MONGODB_DATABASE") or os.environ.get("DB_NAME", "aivcs")
	return _client[database_name]


def repository_collection():
	collection = _database().repositories
	collection.create_index("username", unique=True)
	return collection


def account_collection():
	collection_name = os.environ.get("MONGODB_USERS_COLLECTION", "userdata")
	collection = _database()[collection_name]
	collection.create_index("email", unique=True, sparse=True)
	return collection


def session_collection():
	collection = _database().sessions
	collection.create_index("tokenHash", unique=True)
	collection.create_index("expiresAt", expireAfterSeconds=0)
	return collection


def _normalize_email(email: str) -> str:
	value = email.strip().lower()
	if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
		raise HTTPException(status_code=422, detail="A valid email address is required")
	return value


def _bob_user_data() -> dict[str, Any]:
	return {
		"email": "bob@example.com",
		"username": "bob",
		"createdAt": "2026-09-24T13:00:00+00:00",
		"noOfRepositories": 2,
		"noOfCommits": 3,
		"repositories": [
			{
				"repositoryId": "demo",
				"repositoryName": "AIVCS-project",
				"description": "AIVCS project repository",
				"branches": [
					{
						"branchName": "main",
						"headCommitId": "bob-main-002",
						"commits": [
							{
								"commitId": "bob-main-001",
								"message": "Initial commit",
								"timestamp": "2026-09-24T13:05:00+00:00",
								"author": "bob",
								"parent": None,
								"fileDetails": [{
									"filename": "README",
									"fileextension": ".md",
									"content": "# Bob's project",
									"contentHash": "hash-bob-main",
								}],
							},
							{
								"commitId": "bob-main-002",
								"message": "Added main.py",
								"timestamp": "2026-09-24T13:10:00+00:00",
								"author": "bob",
								"parent": "bob-main-001",
								"fileDetails": [{
									"filename": "main",
									"fileextension": ".py",
									"content": "print('Hello, World!')",
									"contentHash": "hash-bob-main-002",
								}],
							},
						],
					},
					{
						"branchName": "feature-branch",
						"headCommitId": "bob-feature-001",
						"commits": [{
							"commitId": "bob-feature-001",
							"message": "Initial commit on feature branch",
							"timestamp": "2026-09-24T13:20:00+00:00",
							"author": "bob",
							"parent": None,
							"fileDetails": [{
								"filename": "feature.py",
								"fileextension": ".py",
								"content": "print('Feature implementation')",
								"contentHash": "hash-bob-feature-001",
							}],
						}],
					},
				],
			},
			{
				"repositoryId": "demo2",
				"repositoryName": "AIVCS-project-2",
				"description": "AIVCS project repository 2",
				"branches": [{
					"branchName": "main",
					"headCommitId": "bob-main-003",
					"commits": [{
						"commitId": "bob-main-003",
						"message": "Initial commit for repo 2",
						"timestamp": "2026-09-24T13:15:00+00:00",
						"author": "bob",
						"parent": None,
						"fileDetails": [{
							"filename": "README",
							"fileextension": ".md",
							"content": "# Bob's project 2",
							"contentHash": "hash-bob-main-003",
						}],
					}],
				}],
			},
		],
	}


def _demo_accounts() -> list[dict[str, Any]]:
	return [
		{
			"email": "bob@example.com",
			"username": "bob",
			"password": "bob-password",
			"userData": _bob_user_data(),
		},
		{
			"email": "alice@example.com",
			"username": "alice",
			"password": "alice-password",
			"userData": {
				"email": "alice@example.com",
				"username": "alice",
				"createdAt": "2026-09-24T13:00:00+00:00",
				"noOfRepositories": 1,
				"noOfCommits": 0,
				"repositories": [{
					"repositoryId": "alice-playground",
					"repositoryName": "playground",
					"description": "Alice's demo repository",
					"branches": [{
						"branchName": "main",
						"headCommitId": None,
						"commits": [],
					}],
				}],
			},
		},
	]


def _ensure_demo_accounts(collection) -> None:
	for demo in _demo_accounts():
		existing = collection.find_one({"email": demo["email"]}) or collection.find_one(
			{"username": demo["username"]}
		)
		if existing:
			if not existing.get("email"):
				collection.update_one(
					{"_id": existing["_id"]}, {"$set": {"email": demo["email"]}}
				)
			continue
		demo_document = {
			**demo["userData"],
			"password": demo["password"],
		}
		try:
			collection.insert_one(demo_document)
		except DuplicateKeyError:
			continue


def _user_data(document: dict[str, Any]) -> dict[str, Any]:
	stored = document.get("userData")
	if isinstance(stored, dict):
		data = dict(stored)
	else:
		data = {
			key: document[key]
			for key in ("email", "username", "createdAt", "noOfRepositories", "noOfCommits", "repositories")
			if key in document
		}
	data.setdefault("email", document.get("email", ""))
	data.setdefault("username", document.get("username", ""))
	data.setdefault("createdAt", document.get("createdAt", datetime.now(timezone.utc).isoformat()))
	data.setdefault("repositories", [])
	data.setdefault("noOfRepositories", len(data["repositories"]))
	data.setdefault("noOfCommits", 0)
	return data


def _public_account(document: dict[str, Any]) -> dict[str, str]:
	return {"email": document["email"], "username": document["username"]}


def _create_session(document: dict[str, Any]) -> dict[str, str]:
	token = secrets.token_urlsafe(32)
	expires_at = datetime.now(timezone.utc) + timedelta(days=_SESSION_DAYS)
	session_collection().insert_one({
		"tokenHash": hashlib.sha256(token.encode("utf-8")).hexdigest(),
		"email": document["email"],
		"expiresAt": expires_at,
	})
	return {"access_token": token, "token_type": "bearer"}


def _account_response(document: dict[str, Any]) -> dict[str, Any]:
	return {
		**_create_session(document),
		"user": _public_account(document),
		"userData": _user_data(document),
	}


def _current_account(
	credentials: HTTPAuthorizationCredentials | None = Depends(_security),
) -> dict[str, Any]:
	if not credentials or credentials.scheme.lower() != "bearer":
		raise HTTPException(status_code=401, detail="Bearer token required")
	token_hash = hashlib.sha256(credentials.credentials.encode("utf-8")).hexdigest()
	session = session_collection().find_one({
		"tokenHash": token_hash,
		"expiresAt": {"$gt": datetime.now(timezone.utc)},
	})
	if not session:
		raise HTTPException(status_code=401, detail="Session is invalid or expired")
	account = account_collection().find_one({"email": session["email"]})
	if not account:
		raise HTTPException(status_code=401, detail="Account no longer exists")
	return account


def _repository_from_payload(payload: dict[str, Any], repository: str) -> dict[str, Any]:
	value = payload.get("repository")
	if not isinstance(value, dict):
		raise HTTPException(status_code=422, detail="repository must contain repositoryId and branches")
	value = dict(value)
	value["repositoryId"] = repository
	if not isinstance(value.get("branches"), list):
		raise HTTPException(status_code=422, detail="repository.branches must be an array")
	if any(not isinstance(branch, dict) or not branch.get("branchName") for branch in value["branches"]):
		raise HTTPException(status_code=422, detail="each branch must contain branchName")
	return value


@app.get("/health")
def health() -> dict[str, str]:
	return {"status": "ok"}


@app.post("/api/auth/register", status_code=201)
def register(payload: RegisterRequest) -> dict[str, Any]:
	email = _normalize_email(payload.email)
	username = payload.username.strip()
	if not username:
		raise HTTPException(status_code=422, detail="Username is required")
	collection = account_collection()
	_ensure_demo_accounts(collection)
	if collection.find_one({"email": email}):
		raise HTTPException(status_code=409, detail="An account with this email already exists")
	created_at = datetime.now(timezone.utc).isoformat()
	user_data = {
		"email": email,
		"username": username,
		"createdAt": created_at,
		"noOfRepositories": 0,
		"noOfCommits": 0,
		"repositories": [],
	}
	account = {**user_data, "password": payload.password}
	try:
		collection.insert_one(account)
	except DuplicateKeyError as error:
		raise HTTPException(status_code=409, detail="An account with this email already exists") from error
	return _account_response(account)


@app.post("/api/auth/login")
def login(payload: LoginRequest) -> dict[str, Any]:
	email = _normalize_email(payload.email)
	collection = account_collection()
	_ensure_demo_accounts(collection)
	account = collection.find_one({"email": email})
	if not account:
		raise HTTPException(status_code=401, detail="Email or password is incorrect")
	if account.get("password") != payload.password:
		raise HTTPException(status_code=401, detail="Email or password is incorrect")
	return _account_response(account)


@app.get("/api/auth/me")
def current_user(account: dict[str, Any] = Depends(_current_account)) -> dict[str, Any]:
	return {"user": _public_account(account), "userData": _user_data(account)}


@app.post("/api/auth/logout")
def logout(
	credentials: HTTPAuthorizationCredentials | None = Depends(_security),
	account: dict[str, Any] = Depends(_current_account),
) -> dict[str, str]:
	assert credentials is not None
	token_hash = hashlib.sha256(credentials.credentials.encode("utf-8")).hexdigest()
	session_collection().delete_one({"tokenHash": token_hash, "email": account["email"]})
	return {"message": "Signed out"}


@app.get("/api/userdata")
def get_user_data(account: dict[str, Any] = Depends(_current_account)) -> dict[str, Any]:
	return {"userData": _user_data(account)}


@app.put("/api/userdata")
def update_user_data(
	payload: dict[str, Any], account: dict[str, Any] = Depends(_current_account)
) -> dict[str, Any]:
	data = payload.get("userData", payload)
	if not isinstance(data, dict):
		raise HTTPException(status_code=422, detail="userData must be an object")
	repositories = data.get("repositories", [])
	if not isinstance(repositories, list) or any(not isinstance(repo, dict) for repo in repositories):
		raise HTTPException(status_code=422, detail="repositories must be an array of objects")
	data = dict(data)
	data["email"] = account["email"]
	data["username"] = account["username"]
	data["repositories"] = repositories
	data["noOfRepositories"] = len(repositories)
	data["noOfCommits"] = sum(
		len(branch.get("commits", []))
		for repository in repositories
		for branch in repository.get("branches", [])
		if isinstance(branch, dict) and isinstance(branch.get("commits", []), list)
	)
	data.setdefault("createdAt", account.get("createdAt", datetime.now(timezone.utc).isoformat()))
	account_collection().update_one(
		{"_id": account["_id"]},
		{
			"$set": {
				key: data[key]
				for key in (
					"email",
					"username",
					"createdAt",
					"noOfRepositories",
					"noOfCommits",
					"repositories",
				)
			},
			"$unset": {"userData": ""},
		},
	)
	return {"userData": data}


@app.post("/repositories/{repository}/push")
def push_repository(repository: str, payload: dict[str, Any]) -> dict[str, Any]:
	username = payload.get("username")
	email = payload.get("email")
	if not username or not email:
		raise HTTPException(status_code=401, detail="Username and email are required")
	collection = account_collection()
	current = collection.find_one({"username": username.strip(), "email": _normalize_email(email)})
	if not current:
		raise HTTPException(status_code=404, detail="AIVCS account not found")
	user_data = _user_data(current)
	repositories = list(user_data.get("repositories", []))
	pushed = _repository_from_payload(payload, repository)
	existing_repository = next(
		(item for item in repositories if item.get("repositoryId") == repository),
		None,
	)
	branches = list(existing_repository.get("branches", [])) if existing_repository else []
	for pushed_branch in pushed["branches"]:
		branches = [item for item in branches if item.get("branchName") != pushed_branch["branchName"]]
		branches.append(pushed_branch)
	merged_repository = {
		**(existing_repository or {}),
		"repositoryId": repository,
		"repositoryName": (existing_repository or {}).get("repositoryName")
			or pushed.get("repositoryName")
			or repository,
		"description": (existing_repository or {}).get("description")
			or pushed.get("description", ""),
		"branches": branches,
	}
	repositories = [item for item in repositories if item.get("repositoryId") != repository]
	repositories.append(merged_repository)
	user_data["repositories"] = repositories
	user_data["noOfRepositories"] = len(repositories)
	user_data["noOfCommits"] = sum(
		len(branch.get("commits", []))
		for item in repositories
		for branch in item.get("branches", [])
		if isinstance(branch, dict) and isinstance(branch.get("commits", []), list)
	)
	collection.update_one(
		{"_id": current["_id"]},
		{"$set": {
			key: user_data[key]
			for key in (
				"email",
				"username",
				"createdAt",
				"noOfRepositories",
				"noOfCommits",
				"repositories",
			)
		}, "$unset": {"userData": ""}},
	)
	return {"message": f"Pushed {repository} successfully.", "repositoryId": repository}


@app.get("/repositories/{repository}/clone")
def clone_repository(repository: str, username: str = "", email: str = "") -> dict[str, Any]:
	if not username or not email:
		raise HTTPException(status_code=401, detail="Username and email are required")
	document = account_collection().find_one({
		"username": username.strip(),
		"email": _normalize_email(email),
	})
	if not document:
		raise HTTPException(status_code=404, detail="AIVCS account not found")
	repository_data = next(
		(item for item in _user_data(document).get("repositories", []) if item.get("repositoryId") == repository),
		None,
	)
	if not repository_data:
		raise HTTPException(status_code=404, detail=f"Repository not found: {repository}")
	return repository_data
