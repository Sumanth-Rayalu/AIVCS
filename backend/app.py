from __future__ import annotations

import difflib
from logging import root
import os
import re
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import bcrypt
import jwt
from dotenv import load_dotenv
from fastapi import Cookie, Depends, FastAPI, File, Form, HTTPException, Query, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator 
from aivcs.commits import create_commit, history, read_commit
from aivcs.diff import build_diff, object_text
from aivcs.repository import aivcs_path, find_root, head_id, init_repository
from aivcs.remotes import add_remote, list_remotes, pull, push, remove_remote
from aivcs.staging import add, relative_files, status
from backend.database import connection, initialize, user_row

ENV_FILE = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(ENV_FILE, override=True)


PROJECT_ROOT = Path(os.environ.get("AIVCS_ROOT", Path(__file__).resolve().parents[1])).resolve()
WORKSPACE_ROOT = Path(os.environ.get("AIVCS_WORKSPACE", PROJECT_ROOT.parent / "aivcs-workspace")).expanduser().resolve()
REPOSITORY_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")

app = FastAPI(title="AIVCSHub API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("AIVCS_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def jwt_secret() -> str:
    secret = os.environ.get("JWT_SECRET")
    if not secret:
        raise HTTPException(status_code=503, detail="JWT_SECRET is not configured")
    return secret


def db_ready() -> None:
    try:
        initialize()
    except Exception as error:
        raise HTTPException(status_code=503, detail=f"Database unavailable: {error}") from error


def authenticated_user(aivcs_token: str | None = Cookie(default=None)) -> dict[str, Any]:
    if not aivcs_token:
        raise HTTPException(status_code=401, detail="Authentication required")
    try:
        payload = jwt.decode(aivcs_token, jwt_secret(), algorithms=["HS256"])
        user_id = int(payload["sub"])
    except (jwt.InvalidTokenError, KeyError, TypeError, ValueError) as error:
        raise HTTPException(status_code=401, detail="Invalid or expired session") from error
    db_ready()
    with connection() as db:
        cursor = db.cursor()
        cursor.execute("SELECT id, username, name, email, created_at FROM users WHERE id = %s", (user_id,))
        user = user_row(cursor.fetchone())
        cursor.close()
    if not user:
        raise HTTPException(status_code=401, detail="User no longer exists")
    return user


class RepositoryCreate(BaseModel):
    name: str
    description: str = ""
    initialize_readme: bool = True

    @field_validator("name")
    @classmethod
    def valid_name(cls, value: str) -> str:
        value = value.strip()
        if not REPOSITORY_NAME.fullmatch(value):
            raise ValueError("Repository name may contain letters, numbers, dots, dashes, and underscores.")
        return value


class StageRequest(BaseModel):
    paths: list[str] = Field(default_factory=lambda: ["."])


class CommitRequest(BaseModel):
    message: str = Field(min_length=1, max_length=200)
    author: str = Field(default="AIVCS User", max_length=100)

    @field_validator("message")
    @classmethod
    def valid_message(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Commit message is required.")
        return value


class RemoteRequest(BaseModel):
    name: str = "origin"
    location: str


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    name: str = Field(min_length=1, max_length=120)
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=8, max_length=128)
    confirm_password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    identifier: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=1, max_length=128)


def create_session(response: Response, user_id: int) -> None:
    token = jwt.encode(
        {"sub": str(user_id), "exp": datetime.now(timezone.utc) + timedelta(hours=12)},
        jwt_secret(),
        algorithm="HS256",
    )
    response.set_cookie("aivcs_token", token, httponly=True, samesite="lax", secure=False, max_age=43200)


def repository_root() -> Path:
    try:
        return find_root(PROJECT_ROOT)
    except RuntimeError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


def ensure_workspace() -> None:
    WORKSPACE_ROOT.mkdir(parents=True, exist_ok=True)


def named_repository(name: str, owner_id: int | None = None) -> Path:
    if not REPOSITORY_NAME.fullmatch(name):
        raise HTTPException(status_code=400, detail="Invalid repository name")
    ensure_workspace()
    workspace = WORKSPACE_ROOT.resolve()
    if owner_id is not None:
        db_ready()
        with connection() as db:
            cursor = db.cursor()
            cursor.execute("SELECT path FROM repositories WHERE owner_id = %s AND name = %s", (owner_id, name))
            row = cursor.fetchone()
            cursor.close()
        if not row:
            raise HTTPException(status_code=404, detail="Repository not found")
        candidate = Path(row[0]).resolve()
    else:
        candidate = (workspace / name).resolve()
    expected_parent = workspace / str(owner_id) if owner_id is not None else workspace

    if candidate.parent != expected_parent or not (candidate / ".aivcs").is_dir():
        raise HTTPException(status_code=404, detail="Repository not found")
    return candidate


