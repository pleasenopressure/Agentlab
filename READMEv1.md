# what is Agentlab
Project structure for Agentlab based on modern Python standards.
# Architecture
 - `src/agentlab`: Main source code
  - `runtime/`: Runtime execution engines
  - `models/`: LLM integrations
  - `tools/`: Agent tools
  - `memory/`: Memory management
  - `orchestration/`: Orchestration logic
  - `observability/`: Logging and tracing
  - `studio/`: Developer tools/UI

# Quick Start
## create a .env
```bash
# If using Gemini
export GEMINI_API_KEY="YOUR_KEY"
# Optional
export GEMINI_MODEL="gemini-2.5-flash"

```
## run a server
Terminal A
```bash
pip install fastapi uvicorn
pip install -e .
# 启动fastapi服务，--reload 表示热更新，--port 指定端口，--log-config 指定日志配置
uvicorn agentlab.app:app --port 8000 --log-config log_config.json  
```
## smoke test (SSE and ReAct)
Terminal B
```
# 启动sse事件，可以看到事件流
curl.exe -N http://127.0.0.1:8000/session/test/events
```
Terminal C: start a ReAct run
Note: PowerShell 发送 JSON 建议用 Invoke-RestMethod + ConvertTo-Json，避免 curl 引号转义问题
```bash
$json = @{
    prompt = "请等待 4 秒后告诉我现在的时间戳（可以使用工具）"
    system = "用简体中文回答"
} | ConvertTo-Json

Invoke-RestMethod -Method Post `
  -Uri "http://127.0.0.1:8000/session/test/react_chat" `
  -ContentType "application/json; charset=utf-8" `
  -Body ([System.Text.Encoding]::UTF8.GetBytes($json))
```
## Cancel a running session
```bash
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/session/test/cancel"
```
# Agent loop Explained
The ReAct loop enforces a strict **JSON-only action protocol**:

- Tool call:
    

```
{"type":"tool","tool_name":"calc","args":{"expression":"2+2"}}
```

- Final answer:
    

```
{"type":"final","final":"..."}
```

Runtime behavior:

1. Build a fresh system prompt (tool list + constraints) for each run
    
2. LLM generates an action JSON
    
3. If action is `tool`, execute via ToolRunner (timeout/retry/cancel-safe) and append Observation
    
4. If action is `final`, stream the final answer via SSE (`final_delta`)

# liminations
- This is a minimal agent service skeleton; not production hardened yet.
    
- Session history is stored locally (file-based); no database / multi-node consistency.
    
- Tool security is allowlist-based; advanced sandboxing is not implemented.
    
- Eval harness is not included in v0.1 (planned in roadmap).
    
- Some LLM SDK tool/function-calling behaviors are model-dependent; AgentLab uses JSON-only action to stay model-agnostic.