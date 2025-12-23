# Agentlab

Project structure for Agentlab based on modern Python standards.

## Structure

- `src/agentlab`: Main source code
  - `runtime/`: Runtime execution engines
  - `models/`: LLM integrations
  - `tools/`: Agent tools
  - `memory/`: Memory management
  - `orchestration/`: Orchestration logic
  - `observability/`: Logging and tracing
  - `studio/`: Developer tools/UI


## Run
```bash
pip install fastapi uvicorn
pip install -e .
# 启动fastapi服务，--reload 表示热更新，--port 指定端口
uvicorn agentlab.app:app --port 8000 --log-config log_config.json  
# 启动sse事件，可以看到事件流
curl.exe -N http://127.0.0.1:8000/session/test/events

## Day 1 验收标准（你对照打勾）
- [√] `uvicorn agentlab.app:app --reload` 启动无报错  
- [√] `GET /health` 返回 `ok: true`  
- [√] 能打开 `/docs` 看见自动生成 API 文档  
- [√] `.env` 没有提交，`.env.example` 已存在  
- [√] README 写清楚启动方式

---

## Day 1 常见坑（我提前告诉你怎么秒解）
1) **ModuleNotFoundError: agentlab**  
   - 大概率你没 `pip install -e .`，或你不在项目根目录运行  
   - 解决：在根目录执行 `pip install -e .` 再启动

2) **8000 端口被占用**  
   - 解决：`--port 8001`

3) **Windows 激活脚本权限**（PowerShell）  
   - 解决：用管理员 PowerShell 执行一次：`Set-ExecutionPolicy RemoteSigned`

## notes
gemini_genai.py generate函数中我在异步接口里用 asyncio.to_thread 把第三方同步阻塞 SDK 的调用 offload 到线程池执行，从而避免阻塞 event loop，保证 FastAPI 同时处理多个会话、SSE/WS 推送、取消请求等实时性
如果外部取消了这个协程（例如 task.cancel()）：
- 协程会收到 CancelledError
- 但线程里的 _call() 通常还会继续跑到结束（因为普通线程函数无法被 asyncio 强制杀掉）
- 当线程不断创建就会出问题，线程池耗尽
- 解决：加 timeout，防止线程无限卡住
- 改为return await asyncio.wait_for(asyncio.to_thread(_call), timeout=30)


## Day 5 踩坑 & 经验（Pitfalls）

PowerShell 发送 JSON 建议用 Invoke-RestMethod + ConvertTo-Json，避免 curl 引号转义问题

取消必须在执行路径中有 checkpoint，否则 cancel 没效果

sync 工具必须 to_thread，否则会阻塞 event loop（SSE/WS 会卡）

## Day 6
Day6 实现了基于 FastAPI + SSE 的 ReAct Agent Loop：LLM 输出结构化 tool call → ToolRunner 执行并回灌 observation → LLM 生成 final；支持 max_steps 护栏、事件级可观测与任务取消，并解决了 Windows 客户端编码导致的输入乱码问题。
踩坑：
当输入prompt中存在中文时，Windows PowerShell 里 Invoke-RestMethod -Body 可能用非 UTF-8 编码发出字符串，FastAPI 按 UTF-8 解码 JSON → 服务端收到的是乱码（你在 react_user_input 看到 ???）
解决：
```
$json = @{
    prompt = "请等待 4 秒后告诉我现在的时间戳（可以使用工具）"
    system = "用简体中文回答"
} | ConvertTo-Json

Invoke-RestMethod -Method Post `
  -Uri "http://127.0.0.1:8000/session/newtest/react_chat" `
  -ContentType "application/json; charset=utf-8" `
  -Body ([System.Text.Encoding]::UTF8.GetBytes($json))
```

# Day7 — SSE 输出标准化为 JSON（UTF-8）

> 目标：把 SSE 事件流的 `data:` 从 Python dict 的字符串（单引号、中文易乱码）升级为 **标准 JSON（UTF-8）**，让终端/日志/前端都能直接解析与展示。

## 1. 背景与问题

### 1.1 旧输出的问题
之前 SSE `data:` 直接输出 Python `dict`，最终表现为 Python `repr`：

- 单引号（不是 JSON）
- 中文在 Windows 控制台或跨编码链路中容易显示成 `???`
- 前端无法直接 `JSON.parse()`，必须做不可靠的字符串处理

示例（旧）：

```text
data: {'type': 'react_user_input', 'prompt': '???', 'system': '???'}
```

---

## 2. 解决方案

### 2.1 只改 SSE endpoint，EventBus 不改
`EventBus` 的职责是传递结构化事件（Python dict）。
“是否输出标准 JSON”应该在 **SSE 输出层**处理：把 dict 序列化为 JSON 字符串再输出。

核心改动：在 SSE endpoint 中使用 `json.dumps(..., ensure_ascii=False)`。

### 2.2 参考实现（SSE endpoint）
> 说明：下面展示的是关键逻辑；按你的项目实际文件组织放到对应的 `app.py`/路由文件中。

```python
import json
import time
from sse_starlette.sse import EventSourceResponse

@app.get("/session/{session_id}/events")
async def sse_events(session_id: str):
    async def gen():
        async for ev in bus.subscribe(session_id):
            yield {
                "id": str(time.time_ns()),
                "event": "runtime",
                "data": json.dumps(ev, ensure_ascii=False),
            }

    return EventSourceResponse(gen())
```

要点：
- `ensure_ascii=False`：中文直接输出（否则会变成 `\u4e2d\u6587`）
- `id=time.time_ns()`：每条事件唯一，利于重连语义与排查问题

---

## 3. 测试方法（Windows / PowerShell）

### 3.1 订阅 SSE（终端 A）
```powershell
curl.exe -N "http://127.0.0.1:8000/session/test7/events"
```

### 3.2 触发 ReAct（终端 B）
为避免 PowerShell 发送中文 JSON 时的隐式编码问题，使用 UTF-8 bytes 发送请求体：

```powershell
$payload = @{ prompt = "请计算 (19.5 + 2.3) * 4 并给出结果"; system = "用简体中文回答" } | ConvertTo-Json
$bytes = [System.Text.Encoding]::UTF8.GetBytes($payload)

Invoke-RestMethod -Method Post `
  -Uri "http://127.0.0.1:8000/session/test7/react_chat" `
  -ContentType "application/json; charset=utf-8" `
  -Body $bytes
```

---

## 4. 验证结果（SSE 证据）

SSE 输出已变为标准 JSON，且中文可读，例如：

- `react_user_input`：
```text
data: {"type":"react_user_input","prompt":"请计算 (19.5 + 2.3) * 4 并给出结果","system":"用简体中文回答"}
```

- ReAct 链路仍正常：
  - `react_model_raw`（tool）
  - `tool_start` → `tool_end`
  - `react_observation`
  - `react_model_raw`（final）
  - `final` → `run_done`

最终输出示例：
```text
data: {"type":"final","text":"计算结果是 87.2。"}
```

---

## 5. 记录与改进点

### 5.2 终端显示仍乱码的处理
若 SSE 仍显示中文异常，可在订阅 SSE 的 PowerShell 窗口执行：

```powershell
chcp 65001
$OutputEncoding = [Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
```

---

## 6. 本日结论

- SSE `data` 统一输出为 JSON 字符串，是后续 Studio/UI/日志/评估对接的最佳实践。
- 中文与结构化数据的可观测性显著提升：`react_user_input` 能直接确认服务端收到的 prompt/system 是否正确。
