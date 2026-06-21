# AGENTS.md

## Cursor Cloud specific instructions

This repo is a finance/audit SaaS MVP (审计风险识别系统) with two services. Standard install/run/test commands live in `README.md` and the root `package.json` scripts; this section only captures non-obvious caveats for cloud agents (the update script already refreshes dependencies on startup).

### Services

| Service | Dev command (run from repo root) | URL | Notes |
| --- | --- | --- | --- |
| Backend (FastAPI + uvicorn) | `source .venv/bin/activate && pnpm dev:backend` | http://127.0.0.1:8000 | Python deps live in a repo-root virtualenv at `.venv`. Health: `/health`. |
| Frontend (React + Vite, pnpm) | `pnpm dev:frontend` | http://127.0.0.1:5173 | Vite proxies `/api` and `/health` to `127.0.0.1:8000`. |

Use a tmux session for each dev server so it survives across tool calls.

### Non-obvious caveats

- Python deps are installed into a repo-root venv (`/workspace/.venv`), created with `python3 -m venv`. Activate it (`source .venv/bin/activate`) before running `pnpm dev:backend`, `pytest`, or `uvicorn`; the `pnpm dev:backend` script calls `uvicorn` directly and does not activate the venv for you.
- Backend dev port is `8000` (root `package.json` `dev:backend`), and the Vite proxy targets `8000` (`frontend/vite.config.ts`). Keep them aligned. The source of truth is `package.json` + `vite.config.ts` (some README snippets still show other ports like `8010`). A `git reset`/checkout that touches the tracked `backend/finance_audit.db` will roll the dev database back to the committed state and wipe locally-registered test users.
- Default datastore is SQLite at `backend/finance_audit.db` (committed) and a local Qdrant path at `qdrant_local_storage`. PostgreSQL/Redis/Qdrant in `docker-compose.yml` are optional; nothing in the core dev/test flow requires Docker.
- `backend/.env` only sets `SECRET_KEY`; leaving `DATABASE_URL` unset is intentional and falls back to SQLite (see `backend/app/core/config.py`).
- `bcrypt` must stay `<4.1`: `passlib 1.7.4`'s bcrypt backend-detection probe sends a >72-byte secret, which `bcrypt>=4.1` rejects with `ValueError`, breaking all password hashing/auth. This is pinned in `backend/pyproject.toml`. If auth/register tests start failing with `ValueError`, check the installed bcrypt version.
- `frontend` imports `dayjs` directly but pnpm's strict isolation hides antd's copy; `dayjs` is therefore a direct dependency in `frontend/package.json`.

### Build / test health notes

- `pnpm build:frontend` runs `tsc -b` first, so any new TypeScript type error blocks packaging (and deployment). The Vite **dev** server (`pnpm dev:frontend`) does NOT type-check, so a page can work in dev yet fail to build. Always run `pnpm build:frontend` before treating a change as deploy-ready. Past upgrades have repeatedly introduced such blockers (e.g. missing imports, `string | null` vs `string | undefined`, store methods used before they exist).
- A handful of backend tests fail due to test-code bugs / shared-SQLite test ordering (e.g. `test_lifecycle.py` references an unimported `UserLedgerAuth`; `test_me_with_token` passes in isolation but fails under full-suite ordering). The vast majority pass (≈248/255). Run focused tests in isolation when validating.
