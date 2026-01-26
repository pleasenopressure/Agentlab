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

## Storage
- Session storage is handled by `FileSessionStore` in `runtime/storage.py`.
- History is stored as a list of messages in the session store.
- History is loaded from the session store in `app.py`.

## Project Structure

e:\Agentlab
├─ .env                     # 运行时环境变量（实际使用）
├─ .env.example             # 环境变量示例模板
├─ .gitignore               # Git 忽略规则
├─ AGENTS.md                # 项目指南、结构说明及最佳实践
├─ Everyday_outcome.md      # 每日工作/实验结果记录
├─ README.md                # 项目概览、安装与使用说明
├─ log_config.json          # 日志系统的 JSON 配置
├─ pyproject.toml           # 包元数据、依赖与构建配置
├─ logs                     # 运行时日志目录
│   └─ (日志文件…)         
└─ src
    └─ agentlab
        ├─ __init__.py                 # 包初始化文件
        ├─ api_schemas.py              # FastAPI 请求/响应的 Pydantic 模型
        ├─ app.py                      # FastAPI 应用入口（路由、SSE、WebSocket）
        ├─ config.py                   # 配置加载（读取 .env、默认值等）
        ├─ memory                      # （当前为空）用于实现记忆/状态持久化的模块
        ├─ models
        │   ├─ __pycache__             # 编译后的字节码缓存
        │   ├─ base.py                 # 所有模型客户端的抽象基类
        │   ├─ gemini_genai.py         # Gemini LLM 客户端实现（同步/异步）
        │   └─ mock_client.py          # 用于测试的 Mock LLM 客户端
        ├─ observability
        │   ├─ __pycache__
        │   └─ otel.py                 # OpenTelemetry 集成，提供链路追踪与度量
        ├─ orchestration
        │   ├─ __pycache__
        │   └─ react_loop.py           # ReAct 循环实现（工具调用 + 思考）
        ├─ runtime
        │   ├─ __pycache__
        │   ├─ cancel.py               # 任务取消与超时处理工具
        │   ├─ events.py               # 运行时事件定义（SSE、WebSocket 等）
        │   ├─ storage.py              # 运行时数据存储抽象（FileSessionStore 等）
        │   └─ task_manager.py         # 任务调度、会话管理与协程工厂
        ├─ scripts
        │   ├─ __pycache__
        │   └─ day3_smoke.py           # 示例脚本：Smoke 测试 Gemini 客户端
        ├─ studio                       # 开发 UI 钩子（调试/可视化），当前为空
        ├─ tools
        │   ├─ __pycache__
        │   ├─ builtins.py             # 内置工具实现（calc、sleep、now 等）
        │   ├─ registry.py             # 工具注册中心与规范定义
        │   └─ trace_tree.py           # 工具调用追踪树的可视化/序列化
        └─ types.py                     # 项目共享的类型定义（Enum、TypedDict 等）