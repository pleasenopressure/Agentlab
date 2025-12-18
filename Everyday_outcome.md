Day 3:
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
