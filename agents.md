# 下一阶段计划：本地演示版问答体验完善

## Summary

目标是把当前前后端分离版做成“本地可稳定演示”的 RAG 菜谱问答应用：前端能流式显示回答、展示引用来源和检索策略；后端能稳定处理 LLM/Embedding API、索引重建和降级；本地启动后可以完成一次索引重建并验证问答链路。

## Key Changes

- 先收口当前仓库状态：确认 `README.md`、前端类型文件是否真实改动，排除 `.idea` 和本地 `.env.local`；修复或确认中文乱码是否只是终端编码显示问题。
- 完善真正的流式问答链路：后端 `/api/chat/stream` 改为边检索边生成的 SSE 输出，前端 `ChatWorkspace` 使用流式读取并逐步追加 assistant 消息。
- 强化问答 UI：显示生成中状态、检索策略、引用菜谱、错误原因、重试按钮；空状态和异常状态要适合本地演示。
- 完善索引重建能力：状态页增加“重建索引”入口，调用 `/api/index/rebuild`，展示 Neo4j、Milvus、菜谱数、chunk 数、最近重建时间和失败来源。
- 稳定模型配置体验：保留 OpenAI-compatible LLM 和 Embedding 配置；当 API key、模型名、维度或外部服务不可用时，后端返回明确错误或降级说明，避免前端只显示 500。
- 保持本地演示优先：不做公网部署，不引入登录鉴权，不扩展复杂管理后台。

## Implementation Details

- 后端生成模块提供可迭代 token 输出接口，`RagService.stream_chat` 不再先完整生成答案后逐字拆分，而是复用同一套检索结果并直接透传 LLM streaming。
- SSE 事件固定为：`meta` 返回 strategy/sources，`token` 返回增量文本，`error` 返回可展示错误，`done` 表示结束；前端只依赖这四类事件。
- 前端 API 层新增 `streamChat(query, handlers)`，保留非流式 `chat()` 作为兼容或测试入口。
- 状态页的重建操作采用单次请求模式：点击后进入 loading，完成后刷新状态；不做后台任务队列，避免本地演示复杂化。
- README 补充本地演示流程：安装依赖、配置 `.env`、启动后端/前端、重建索引、测试问题示例；同时注明 embedding 模型/维度变更后必须重建索引。

## Test Plan

- 后端：运行 `python -m compileall backend\app`，用 TestClient 验证 `/api/health`、`/api/chat`、`/api/chat/stream`、`/api/index/rebuild` 的成功和降级场景。
- 前端：运行 `npm run build`，确认 Next 构建通过。
- 本地联调：启动后端和前端，访问聊天页，输入“推荐几个简单素菜”，确认回答流式出现、来源可点击、策略可见。
- 索引验收：在状态页点击重建索引，确认按钮 loading、结果刷新、失败来源或降级信息可读。
- 配置验收：分别测试缺少 LLM key、Embedding 模型不可用、Milvus 未启动时的提示是否清晰。

## Assumptions

- 下一阶段优先“问答体验”，不是部署上线。
- 本地演示要求包含“可重建索引”。
- 继续使用当前技术栈：FastAPI、Next.js、Neo4j、Milvus、OpenAI-compatible API。
- `.idea`、`frontend/.env.local` 这类本地环境文件不纳入提交。
- 当前未推送提交需要在后续实现完成后一起处理；如果 Codex 沙箱仍无法访问 SSH key，就由你在本机 PowerShell 执行 `git push origin codex-web-graph-rag`。
