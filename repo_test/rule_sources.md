# rule_sources 对象化 — 测试断言

> 依据: `DESIGN_RULE_SOURCES.md`
> Schema: `user_config.schema.json`

---

## 后端

| # | 场景 | 期望 |
|---|------|------|
| T1 | `list-sources` 返回所有 key | `source_names: ["default", "custom"]` |
| T2 | `list-sources` 无 rule_sources | `source_names: []` |
| T3 | `scan-by-source` 已知 name，目录路径 | 返回 `.kmmrule.json` 文件列表 |
| T4 | `scan-by-source` 未知 name | `E_SOURCE_NOT_FOUND` |
| T5 | `scan-by-source` 混合路径（目录+文件） | 两类都正确返回 |
| T6 | `scan-by-source` 路径中有不存在的目录 | warning `W_PATH_NOT_FOUND`，其他路径正常返回 |
| T7 | `scan-by-source` source 存在但所有路径都不存在 | `files: []` + warnings |
| T8 | `scan-by-source` 现有 aggregate 不受影响 | 聚合仍接收 `paths`，正常工作 |

## 前端

| # | 场景 | 期望 |
|---|------|------|
| T9 | SettingsPage 展示 rule_sources 表格 | 名称列 + 路径列 + 编辑/删除按钮 |
| T10 | 添加新 source → 保存 | `/config/save` 写入完整对象 |
| T11 | RulesOverviewPage source 下拉 | 选择后自动加载文件列表 |
