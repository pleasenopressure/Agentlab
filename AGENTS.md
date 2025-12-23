# Repository Guidelines

## Project Structure & Module Organization
- Core code lives in `src/agentlab/`: `runtime/` (task manager & scheduling), `models/` (LLM clients like Gemini), `tools/` (builtin and registered tools), `orchestration/` (ReAct loops), `memory/`, `observability/` (otel wiring), `studio/` (dev UI hooks), `scripts/` (one-off utilities).
- Entrypoints: `app.py` exposes FastAPI routes, SSE, and WebSocket; `config.py` loads environment; `api_schemas.py` and `types.py` define request/response types.
- Config is read from `.env`; start from `.env.example` and keep `.env` untracked.

## Build, Test, and Development Commands
- conda virtual environment: `conda activate agentlab`
- Install editable deps: `python -m pip install -e .` (requires Python 3.10+).
- Run API locally: `uvicorn agentlab.app:app --reload --port 8000`.
- Health/SSE smoke: `curl.exe http://127.0.0.1:8000/health` then `curl.exe -N http://127.0.0.1:8000/session/test/events`.
- No formal build step; package metadata is in `pyproject.toml` (hatchling backend).

## Coding Style & Naming Conventions
- Follow PEP 8 with 4-space indents; favor type hints on public functions and FastAPI handlers.
- Keep async paths non-blocking; offload sync/IO to threads (see `GeminiGenAIClient` usage with `asyncio.to_thread` in `models/`).
- Name modules and files lowercase_with_underscores; classes are PascalCase; functions/vars snake_case.
- Prefer small, composable functions; document new routes and tool behaviors with concise docstrings.

## Testing Guidelines
- Pytest is the expected harness; place tests under `tests/` mirroring `src/agentlab/` (e.g., `tests/runtime/test_task_manager.py`).
- Use `python -m pytest` to run the suite; add fixtures for SSE/WebSocket event streams when applicable.
- For manual checks, hit `/health`, `/docs`, and `/session/{id}/events` while running `start_demo` or `react_chat` flows.
- Target pragmatic coverage on orchestration, tool registry behaviors, and cancellation paths.

## Commit & Pull Request Guidelines
- Git history favors short, day-tagged subjects (`Day 7: ...`) with a crisp summary; keep subjects imperative and <72 chars.
- PRs should include: problem statement, key changes, test evidence (`pytest` output or curl snippets), and any SSE/log screenshots if behavior changed.
- Link related issues/tasks; mention env or config changes explicitly.
- Avoid committing secrets; ensure `.env` stays local and `.env.example` reflects new required settings.

## Security & Configuration Tips
- Required envs: `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `LOG_LEVEL`; add new secrets to `.env.example` with comments.
- Keep FastAPI/uvicorn exposed only on localhost in dev; use `--port` override if 8000 is occupied.
- When adding tools or model clients, guard network calls with timeouts and propagate cancellations via the task manager checkpoints.
