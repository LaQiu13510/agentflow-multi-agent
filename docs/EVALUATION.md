# AgentFlow 测试与评测

## 离线测试

```bash
python test_imports.py
python test_e2e.py
```

`test_imports.py` 覆盖：

- 配置和核心模块导入。
- MCP 风格工具注册和参数类型错误。
- 单意图关键词路由。
- Skill 多意图顺序和图片独占规则。
- 短期记忆、长期记忆和 Redis 内存降级。
- 上下文预算与运行时状态。

`test_e2e.py` 使用 Fake LLM 与 Fake MCP Server 覆盖：

- Researcher、Engineer、Writer、General 四类 Worker。
- 多 Worker 协作、上游结果交接和 Supervisor 协调。
- Worker 独立工具计划和工具调用记录。
- 长短期记忆写入与长期记忆检索。
- FastAPI 普通任务接口。
- LangGraph 节点级 SSE 事件。
- Checkpoint 查询与 Resume 接口。

## 路由评测

```bash
python eval/agent_eval.py
```

离线数据集包含单意图、复合意图、图片与工程冲突、自然语言改写等任务，输出：

- 单意图准确率。
- 单意图 Macro-F1。
- 各 Worker 的 Precision、Recall 和 F1。
- 路由混淆矩阵。
- 多意图 Skill 计划完全匹配率。
- 多意图工具计划完全匹配率。
- Skill Schema 覆盖率。

未命中规则的自然语言任务会在真实运行时进入 LLM 路由降级，因此离线 Skill 指标只衡量确定性路由层，不等同于完整线上系统准确率。

## 上下文评测

```bash
python eval/context_eval.py
```

该脚本构造长任务、长记忆、重复工具证据和敏感连接串，检查总预算合规率、任务保留率、近期记忆保留率、高优先级证据保留率、观察去重率、脱敏率和平均压缩比例。

## 外部服务检查

```bash
python test_imports.py --live
python test_e2e.py --live
```

Live 模式检查 LLM、Embedding、PostgreSQL 和 Milvus。图片服务可通过页面健康检查或 `image.health` 工具单独验证。

## 持续集成

GitHub Actions 在推送和拉取请求时执行：

1. Python 依赖安装。
2. 全仓库语法编译。
3. Docker Compose 配置校验。
4. 离线导入、端到端和路由评测。