def branch_name(root: Path) -> str:
    head = aivcs_path(root, "HEAD").read_text(encoding="utf-8").strip()
    return head.rsplit("/", 1)[-1] if head.startswith("ref: ") else "detached"


def commit_diff(root: Path, commit_id: str) -> str:
    commit = read_commit(root, commit_id)
    parent = read_commit(root, commit["parent"]) if commit.get("parent") else {"files": {}}
    chunks: list[str] = []
    old_files = parent.get("files", {})
    new_files = commit.get("files", {})
    for path in sorted(set(old_files) | set(new_files)):
        old = object_text(root, old_files.get(path)).splitlines(keepends=True)
        new = object_text(root, new_files.get(path)).splitlines(keepends=True)
        chunks.extend(difflib.unified_diff(old, new, fromfile=f"a/{path}", tofile=f"b/{path}"))
    return "".join(chunks)


def repository_payload(root: Path) -> dict[str, Any]:
    changes = status(root)
    commits = history(root)
    latest = commits[0] if commits else None
    description = ""
    try:
        with connection() as db:
            cursor = db.cursor()
            cursor.execute("SELECT description FROM repositories WHERE path = %s", (str(root),))
            row = cursor.fetchone()
            description = row[0] if row else ""
            cursor.close()
    except Exception:
        pass
    return {
        "name": root.name,
        "path": str(root),
        "description": description,
        "branch": branch_name(root),
        "head": head_id(root),
        "files": relative_files(root),
        "commits": commits,
        "latest_commit": latest,
        "status": changes,
        "clean": not any(changes.values()),
        "remotes": list_remotes(root),
        "stats": {"commits": len(commits), "files": len(relative_files(root)), "changes": sum(len(items) for items in changes.values())},
    }


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/auth/register", status_code=201)
def register(request: RegisterRequest, response: Response) -> dict[str, Any]:
    if request.password != request.confirm_password:
        raise HTTPException(status_code=400, detail="Passwords do not match")
    db_ready()
    password_hash = bcrypt.hashpw(request.password.encode(), bcrypt.gensalt()).decode()
    try:
        with connection() as db:
            cursor = db.cursor()
            cursor.execute(
                "INSERT INTO users (username, name, email, password_hash) VALUES (%s, %s, %s, %s)",
                (request.username.strip(), request.name.strip(), request.email.strip().lower(), password_hash),
            )
            db.commit()
            user_id = cursor.lastrowid
            cursor.close()
    except Exception as error:
        if "Duplicate" in str(error) or "1062" in str(error):
            raise HTTPException(status_code=409, detail="Username or email already exists") from error
        raise HTTPException(status_code=500, detail="Could not create account") from error
    create_session(response, int(user_id))
    return {"user": {"id": user_id, "username": request.username.strip(), "name": request.name.strip(), "email": request.email.strip().lower()}}


@app.post("/api/auth/login")
def login(request: LoginRequest, response: Response) -> dict[str, Any]:
    db_ready()
    with connection() as db:
        cursor = db.cursor()
        cursor.execute(
            "SELECT id, username, name, email, password_hash, created_at FROM users WHERE username = %s OR email = %s",
            (request.identifier.strip(), request.identifier.strip().lower()),
        )
        row = cursor.fetchone()
        cursor.close()
    if not row or not bcrypt.checkpw(request.password.encode(), row[4].encode()):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    user = user_row(row[:4] + (row[5],))
    create_session(response, int(row[0]))
    return {"user": user}


@app.post("/api/auth/logout")
def logout(response: Response) -> dict[str, bool]:
    response.delete_cookie("aivcs_token")
    return {"ok": True}


@app.get("/api/auth/me")
def me(user: dict[str, Any] = Depends(authenticated_user)) -> dict[str, Any]:
    return user


@app.get("/api/repositories")
def get_repositories(user: dict[str, Any] = Depends(authenticated_user)) -> list[dict[str, Any]]:
    db_ready()
    with connection() as db:
        cursor = db.cursor()
        cursor.execute("SELECT path FROM repositories WHERE owner_id = %s ORDER BY name", (user["id"],))
        paths = [Path(row[0]) for row in cursor.fetchall()]
        cursor.close()
    return [repository_payload(path) for path in paths if (path / ".aivcs").is_dir()]


