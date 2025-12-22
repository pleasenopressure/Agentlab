# Day 3:
下面是你 **Day3（模型接入层：Gemini API）** 这一天真正学到/落地的知识点总结（按 JD 关键词对齐，都是你今天已经“写进代码、跑通终端”的）。

---

## Day3 核心目标回顾

把“上层智能体/Runtime”与“底层模型 SDK”解耦：
**同一套 Agent Runtime 代码，能无缝切换不同 LLM（今天是 Gemini）**，并且同时支持：

* 非流式：一次性拿完整回答
* 流式：分段/增量输出（chunk/token）

---

## 1) 统一 LLM 抽象层：`LLMClient`

你把模型调用统一成两个能力：

* `generate(messages) -> str`：非流式
* `stream(messages) -> AsyncIterator[str]`：流式

意义：

* 上层（ReAct、Pipeline、LangGraph、工具调用）只依赖接口，不依赖 SDK；
* 未来换 OpenAI / Claude / Qwen，只需要实现同样的 Client。

---

## 2) 消息协议与“角色映射”

你今天解决了一个关键工程点：**不同厂商的 message 结构不一样**，要做“适配层”。

典型处理：

* `system`：Gemini 推荐用 `system_instruction` 放进 config
* `assistant`：Gemini 侧对应 `model`
* `user`：保持 `user`

这就是你后面做多 Agent 消息传递、memory、tool call 的“协议基座”。

---

## 3) Gemini SDK 的两条调用路径（你已跑通）

* 非流式：`client.models.generate_content(...)`
* 流式：`client.models.generate_content_stream(...)` 逐 chunk 读 `chunk.text`

你还实践了：**流式不一定逐 token，而是逐 chunk**（一段段文本增量）。

---

## 4) 认证机制与环境变量（你踩坑并修复了）

你遇到并解决了典型问题：

* `genai.Client()` 初始化时没有拿到认证信息 → 报 `Missing key inputs argument`
* 修复方式：显式从 `GEMINI_API_KEY / GOOGLE_API_KEY` 读取并传入 `genai.Client(api_key=...)`

同时你也理解了 Windows PowerShell 的关键点：

* `$env:XXX="..."` 只对当前终端会话生效
* `setx` 写入后需要重开终端才生效

---

## 5) 异步架构里“同步 SDK”的正确用法

Gemini 的 streaming 接口在 Python SDK 里是**同步迭代**（阻塞式 `for chunk in resp_stream`），但你的 Agent Runtime 是 **asyncio**。

你采用了工程上常见的桥接方式：

* 在后台线程 `run_in_executor` 执行同步 streaming
* 通过 `asyncio.Queue` 把 chunk 送回 async 世界
* 主协程 `async for` 方式消费输出

这一步非常关键：后续你接工具调用、可观测性、并发调度都靠这个模式。

---

## 6) 503 Overloaded：云模型的“临时容量失败”与工程化处理

你实际遇到了云端常见错误：

* `503 UNAVAILABLE: The model is overloaded`
这类错误的含义是：服务端暂时没有足够资源来处理你的请求（不是你代码写错，也不是 key 错）。

常见原因（云端侧）：

当前区域/模型实例 并发太高（流量尖峰）

服务端做了 限流/排队保护

临时维护或后端依赖抖动（较少见）

并完成了工程补齐：

* 为流式增加 **指数退避重试**
* 将后台线程异常通过队列传回主协程，避免 “Future exception was never retrieved”
* 最终做到：失败也能“可控地报错”，而不是莫名其妙在后台炸

这就是 JD 里“可靠性/重试/异常治理”的雏形。

---

## 7) 输出长度/资源控制意识

你在 config 里加了类似 `max_output_tokens` 的限制，这体现了：

* 降低过载概率
* 控制成本与延迟
* 为后续 evaluation（耗时、token）打基础

---

## 8) Day3 的最终成果（可验收）

你今天已经具备了一个可复用的“模型接入层”：

* ✅ Mock LLM（离线开发）
* ✅ Gemini 非流式 generate
* ✅ Gemini 流式 stream（带错误治理/重试）
* ✅ smoke test 跑通（终端验证）

---

如果你愿意，我可以把 Day3 的内容整理成一段**简历可写点 + README 小节**（非常短但很“工程味”），直接复制进你的项目文档里。

# Day 4
事件流（Event Stream）的概念与用途
你把一次任务运行过程拆成连续事件（run_start / llm_start / llm_delta / llm_done / run_done），实现“运行过程直播”，而不是只拿最终结果。

