# AIVCS

AIVCS (AI-native Version Control System) is an educational, file-backed version-control core. Phase 1 implements repository initialization, staging, SHA-256 content hashing, status, unified diffs, commits, history, and commit inspection.

## Run from the workspace

```powershell
python -m aivcs.cli init
python -m aivcs.cli add .
python -m aivcs.cli status
python -m aivcs.cli diff --staged
python -m aivcs.cli commit -m "feat: initialize project"
python -m aivcs.cli log --oneline
python -m aivcs.cli show <commit-id>
```

Create and switch branches. Branch switching rewrites the working folder from the selected commit snapshot; the `.aivcs` JSON metadata and content objects are never deleted.

```powershell
aivcs branch feature
aivcs switch feature
aivcs add .
aivcs commit -m "feat: add feature files"
aivcs switch main
aivcs branch
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

## MongoDB Atlas demo remote

The backend uses one MongoDB Atlas cluster and one `repositories` collection. Each user has one document:

```json
{
  "email": "user@example.com",
  "username": "username",
  "password": "password",
  "createdAt": "2026-09-24T12:00:00+00:00",
  "repositories": [
    {
      "repositoryId": "demo",
      "branches": [
        {
          "branchName": "main",
          "headCommitId": "abc123",
          "commits": [
            {
              "commitId": "abc123",
              "message": "initial commit",
              "timestamp": "2026-09-24T12:00:00+00:00",
              "author": "AIVCS User",
              "parent": null,
              "fileDetails": [
                {
                  "filename": "Hello.txt",
                  "fileextension": ".txt",
                  "content": "hello\n",
                  "contentHash": "sha256..."
                }
              ]
            }
          ]
        }
      ]
    }
  ]
}
```

Arrays are used for repositories, branches, commits, and file details because MongoDB field names cannot safely be used as arbitrary user-controlled map keys. `contentHash` is retained so a clone can rebuild AIVCS content objects exactly.

Start the backend with the Atlas connection string (keep the password in an environment variable rather than committing it):

```powershell
$env:MONGODB_URI = "mongodb+srv://<user>:<password>@<cluster>/<database>?retryWrites=true&w=majority"
$env:MONGODB_DATABASE = "aivcs"
python -m uvicorn backend.app:app --reload
```

Configure the CLI and push a committed repository:

```powershell
aivcs config email "user@example.com"
aivcs config username "username"
aivcs config password "password"
aivcs config backend-url "http://localhost:8000"
aivcs push main
aivcs push feature --repository demo
aivcs clone demo copied-demo
```

The backend URL is the placeholder for the deployed FastAPI service that connects to Atlas. This demo stores the password as supplied; use password hashing and HTTPS before treating it as production code.
