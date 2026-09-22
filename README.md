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

To install the `aivcs` command in a virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
aivcs init
```

## Storage model

Each repository contains a `.aivcs` directory. The index stores staged paths and hashes, `objects/` stores file contents by SHA-256 hash, and `commits/` stores readable JSON metadata and snapshots. The current branch is `main`.

AI commit messages, the Flask API, SQLite database, and React frontend are planned for later phases.
