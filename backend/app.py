import hashlib
import json
import os
import re
import secrets
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field
from pymongo import MongoClient
from pymongo.errors import DuplicateKeyError, PyMongoError


BACKEND_DIR = Path(__file__).resolve().parent
load_dotenv(BACKEND_DIR / ".env", override=True)
load_dotenv(BACKEND_DIR / "atlas-credentials.env", override=False)

app = FastAPI(title="AIVCS backend")


@app.exception_handler(PyMongoError)
async def pymongo_exception_handler(_request, exc: PyMongoError):
	return JSONResponse(
		status_code=503,
		content={
			"detail": f"Database error: {exc}. Please verify MongoDB Atlas Network Access (IP whitelist) and credentials."
		},
	)


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
class LocalCollection:
	def __init__(self, name: str, db: "LocalDatabase"):
		self.name = name
		self.db = db
		self.indexes: list[dict[str, Any]] = []

	def create_index(self, key: str, unique: bool = False, sparse: bool = False, expireAfterSeconds: int | None = None) -> str:
		self.indexes.append({"key": key, "unique": unique, "sparse": sparse})
		return key

	def _matches(self, doc: dict[str, Any], query: dict[str, Any]) -> bool:
		for k, v in query.items():
			doc_val = doc.get(k)
			if isinstance(v, dict):
				for op, op_val in v.items():
					if op == "$gt":
						dv = doc_val
						ov = op_val
						if isinstance(dv, str):
							try:
								dv = datetime.fromisoformat(dv)
							except Exception:
								pass
						if isinstance(ov, str):
							try:
								ov = datetime.fromisoformat(ov)
							except Exception:
								pass
						if dv is None or dv <= ov:
							return False
					elif op == "$lt":
						dv = doc_val
						ov = op_val
						if isinstance(dv, str):
							try:
								dv = datetime.fromisoformat(dv)
							except Exception:
								pass
						if isinstance(ov, str):
							try:
								ov = datetime.fromisoformat(ov)
							except Exception:
								pass
						if dv is None or dv >= ov:
							return False
					else:
						return False
			else:
				if k == "_id":
					if str(doc_val) != str(v):
						return False
				elif doc_val != v:
					return False
		return True

	def find_one(self, query: dict[str, Any] | None = None) -> dict[str, Any] | None:
		query = query or {}
		docs = self.db._data.setdefault(self.name, [])
		for d in docs:
			if self._matches(d, query):
				return dict(d)
		return None

	def insert_one(self, doc: dict[str, Any]):
		docs = self.db._data.setdefault(self.name, [])
		item = dict(doc)
		if "_id" not in item:
			item["_id"] = secrets.token_hex(12)
		for idx in self.indexes:
			if idx.get("unique"):
				key = idx["key"]
				val = item.get(key)
				if val is not None or not idx.get("sparse"):
					for existing in docs:
						if existing.get(key) == val and val is not None:
							raise DuplicateKeyError(f"Duplicate key for index {key}: {val}")
		docs.append(item)
		self.db._save()
		return type("InsertResult", (), {"inserted_id": item["_id"]})()

	def update_one(self, query: dict[str, Any], update: dict[str, Any]):
		docs = self.db._data.setdefault(self.name, [])
		for item in docs:
			if self._matches(item, query):
				if "$set" in update:
					for k, v in update["$set"].items():
						item[k] = v
				if "$unset" in update:
					for k in update["$unset"]:
						item.pop(k, None)
				self.db._save()
				return type("UpdateResult", (), {"modified_count": 1})()
		return type("UpdateResult", (), {"modified_count": 0})()

	def delete_one(self, query: dict[str, Any]):
		docs = self.db._data.setdefault(self.name, [])
		for idx, item in enumerate(docs):
			if self._matches(item, query):
				docs.pop(idx)
				self.db._save()
				return type("DeleteResult", (), {"deleted_count": 1})()
		return type("DeleteResult", (), {"deleted_count": 0})()


