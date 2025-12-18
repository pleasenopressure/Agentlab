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
uvicorn agentlab.app:app --reload --port 8000

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

