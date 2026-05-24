# config_index Header 传输 — 测试断言

> 依据: `DESIGN_CONFIG_INDEX_PROTOCOL.md`

---

## 前端（Transport 层）

| # | 场景 | 期望 |
|---|------|------|
| T1 | sessionStorage 有 configIndex → apiPost 请求带 `X-UserConfig-Index` header | header 值为 `{"type":"path","string":"/test/config.json"}` |
| T2 | sessionStorage 空 → localStorage 有 → apiGet 请求带 header | 同上，从 localStorage 回退读取 |
| T3 | sessionStorage 和 localStorage 都空 → apiPost 返回错误 | `{ok:false, errors:["请先在设置页面连接配置文件"]}` |
| T4 | apiPost body 中不再有 `config_index` 字段 | body 仅含业务字段 |
| T5 | apiGet URL 中不再有 `?config_index=...` query | URL 干净 |
| T6 | streamSse 请求带 `X-UserConfig-Index` header | 同上 |

## 后端

| # | 场景 | 期望 |
|---|------|------|
| T7 | 请求带有效 `X-UserConfig-Index` header → `get_config_index()` 返回路径字符串 | `"/home/user/.config/kmm/user_config.json"` |
| T8 | 请求无 `X-UserConfig-Index` header → 400 或 422 | FastAPI 自动返回验证错误 |
| T9 | Header 值非法 JSON → 400 | `"Invalid X-UserConfig-Index header"` |
| T10 | `/config/discover` 不再需要 body 中的 `config_index` | schema 中无此字段 |
| T11 | `/api/workspace/{id}/pipeline/compute` 不带 query 参数正常执行 | 422 不再出现 |