@app.get("/api/dashboard")
def dashboard(user: dict[str, Any] = Depends(authenticated_user)) -> dict[str, int | str]:
    repositories = get_repositories(user)
    db_ready()
    with connection() as db:
        cursor = db.cursor()
        cursor.execute("SELECT COUNT(*) FROM follows WHERE followed_id = %s", (user["id"],))
        followers = int(cursor.fetchone()[0])
        cursor.execute("SELECT COUNT(*) FROM follows WHERE follower_id = %s", (user["id"],))
        following = int(cursor.fetchone()[0])
        cursor.execute("SELECT COUNT(*) FROM issues i JOIN repositories r ON r.id = i.repository_id WHERE r.owner_id = %s", (user["id"],))
        issues = int(cursor.fetchone()[0])
        cursor.close()
    return {
        "username": user["username"],
        "repositories": len(repositories),
        "commits": sum(len(repository["commits"]) for repository in repositories),
        "issues": issues,
        "tracked_files": sum(repository["stats"]["files"] for repository in repositories),
        "followers": followers,
        "following": following,
    }


def register_repository(user_id: int, name: str, description: str, root: Path) -> None:
    db_ready()
    try:
        with connection() as db:
            cursor = db.cursor()
            cursor.execute(
                "INSERT INTO repositories (owner_id, name, description, path) VALUES (%s, %s, %s, %s)",
                (user_id, name, description, str(root)),
            )
            db.commit()
            cursor.close()
    except Exception as error:
        if "Duplicate" in str(error) or "1062" in str(error):
            raise HTTPException(status_code=409, detail="Repository already exists") from error
        raise HTTPException(status_code=500, detail="Could not save repository metadata") from error


@app.post("/api/repositories", status_code=201)
def create_repository(request: RepositoryCreate, user: dict[str, Any] = Depends(authenticated_user)) -> dict[str, Any]:
    db_ready()
    ensure_workspace()
    root = WORKSPACE_ROOT / str(user["id"]) / request.name
    if root.exists():
        raise HTTPException(status_code=409, detail="Repository already exists")
    root.mkdir(parents=True)
    init_repository(root)
    if request.initialize_readme:
        (root / "README.md").write_text(f"# {request.name}\n\n{request.description}\n", encoding="utf-8")
    try:
        register_repository(user["id"], request.name, request.description, root)
    except Exception:
        shutil.rmtree(root, ignore_errors=True)
        raise
    return repository_payload(root)


@app.post("/api/repositories/import", status_code=201)
async def import_repository(
    name: str = Form(...),
    description: str = Form(""),
    files: list[UploadFile] = File(...),
    user: dict[str, Any] = Depends(authenticated_user),
) -> dict[str, Any]:
    name = RepositoryCreate(name=name, description=description).name
    ensure_workspace()
    root = (WORKSPACE_ROOT / str(user["id"]) / name).resolve()
    if root.exists():
        raise HTTPException(status_code=409, detail="Repository already exists")
    root.mkdir(parents=True)
    init_repository(root)
    relative_names = [Path(upload.filename or "").as_posix() for upload in files]
    parts = [Path(filename).parts for filename in relative_names]
    common_root = parts[0][0] if parts and all(item and item[0] == parts[0][0] for item in parts) else None
    try:
        for upload, filename in zip(files, relative_names):
            item = Path(filename)
            if common_root and len(item.parts) > 1:
                item = Path(*item.parts[1:])
            if not item.parts or item.name in {".env", ".aivcs"} or any(part in {".aivcs", ".env"} for part in item.parts):
                continue
            destination = (root / item).resolve()
            if root not in destination.parents:
                raise HTTPException(status_code=400, detail="Uploaded path is outside the repository")
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(await upload.read())
    except Exception:
        shutil.rmtree(root, ignore_errors=True)
        raise
    add(root, ["."])
    register_repository(user["id"], name, description, root)
    return repository_payload(root, owner_id=user["id"])


@app.delete("/api/repositories/{name}", status_code=204)
def delete_repository(name: str, user: dict[str, Any] = Depends(authenticated_user)) -> None:
    root = named_repository(name, user["id"])
    shutil.rmtree(root)
    with connection() as db:
        cursor = db.cursor()
        cursor.execute("DELETE FROM repositories WHERE owner_id = %s AND name = %s", (user["id"], name))
        db.commit()
        cursor.close()


