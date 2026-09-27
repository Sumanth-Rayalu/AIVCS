# AIVCS and AIVCSHub

AIVCS is the file-backed version-control engine. AIVCSHub is the FastAPI and React interface over that same core. Phase 1 supports repository initialization and discovery, staging, status, working and staged diffs, commits, history, file browsing, persistent workspace repositories, local filesystem remotes, push, and pull.

## Run from the workspace

```powershell
python -m aivcs.cli init
python -m aivcs.cli add .
python -m aivcs.cli status
python -m aivcs.cli diff --staged
python -m aivcs.cli commit -m "feat: initialize project"
python -m aivcs.cli log --oneline
python -m aivcs.cli show <commit-id>
python -m aivcs.cli remote add origin ..\aivcs-remotes\my-project
python -m aivcs.cli remote -v
python -m aivcs.cli push
python -m aivcs.cli pull
```

To install the `aivcs` command in a virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
aivcs init
```

## Storage model

Each repository contains a `.aivcs` directory. The index stores staged paths and hashes, `objects/` stores file contents by SHA-256 hash, and `commits/` stores readable JSON metadata and snapshots. The current branch is `main`.

## Run AIVCSHub

The backend uses `AIVCS_WORKSPACE` for its persistent repository workspace and MySQL for users, authentication, repository ownership, issues, and follows. Copy `.env.example` to `.env` and set real local credentials before starting the backend. The application never uses a fake authentication fallback.

Create the MySQL application user/database once as an administrator:

```sql
CREATE DATABASE aivcs_hub;
CREATE USER 'aivcs'@'localhost' IDENTIFIED BY 'your-password';
GRANT ALL PRIVILEGES ON aivcs_hub.* TO 'aivcs'@'localhost';
FLUSH PRIVILEGES;
```

Then configure `.env`:

```text
DB_HOST=127.0.0.1
DB_PORT=3306
DB_USER=aivcs
DB_PASSWORD=your-password
DB_NAME=aivcs_hub
JWT_SECRET=use-a-long-random-secret
AIVCS_WORKSPACE=./aivcs-workspace
```

The backend creates the required tables automatically on the first authenticated request.

```powershell
python -m pip install -r backend\requirements.txt
python -m uvicorn backend.app:app --reload
```

In another terminal:

```powershell
cd frontend
npm install
npm run dev
```

The frontend uses the Vite `/api` proxy and the backend API. Register and log in first. Repository creation, deletion, browsing, staging, diffs, commits, history, remote configuration, push, and pull operate on the authenticated user's persistent workspace and the shared AIVCS core.

Phase 1 remotes are local filesystem paths. Network remotes, branching/merging, authentication, issues, pull requests, and advanced AI features are intentionally outside this phase.
