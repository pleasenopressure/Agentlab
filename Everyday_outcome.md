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

# Day 8 — OpenTelemetry（OTel）可观测性接入与 Trace ↔ SSE 对齐（总结笔记）

> 项目：AgentLab（FastAPI + SSE 事件流 + ReAct + Tools）  
> 目标：把“请求 → agent.run → react.step → tool.run”这条链路做成可观测（Tracing），并把 **trace_id / span_id** 关联到 **SSE runtime events**，便于定位问题与性能分析。

---

## 1. Day 8 目标与范围

本日聚焦 **Observability / OTel Tracing**：

- 理解并掌握：Trace / Span / 埋点（Instrumentation）、Collector、可视化平台（Jaeger/Tempo/Langfuse/Arize 等）
- 在项目中接入 OTel：给关键执行路径打 Span（HTTP、agent.run、react.step、tool.run）
- 解决调试痛点：
  - FastAPI 终端 trace 太“刷屏”
  - SSE 里看不到 trace_id/span_id，无法对齐“事件”和“链路”
- 产出：
  - traces.jsonl（或 traces.json）文件落盘
  - SSE 输出携带 trace_id/span_id
  - 用 trace_id 抽取并打印树状结构的辅助脚本（trace_tree.py）

---

## 2. 本日遇到的主要问题（按发生顺序）

### 2.1 终端 trace 输出太杂乱，难以阅读
**现象**
- FastAPI/uvicorn 终端输出大量 JSON（尤其 SSE 长连接 `/events`）
- spans 中大量 `http.response.body` / `http send` 记录把关键业务 span 淹没

**原因（关键点）**
- `ConsoleSpanExporter()` 会把每个 span 直接打印到终端
- SSE 是长连接，会持续 flush/心跳，触发非常多 asgi 事件 span

**解决**
- 把 exporter 从 Console 改为 **写文件 JSONL**（每行一个 span）
- 后续可选：过滤掉 `/events` 路由产生的噪声 span（在 exporter 层过滤）

---

### 2.2 ImportError：cannot import name 'tracer'（otel.py 中没有 tracer）
**现象**
- `from agentlab.observability.otel import tracer` 报错：`ImportError: cannot import name 'tracer'`

**原因**
- `otel.py` 里只 `setup_otel()`，但没有显式 `tracer = trace.get_tracer(__name__)`
- 代码在其它模块直接 import tracer，但 otel.py 没提供该符号

**解决**
- 在 `otel.py`（或 app.py）中补齐：
  - `tracer = trace.get_tracer(__name__)`
- 或统一改成在使用处调用：`trace.get_tracer(__name__)`（避免跨文件 import tracer 的耦合）

---

### 2.3 SSE 中看不到 trace_id/span_id（但 FastAPI 终端能看到）
**现象**
- FastAPI 终端能看到 OTel spans（trace_id/span_id）
- SSE runtime events 却没有 `trace_id/span_id` 字段，无法对齐

**原因**
- OTel trace 是 span 体系；SSE runtime event 是业务事件 dict
- 需要在发布事件时将 “当前活跃 span context” 附加到事件上

**解决**
- 在 `EventBus.publish()` 里对 event 做 `_attach_trace(event)`：
  - `trace.get_current_span()` → 取 `trace_id/span_id` → 写进 event copy
- 同时确认 **context 传播**：后台任务（TaskManager create_task）需要从请求上下文 attach 进去  
  - 在 job 内使用 `attach(parent_ctx)` / `detach(token)`，让后台协程仍处于同一 trace

客户端                  FastAPI(请求处理)                        后台任务(TaskManager)
  |  POST /react_chat          |                                         |
  |--------------------------->|                                         |
  |                            | ① 进入 HTTP span(uvicorn/otel 自动)     |
  |                            |    current_span = HTTP span             |
  |                            |                                         |
  |                            | ② parent_ctx = get_current()            |
  |                            |    (把“当前上下文”保存下来)              |
  |                            |                                         |
  |                            | ③ tm.start(session_id, job)             |
  |                            |---------------------------------------->|  (create_task)
  |                            |                                         | ④ attach(parent_ctx)
  |                            |                                         |    current_span 恢复为 HTTP span
  |                            |                                         |    (关键：让后台也“继承”这条链路)
  |                            |                                         |
  |                            |                                         | ⑤ start agent.run span
  |                            |                                         |    current_span = agent.run
  |                            |                                         |
  |                            |                                         | ⑥ bus.publish(event)
  |                            |                                         |    _attach_trace() 读取 current_span
  |                            |                                         |    → 把 trace_id/span_id 塞进 event
  |                            |                                         |    → 进队列
  |                            |                                         |
  |                            |                                         | ⑦ SSE /events 订阅从队列取出 event
  |                            |                                         |    → 推给 curl 终端
  |                            |                                         |
  |                            |                                         | ⑧ detach() 清理上下文
  |                            |                                         |
  |  200 {"result":"started"}  |                                         |
  |<---------------------------|                                         |