@app.get("/api/repositories/{name}")
def get_repository_by_name(name: str, user: dict[str, Any] = Depends(authenticated_user)) -> dict[str, Any]:
    return repository_payload(named_repository(name, user["id"]))


@app.get("/api/repositories/{name}/status")
def get_repository_status(name: str, user: dict[str, Any] = Depends(authenticated_user)) -> dict[str, list[str]]:
    return status(named_repository(name, user["id"]))


@app.get("/api/repositories/{name}/files")
def get_repository_files(name: str, path: str = "", user: dict[str, Any] = Depends(authenticated_user)) -> dict[str, Any]:
    root = named_repository(name, user["id"])
    requested = (root / path).resolve()
    if root not in requested.parents and requested != root:
        raise HTTPException(status_code=400, detail="Path is outside the repository")
    if requested.is_dir():
        entries = []
        for child in sorted(requested.iterdir()):
            if child.name in {".aivcs", ".env"}:
                continue
            entries.append({"name": child.name, "path": child.relative_to(root).as_posix(), "directory": child.is_dir()})
        return {"path": path, "entries": entries}
    if requested.is_file() and requested.name != ".env":
        return {"path": requested.relative_to(root).as_posix(), "content": requested.read_text(encoding="utf-8", errors="replace")}
    raise HTTPException(status_code=404, detail="File not found")


@app.get("/api/repositories/{name}/diff")
def get_repository_diff(name: str, staged: bool = Query(False), user: dict[str, Any] = Depends(authenticated_user)) -> dict[str, str]:
    return {"diff": build_diff(named_repository(name, user["id"]), staged=staged)}


@app.post("/api/repositories/{name}/add")
def stage_repository(name: str, request: StageRequest, user: dict[str, Any] = Depends(authenticated_user)) -> dict[str, Any]:
    root = named_repository(name, user["id"])
    try:
        staged = add(root, request.paths)
    except (FileNotFoundError, RuntimeError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return {"staged": staged, "repository": repository_payload(root)}


@app.post("/api/repositories/{name}/commit")
def commit_repository(name: str, request: CommitRequest, user: dict[str, Any] = Depends(authenticated_user)) -> dict[str, Any]:
    root = named_repository(name, user["id"])
    try:
        commit = create_commit(root, request.message, user["username"])
    except RuntimeError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return {"commit": commit, "repository": repository_payload(root)}


@app.get("/api/repositories/{name}/commits")
def get_commits(name: str, user: dict[str, Any] = Depends(authenticated_user)) -> list[dict[str, Any]]:
    return history(named_repository(name, user["id"]))


@app.get("/api/repositories/{name}/commits/{commit_id}")
def get_commit(name: str, commit_id: str, user: dict[str, Any] = Depends(authenticated_user)) -> dict[str, Any]:
    root = named_repository(name, user["id"])
    match = next((item for item in history(root) if item["id"].startswith(commit_id)), None)
    if not match:
        raise HTTPException(status_code=404, detail="Commit not found")
    return {**match, "diff": commit_diff(root, match["id"])}


@app.get("/api/repositories/{name}/remote")
def get_remote(name: str, user: dict[str, Any] = Depends(authenticated_user)) -> dict[str, str]:
    return list_remotes(named_repository(name, user["id"]))


@app.post("/api/repositories/{name}/remote")
def configure_remote(name: str, request: RemoteRequest, user: dict[str, Any] = Depends(authenticated_user)) -> dict[str, str]:
    root = named_repository(name, user["id"])
    add_remote(root, request.name, request.location)
    return list_remotes(root)


@app.delete("/api/repositories/{name}/remote/{remote_name}", status_code=204)
def delete_remote(name: str, remote_name: str, user: dict[str, Any] = Depends(authenticated_user)) -> None:
    remove_remote(named_repository(name, user["id"]), remote_name)


@app.post("/api/repositories/{name}/push")
def push_repository(name: str, remote: str = "origin", user: dict[str, Any] = Depends(authenticated_user)) -> dict[str, object]:
    try:
        return push(named_repository(name, user["id"]), remote)
    except RuntimeError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.post("/api/repositories/{name}/pull")
def pull_repository(name: str, remote: str = "origin", user: dict[str, Any] = Depends(authenticated_user)) -> dict[str, object]:
    try:
        root = named_repository(name, user["id"])
        result = pull(root, remote)
    except RuntimeError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    result["repository"] = repository_payload(root)
    return result