class LocalDatabase:
	def __init__(self, filepath: Path | None = None):
		self.filepath = filepath
		self._data: dict[str, list[dict[str, Any]]] = {}
		self._load()

	def _load(self) -> None:
		if self.filepath and self.filepath.exists():
			try:
				with open(self.filepath, "r", encoding="utf-8") as f:
					self._data = json.load(f)
			except Exception:
				self._data = {}

	def _save(self) -> None:
		if self.filepath:
			try:
				def default_json(obj: Any) -> str:
					if isinstance(obj, datetime):
						return obj.isoformat()
					return str(obj)

				with open(self.filepath, "w", encoding="utf-8") as f:
					json.dump(self._data, f, indent=2, default=default_json)
			except Exception as exc:
				print(f"[AIVCS] Warning: could not persist local db: {exc}")

	def __getitem__(self, name: str) -> LocalCollection:
		return LocalCollection(name, self)

	def __getattr__(self, name: str) -> LocalCollection:
		return self[name]


_client: MongoClient | None = None
_client_uri: str | None = None
_atlas_available: bool | None = None
_last_atlas_check: float = 0.0
_local_db: LocalDatabase | None = None
_security = HTTPBearer(auto_error=False)
_SESSION_DAYS = 14


class RegisterRequest(BaseModel):
	username: str = Field(min_length=1, max_length=64)
	email: str = Field(min_length=3, max_length=254)
	password: str = Field(min_length=6, max_length=256)


class LoginRequest(BaseModel):
	email: str = Field(min_length=3, max_length=254)
	password: str = Field(min_length=1, max_length=256)


def _get_local_db() -> LocalDatabase:
	global _local_db
	if _local_db is None:
		_local_db = LocalDatabase(BACKEND_DIR / ".local_db.json")
	return _local_db


def _database():
	global _client, _client_uri, _atlas_available, _last_atlas_check
	load_dotenv(BACKEND_DIR / ".env", override=True)
	load_dotenv(BACKEND_DIR / "atlas-credentials.env", override=False)

	if os.environ.get("USE_LOCAL_DB", "").lower() in ("true", "1", "yes"):
		return _get_local_db()

	uri = os.environ.get("MONGODB_URI")
	if not uri:
		return _get_local_db()

	now = time.time()
	if _atlas_available is False and (now - _last_atlas_check < 30.0):
		return _get_local_db()

	try:
		if _client is None or _client_uri != uri:
			_client = MongoClient(uri, serverSelectionTimeoutMS=2000)
			_client_uri = uri
		_client.admin.command("ping")
		_atlas_available = True
		_last_atlas_check = now
		database_name = os.environ.get("MONGODB_DATABASE") or os.environ.get("DB_NAME", "aivcs")
		return _client[database_name]
	except Exception as exc:
		_atlas_available = False
		_last_atlas_check = now
		print(f"[AIVCS] Notice: MongoDB Atlas unavailable ({exc}). Using local database.")
		return _get_local_db()


def repository_collection():
	try:
		collection = _database().repositories
		collection.create_index("username", unique=True)
		return collection
	except PyMongoError:
		global _atlas_available
		_atlas_available = False
		collection = _get_local_db().repositories
		collection.create_index("username", unique=True)
		return collection


def account_collection():
	collection_name = os.environ.get("MONGODB_USERS_COLLECTION", "userdata")
	try:
		collection = _database()[collection_name]
		collection.create_index("email", unique=True, sparse=True)
		return collection
	except PyMongoError:
		global _atlas_available
		_atlas_available = False
		collection = _get_local_db()[collection_name]
		collection.create_index("email", unique=True, sparse=True)
		return collection


def session_collection():
	try:
		collection = _database().sessions
		collection.create_index("tokenHash", unique=True)
		collection.create_index("expiresAt", expireAfterSeconds=0)
		return collection
	except PyMongoError:
		global _atlas_available
		_atlas_available = False
		collection = _get_local_db().sessions
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