SSE（Server-Sent Events）如何把事件流推给客户端
你用 GET /session/{id}/events 建立长连接，后端通过 yield 持续推送事件；客户端用 curl.exe -N 就能实时看到输出。

生产者-消费者模型在异步系统里的落地
后台任务是“生产者”不断 publish(event)；SSE 订阅端是“消费者”不断 subscribe() + q.get()，这就是典型的 asyncio Queue 模式。

EventBus 的最小实现（按 session 隔离）
events.py 用 session_id -> asyncio.Queue 把不同会话的事件分开，避免串线；publish 负责入队，subscribe 负责持续出队。

把 LLM 的流式输出接入你自己的 Runtime
你成功实现了：Gemini 的 streaming chunk → 你自己的 llm_delta 事件 → SSE 推送 → 终端实时显示，等价于“打字机效果”。

用 TaskManager 的取消机制实现 mid-stream cancel（steering 基础）
你把 token.checkpoint() 放在流式循环内，实现“边生成边检查取消”；这样 /cancel 能尽快停止任务，并在事件流里体现为 cancel_called / cancelled。

SSE 心跳（ping）是什么
你看到 : ping - ... 这种行，理解它是保持连接的心跳注释，不是业务事件，不影响你的数据流。

模型输出不稳定（语言漂移）是“提示工程/约束”的问题，不是流式问题
你观察到“要求中文但输出韩文”，学会定位：事件流链路是对的，问题在模型遵循指令的不确定性；可以通过更强的用户侧约束/格式约束来提升稳定性。

# Day5 — 工具体系（Tooling System）：Registry + Runner + 可观测 + 可取消

> 目标：把“工具调用”从随手写函数，升级为 **可注册、可治理、可观测、可取消** 的子系统，为后续 ReAct / 多 Agent / MCP 打基础。

---

## 1. Day5 交付标准（Done Checklist）

- [x] 工具注册中心 `ToolRegistry`：注册/获取/列出工具
- [x] 工具描述 `ToolSpec`：name/description/input_schema/timeout/retry/is_async/func
- [x] 工具执行器 `ToolRunner`：
  - [x] 支持 sync/async 工具
  - [x] 超时 `timeout`（`asyncio.wait_for`）
  - [x] 重试 `retry`（指数退避 + jitter）
  - [x] 用户中断（`token.checkpoint()`）
  - [x] 事件流可观测（tool_start/tool_end/tool_error/tool_cancelled）
- [x] API：
  - [x] `GET /tools`：列出工具元数据
  - [x] `POST /session/{id}/tool/{name}`：运行工具（后台 task）
- [x] SSE 可见：订阅 `/session/{id}/events` 可实时看到工具执行过程

---

## 2. 为什么要做工具体系（Why Tooling System）

### 2.1 如果没有工具体系，会怎样？
- 工具调用散落在各处（`requests.get()`、`time.sleep()`、DB query…）
- 无统一治理：超时、重试、异常格式、日志、取消都要每处手写
- 无可观测：UI/调试只能“猜”卡在哪里
- 无法让 LLM 稳定调用：LLM 需要 “工具清单 + 参数 schema + 统一返回格式”

### 2.2 Day5 解决的核心痛点
- **统一入口**：所有工具必须先注册
- **统一执行**：所有工具都走 ToolRunner（timeout/retry/cancel/事件）
- **统一观测**：每次工具运行都有 start/end/error 事件
- **可扩展**：后面接 MCP、HTTP 工具、外部服务都能复用同一套 Runner

---

## 3. 总体架构（How it works）

### 3.1 组件关系
- `ToolRegistry`：存所有工具（name → ToolSpec）
- `ToolSpec`：单个工具的“元数据 + 执行函数”
- `ToolRunner`：负责“治理式执行”（timeout/retry/cancel + 事件上报）
- `TaskManager`：负责后台任务生命周期、cancel、status
- `EventBus`：负责事件流（SSE/WS）发布与订阅

### 3.2 运行链路（以调用 calc 为例）
1. `POST /session/test/tool/calc` → FastAPI 启动后台 job（`tm.start`）
2. job 调用 `tool_runner.run(...)`
3. ToolRunner：
   - publish `tool_start`
   - 执行工具（sync→to_thread / async→await）
   - timeout / retry / cancel checkpoint
   - publish `tool_end` 或 `tool_error`/`tool_cancelled`
4. SSE 订阅端实时收到事件并展示

---

## 4. 关键设计点与代码要点（重点）

