# 传输层 + config save + 报错系统 — 测试断言

> 依据: `DESIGN_CONFIG_INDEX_PROTOCOL.md`、`DESIGN_USERCONFIG_OPS.md`、`DESIGN_RULE_VALIDATION.md`

---

## IMP1 — ForestPage 传输层绕过

| # | 场景 | 期望 |
|---|------|------|
| T1 | ForestPage 加载时调 `apiGet('/workspace/{id}/forest/mapping')` | 请求带 `X-UserConfig-Index` header |
| T2 | ForestPage 加载 SVG 时 | 请求带 `X-UserConfig-Index` header |
| T3 | 全站无 `fetch()` 裸调用绕开 transport 层 | grep 结果为 0（SVG 除外，SVG 需返回 text 不能走 apiGet） |

---

## IMP2 — config/save merge 语义

| # | 场景 | 期望 |
|---|------|------|
| T4 | 保存只改 `baksuffix` → 读回文件 → 其他字段不变 | `schema_namespace`、`workspace_dir` 等未被改动 |
| T5 | 保存时新增 `bakignore` 条目 → 读回文件 | 新增条目在，原有条目也在 |
| T6 | save 前后文件字节数对比 | 仅预期字段有差异 |

---

## IMP3 — Header 正确打包

| # | 场景 | 期望 |
|---|------|------|
| T7 | sessionStorage 有 configIndex → apiPost → 请求带完整 Header | Header 值为 `{"type":"path","string":"..."}` |
| T8 | sessionStorage 空 + localStorage 有 → apiGet → 请求带 Header | 从 localStorage 回退读取 |
| T9 | 两存储都空 → apiPost / apiGet 返回错误 | `{ok:false, errors:["请先在设置页面连接配置文件"]}` |

---

## IMP5 — 报错精准定位

| # | 场景 | 期望 |
|---|------|------|
| T10 | `rule_sources` 为旧数组格式 → schema verify 报错 | 错误指向 `rule_sources`，不指向 `schema_namespace` |
| T11 | `rule_sources.CT.name` 缺 `paths` → 报错 | 错误指向 `rule_sources → CT_allinone` |
| T12 | `databases.default` 缺 `path` → 报错 | 错误指向 `databases → default` |
| T13 | 未知额外字段 → `additionalProperties: false` 报错 | 明确指出哪个字段是多余的 |