A. _attach_trace(event) 到底在做什么？

它做的只有一件事：
span = trace.get_current_span() —— 取当前上下文里的 span
ctx = span.get_span_context() —— 取 span 的 trace_id/span_id
把 trace_id/span_id 写进 event 的 copy 里，返回
所以它依赖一个前提：调用 publish 的那一刻，当前上下文里必须有活跃 span。
B. 为什么必须 attach(parent_ctx)？
因为你是这样启动后台任务的：
HTTP 请求进来 → FastAPI handler 在一个上下文里（有 HTTP span）
tm.start() → asyncio.create_task() 创建后台任务（新的 Task）
新的 Task 默认可能拿不到原来请求的上下文（尤其是你跨线程/跨 Task/使用 to_thread 等时更明显）。
结果就是：
你在后台 bus.publish() 时 trace.get_current_span() 可能是 无效 span
_attach_trace() 读不到 trace_id/span_id → SSE 事件就不会带 id
attach(parent_ctx) 的意义就是：
把“请求时的上下文（含 trace 信息）”显式带到后台任务里，让后台任务继续属于同一条 trace。
C. 为什么要 detach(token_handle)？
attach() 像“把某个上下文压栈”，detach() 像“出栈恢复”。
如果你不 detach：
这个后台 Task 结束后可能还残留旧上下文
下一个任务可能“串台”，trace 混乱（最难排查的那种）
---

### 2.4 SSE “只有 see_connection，没有后续事件” / logger 也看不到
**现象**
- `curl -N /session/test/events` 只能看到连接事件
- `EventBus.publish()` 中的 `logger.info(...)` 不出现在 `agentlab.log`
- `subscribe()` 的 “consumed” 日志也没有

**原因（排查要点）**
- 订阅 `/events` 本身不会产生业务事件；需要另一个终端触发 `POST /react_chat`
- `subscribe()` 中 `logger.info` 写在 `yield` 后面，很多情况下不会执行到
- `_attach_trace()` 可能在某些路径未 return（返回 None）导致队列中出现 None
- logging 配置未把 `agentlab.events` logger 写入文件（或仍用 print、未使用 uvicorn log-config）

1) yield 在生成器里到底做了什么？

普通函数：return 一次性结束。

生成器函数（有 yield）：每次执行到 yield：

暂停函数

把一个值“吐”给外面

保存当前执行位置

等外面“下一次要值”时，从 yield 的下一行继续跑

异步生成器（async def ... + yield）同理，只是“下一次要值”发生在 async for 的下一轮。

2) 用最小例子理解“yield 后面为什么可能不执行”
def gen():
    print("A")
    yield 1
    print("B")
    yield 2
    print("C")


运行：

g = gen()
next(g)   # 打印 A，返回 1
# 这时候 B 还没执行，因为函数暂停在 yield 1 那里

next(g)   # 打印 B，返回 2
next(g)   # 打印 C，然后 StopIteration


结论：yield 后面的代码要等下一次 next() 才会执行。

3) 迁移到你的 subscribe()（异步生成器）

你现在的模式是：

async def subscribe(self, session_id):
    q = self.get_queue(session_id)
    while True:
        yield await q.get()
        logger.info("consumed")


这里发生了什么：

ev = await q.get() 拿到事件

yield ev 把事件交给 SSE 的 async for（EventSourceResponse）

生成器暂停在 yield 这一行

只有当 SSE 框架“继续拉下一条事件”（下一次循环）时，才会回到 logger.info("consumed")

为什么很多时候你看不到这条 log？

因为在 SSE 场景里，经常出现：

客户端断开（curl 结束 / 网络断开）

SSE 框架停止迭代（不再 async for）

生成器被取消（CancelledError）

这时生成器可能永远不会恢复到 yield 后面，所以 logger.info 就不会执行。

4) 正确写法：把 log 放在 yield 之前（你想要“消费就记录”）

你要表达的是：“我从队列取出来了，马上记录”，那就写成：

async def subscribe(self, session_id):
    q = self.get_queue(session_id)
    while True:
        ev = await q.get()
        logger.info(f"consumed by subscriber: {session_id} ev={ev.get('type')}")
        yield ev


这样：

只要取到了事件，就一定会 log

不依赖下一次迭代是否发生

