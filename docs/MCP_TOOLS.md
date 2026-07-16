# AgentFlow MCP 风格工具层

AgentFlow 使用进程内 MCP 风格协议统一工具发现、参数约束、调用结果和错误处理。该实现保留 Agent 与外部能力之间的契约边界，但不启动独立官方 MCP Server 进程。

## 基础类型

- `ToolSpec`：工具名称、说明和输入 Schema。
- `ToolResult`：成功状态、文本内容和元数据。
- `LocalMCPServer`：同类工具服务基类。
- `ToolRegistry`：多服务注册、发现和统一调用入口。

调用格式：

```python
registry.call("server_name", "tool_name", **arguments)
```

工具执行前会使用处理函数签名检查必填参数，并根据类型标注校验 `str`、`int`、`float` 和 `bool` 参数。错误统一转换为 `ToolResult`，避免异常直接打断整个 Agent 图。

## PostgreSQL 工具

服务名：`postgres`

| 工具 | 说明 |
| --- | --- |
| `health` | 检查数据库连接 |
| `list_tables` | 查看允许访问的表 |
| `list_smartkb_documents` | 查询 SmartKB 文档元数据 |
| `safe_select` | 对白名单表执行受限只读查询 |

## Milvus 工具

服务名：`milvus`

| 工具 | 说明 |
| --- | --- |
| `health` | 检查 Milvus 连接 |
| `collection_stats` | 查看 Collection 和向量数量 |
| `search_smartkb` | 检索 SmartKB 知识片段 |

## 项目分析工具

服务名：`project`

| 工具 | 说明 |
| --- | --- |
| `engineering_requirements` | 返回 AI 应用工程检查项 |
| `project_summary` | 生成项目摘要所需结构化信息 |
| `quality_checklist` | 根据技术栈生成质量检查清单 |

## 图片生成工具

服务名：`image`

| 工具 | 说明 |
| --- | --- |
| `health` | 检查图片服务配置 |
| `generate_image` | 调用 Right Code 兼容接口和 `gpt-image-2` 生成图片 |

图片工具返回 URL 或本地保存路径，并在元数据中记录尺寸等信息。图片 Skill 具有独占优先级，架构图和流程图请求不会再被 Engineer 路由覆盖。

## 扩展方式

1. 继承 `LocalMCPServer`。
2. 在 `register_tools()` 中声明 `ToolSpec` 和处理函数。
3. 在 `tools/registry.py` 中注册服务。
4. 在 Skill 的 `suggested_tools` 或 Worker 默认计划中引用 `server.tool`。
5. 增加参数错误、成功返回和工具不可用测试。
