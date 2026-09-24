import os
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, HTTPException
from pymongo import MongoClient


app = FastAPI(title="AIVCS backend")
_client: MongoClient | None = None


def repository_collection():
	global _client
	uri = os.environ.get("MONGODB_URI")
	if not uri:
		raise HTTPException(status_code=500, detail="MONGODB_URI is not configured")
	if _client is None:
		_client = MongoClient(uri)
	database = _client[os.environ.get("MONGODB_DATABASE", "aivcs")]
	collection = database.repositories
	collection.create_index("username", unique=True)
	return collection


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


@app.post("/repositories/{repository}/push")
def push_repository(repository: str, payload: dict[str, Any]) -> dict[str, Any]:
	username = payload.get("username")
	password = payload.get("password")
	if not username or not password:
		raise HTTPException(status_code=401, detail="Username and password are required")

	collection = repository_collection()
	current = collection.find_one({"username": username})
	if current and current.get("password") != password:
		raise HTTPException(status_code=401, detail="Invalid username or password")
	repositories = list(current.get("repositories", [])) if current else []
	pushed = _repository_from_payload(payload, repository)
	existing_repository = next(
		(item for item in repositories if item.get("repositoryId") == repository),
		None,
	)
	branches = list(existing_repository.get("branches", [])) if existing_repository else []
	for pushed_branch in pushed["branches"]:
		branches = [item for item in branches if item.get("branchName") != pushed_branch["branchName"]]
		branches.append(pushed_branch)
	merged_repository = {"repositoryId": repository, "branches": branches}
	repositories = [item for item in repositories if item.get("repositoryId") != repository]
	repositories.append(merged_repository)
	document = {
		"email": payload.get("email", current.get("email", "") if current else ""),
		"username": username,
		"password": password,
		"createdAt": current.get("createdAt") if current else datetime.now(timezone.utc).isoformat(),
		"repositories": repositories,
	}
	collection.replace_one({"username": username}, document, upsert=True)
	return {"message": f"Pushed {repository} successfully.", "repositoryId": repository}


@app.get("/repositories/{repository}/clone")
def clone_repository(repository: str, username: str, password: str) -> dict[str, Any]:
	document = repository_collection().find_one({"username": username, "password": password})
	if not document:
		raise HTTPException(status_code=401, detail="Invalid username or password")
	repository_data = next(
		(item for item in document.get("repositories", []) if item.get("repositoryId") == repository),
		None,
	)
	if not repository_data:
		raise HTTPException(status_code=404, detail=f"Repository not found: {repository}")
	return repository_data