5) 你可能还关心：yield 前后分别代表什么语义？
yield 前适合做什么？

“准备输出之前的事情”

取数据、校验、记录日志、打点、做转换

yield 后适合做什么？

“这一条已经成功交给消费者之后才做的事情”

比如你真的想确认“消费者已经请求下一条了”才算“上一条完成”，才放到 yield 后

但注意：SSE/网络流不保证真正送达，yield 只是把数据交给框架，不能严格代表“客户端已收到”。


**解决**
- 先取再 log 再 yield：
  - `ev = await q.get(); logger.info(...); yield ev`
- 保证 `_attach_trace()` 任意路径都返回 dict（不要返回 None）
- 统一使用 `uvicorn --log-config log_config.json` 把应用日志落盘到 `logs/agentlab.log`
- 明确调试路径：
  1) 开 SSE 订阅终端
  2) 另开终端 POST /react_chat 触发 publish

---

## 3. 本日完成的事情（落地成果）

### 3.1 完成 OTel 初始化（setup_otel）与落盘 trace 文件
- 将默认 `ConsoleSpanExporter`（刷屏）替换为 **JSONL 文件 exporter**
- 产物：`logs/traces.jsonl`（每行一条 span，便于搜索/过滤/脚本处理）
- 可选：若设置 `OTEL_EXPORTER_OTLP_ENDPOINT`，仍可走 OTLP 导出

> 备注：调试期更适合“写文件 + 过滤噪声”，而不是采样（sampling 可能丢掉关键 trace）。

---

### 3.2 把 trace_id/span_id 附加到 SSE runtime events
- 在 `EventBus.publish()` 内：`await q.put(self._attach_trace(event))`
- SSE 端最终输出效果：每条业务 event dict 携带
  - `"trace_id": "...", "span_id": "..."`
- 价值：可以把 SSE 的每个 runtime event 精确对应到某个 span（更快定位 “哪一步” 卡住或异常）。

---

### 3.3 验证 trace 与 SSE 的对应关系（对齐方法）
- 使用 SSE 输出的 `trace_id`：在 `traces.jsonl` 中筛选同 trace 的所有 spans
- 用 `span_id` 在 trace 文件中精确查某个 span
- 用 `parent_span_id` 串起树结构：
  - HTTP POST /react_chat（root）
    - agent.run
      - react.step#1
        - tool.run sleep
      - react.step#2
        - tool.run now
      - react.step#3
- 对齐耗时：
  - trace 的 `(end-start)/1e6` ≈ SSE 中 `duration_ms`（例如 sleep 约 4013ms）

---

### 3.4 产出辅助脚本：按 trace_id 打印树状链路（trace_tree.py）
- 输入 `trace_id`，输出树结构 + 每个 span 耗时（ms）+ step/tool 信息
- 用于快速从海量 spans 中抽出“本次请求”的关键链路，替代肉眼看 JSONL。

---

## 4. 本日关键知识点（简明版）

- **Tracer**：创建 span 的“句柄/工具对象”（不会每次请求都新建）
- **Trace**：一次请求/一次任务的整条链路（一个 trace_id）
- **Span**：链路中的一个步骤节点（span_id），通过 parent_span_id 构成树
- **埋点/Instrumentation**：在关键代码处创建 span、记录属性、异常、耗时
- **SSE**：长连接流式推送，容易产生大量 http.response.body 类 spans（噪声来源）
- **对齐思路**：在发布业务事件时附加当前 span 的 trace_id/span_id → 事件与链路可互相跳转

---

## 5. 后续建议（下一步）

1. **过滤噪声 spans（强烈推荐）**
   - 在 exporter 中丢弃 `/events` 路由产生的 `http.response.body` 等 spans
2. **把 ERROR 变得可读**
   - 在捕获异常处：`span.record_exception(e)` + `span.set_status(ERROR)`
3. **统一日志落盘**
   - 全部 print → logging；uvicorn/fastapi 统一写入 `logs/agentlab.log`
4. **接入可视化后端（可选）**
   - 本地：Jaeger / Tempo（通过 OTLP 导出）
   - LLM 专用：Langfuse / Arize（对 prompt、tool、cost 更友好）

---

## 6. 文件与命令（备忘）

- trace 文件：`logs/traces.jsonl`
- 应用日志：`logs/agentlab.log`
- 启动（带日志配置）：
  - `uvicorn agentlab.app:app --port 8000 --log-config log_config.json`
- SSE 订阅：
  - `curl.exe -N http://127.0.0.1:8000/session/test/events`
- 触发请求：
  - `Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/session/test/react_chat" -ContentType "application/json" -Body (@{prompt="...";system="..."} | ConvertTo-Json)`