### 4.1 `ToolSpec`：工具的“完整定义”
包含：
- `name/description`：给 LLM/UI 看
- `input_schema`：参数结构（JSON schema 简化版）
- `func`：实际执行函数
- `is_async`：是否 async
- `timeout_s`：超时治理
- `retry`：重试策略（max_retries/backoff/jitter）

> 设计意义：把“工具的能力描述”和“执行约束”绑定在一起，后续做 tool-call、eval、文档生成都很顺。

---

### 4.2 sync/async 工具的统一执行：`asyncio.to_thread`
- async 工具：`await spec.func(args)`
- sync 工具：`await asyncio.to_thread(spec.func, args)`

> 核心意义：避免同步工具阻塞 event loop（否则 SSE/WS 会卡死、并发请求会卡死）。

---

### 4.3 超时治理：`asyncio.wait_for`
```python
result = await asyncio.wait_for(call, timeout=spec.timeout_s)


## Day6 目标

把 Day5 的工具体系真正接进 Agent 控制流，做出一个最小可用的 **ReAct 闭环**：

> **LLM 规划（选择工具）→ 执行工具 → Observation 回灌 → LLM 输出最终答案**

并且全程 **可观测（SSE 事件流）+ 可取消（TaskManager token）**。

---

## 你完成的核心功能

### 1) ReAct Loop（多步控制流）

- 引入 `max_steps`（例如 6）防止模型死循环
    
- 每一步都有：
    
    - `react_step_start`
        
    - `react_model_raw`（模型原始输出）
        
    - （可能）工具调用与 observation
        
    - 直到 `final`
        

你跑通的例子非常典型：

- Step1：模型输出 tool call JSON → 选择 `calc`
    
- Step2：模型输出 final JSON → 给出答案
    
---

### 2) 动作协议（JSON action format）

你没有直接用 Gemini 的原生 tool-calling，而是先用最稳定、可移植的 **JSON 协议**：

- 工具调用：
    
    `{"type":"tool","tool_name":"calc","args":{"expression":"(19.5 + 2.3) * 4"}}`
    
- 最终回答：
    
    `{"type":"final","final":"87.2"}`
    

优点：

- 任何模型都能用同一套 loop
    
- 易调试：解析失败可以直接看 `react_model_raw`
    

---

### 3) 工具执行真正进入 agent loop

当模型选择工具后，你把它交给 Day5 的 `ToolRunner` 执行：

- `tool_start`
    
- `tool_end` / `tool_error`
    
- 结果变成 Observation，再喂回 LLM
    

你 SSE 中的关键证据：

- `tool_start` → `tool_end`
    
- `react_observation`（里面带 `value: 87.2`）
    

---

### 4) 观测性（Observability）完整闭环

你通过 EventBus + SSE，把整个 ReAct 过程“直播”出来：

- 模型的决策（`react_model_raw`）
    
- 工具的开始/结束（`tool_start/tool_end`）
    
- 回灌内容（`react_observation`）
    
- 最终输出（`final`）
    

这为后续 Studio/调试/评估奠定了基础。

---

### 5) 可中断（Cancellation / Steering 基础）

你在循环关键点放了：

- `await token.checkpoint()`
    

意味着：

- 用户调用 `/cancel` 能在下一次 checkpoint 处中断 ReAct（包括工具执行前/下一步推理前）。
    

---

## Day6 你踩到的关键坑与修复思路

### 1) “为什么没看到模型输出？”

你看到的模型输出主要以两种事件体现：

- `react_model_raw`：模型原始 JSON 输出
    
- `final`：最终答案
    

因为 Day6 用的是 `llm.generate()`（一次性生成），还没有做 Day4 那种 `llm_delta` 流式输出。

---

### 2) “为什么我想调用 sleep，却调用了 calc？”

你定位到了根因之一：**输入在客户端就乱码了**，导致模型无法理解“等待”意图。

- Windows PowerShell 里 `Invoke-RestMethod -Body` 可能用非 UTF-8 编码发出字符串
    
- FastAPI 按 UTF-8 解码 JSON → 服务端收到的是乱码（你在 `react_user_input` 看到 `???`）
    

解决方法（你已经掌握方向）：

- 用 UTF-8 字节发送 JSON（最稳）
    
- 或调整终端/脚本编码，确保请求体是 UTF-8
    

---

## 你 Day6 最重要的“能力增长”

- 你从“能流式输出”升级为“能做 agent 控制流”：  
    **模型不只是回答，而是能“选择工具、执行工具、利用工具结果再回答”。**
    
- 你把工具执行从“函数调用”提升为“可治理动作”（timeout/retry/cancel/事件）。
    
- 你做出了一个可调试的 ReAct 原型：任何一步出问题都能在 SSE 里定位。