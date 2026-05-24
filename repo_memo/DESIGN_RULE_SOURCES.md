# DESIGN_RULE_SOURCES — rule_sources 对象化设计

> Status: active
> Authority: authoritative
> Read-Tier: task-scoped
> Purpose: 规定 `rule_sources` 从字符串数组改为 `{name: {paths: [...]}}` 对象后的前后端契约
> 创建: 2026-05-23
> 依赖: `user_config.schema.json`（已更新）、`DESIGN_BOOTSTRAP.md` §4.2

---

## 一、Schema

`user_config.rule_sources` 格式（权威定义见 `user_config.schema.json`）：

```json
{
  "default": {
    "paths": ["~/workspace/modmanager/description/"]
  },
  "custom": {
    "paths": ["/path/to/rules/", "/other/rule.kmmrule.json"]
  }
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `<name>` | `string` | ✅ | source 别名（用户自定义，前端展示） |
| `<name>.paths` | `list[string]` | ✅ | 路径列表——目录以 `/` 结尾（扫描 `*.kmmrule.json`），文件以 `.kmmrule.json` 结尾 |

---

## 二、后端契约

### 2.1 `POST /api/rules/list-sources`

**请求**：`{}`（无参数）

前端调用此端点获取"有哪些 rule source 名字可用"。

**后端逻辑**：读取 `user_config.rule_sources`，返回所有 key。

**响应**：
```json
{
  "ok": true,
  "data": {"source_names": ["default", "custom"]},
  "errors": [],
  "warnings": []
}
```

### 2.2 `POST /api/rules/scan-by-source`

**请求**：`{"source_name": "default"}`

前端选择一个 source 名字 → 后端按名找 paths → 扫描目录 → 返回 `.kmmrule.json` 文件列表。

**后端逻辑**：
1. `discover_user_config()` → `rule_sources["default"]["paths"]`
2. 对每个 path 先调 `expand_path()` 展开 `~` 和环境变量
3. 对每个 path：
   - 目录（以 `/` 结尾）→ 调用现有 `/rules/scan` 逻辑 → 列出 `*.kmmrule.json`
   - 文件（以 `.kmmrule.json` 结尾）→ 校验文件存在 → 直接加入列表
   - 路径不存在 → 记录 warning: `W_PATH_NOT_FOUND: {path}`，继续处理其余路径
4. 按 `path` 去重后返回

**请求 Schema**：
```python
class RulesScanBySourceRequest(BaseModel):
    source_name: str
```

**错误**：
- `source_name` 不存在 → `{ok: false, errors: ["E_SOURCE_NOT_FOUND: 'xxx'"]}`
- source 存在但所有 paths 都无法访问 → `{ok: true, data: {files: []}, warnings: [...]}`

**响应**：
```json
{
  "ok": true,
  "data": {
    "source_name": "default",
    "files": [{"name": "...", "path": "/abs/path/...", "size": 12345}]
  },
  "errors": [],
  "warnings": []
}
```

### 2.3 现有端点不变

- `POST /api/workspace/{id}/rules/aggregate` — 仍接受 `paths: list[str]`
- `POST /api/rules/scan` — 保留，作为内部实现 `scan-by-source` 使用

---

## 三、前端契约

### 3.1 SettingsPage

**当前**：`rule_sources` 是字符串数组，每行一个路径。

**改后**：`rule_sources` 是 name→{paths} 对象。展示为可编辑表格：

| 名称 | 路径列表 | 操作 |
|------|---------|------|
| default | `/home/.../description/, /other/rule.kmmrule.json` | 编辑 / 删除 |
| [+ 添加] | | |

编辑弹窗：输入名称 + 路径列表（每行一个路径，可增删）。
保存时调 `POST /api/config/save`，写入完整 `rule_sources` 对象。

### 3.2 RulesOverviewPage

**当前**：从 `user_config.rule_sources`（字符串数组）直接扫描所有目录。

**改后**：
1. 页面顶部：source 下拉选择器（调 `POST /api/rules/list-sources` 获取选项）
2. 选择 source → 自动调 `POST /api/rules/scan-by-source` → 展示文件列表
3. 用户勾选文件 → 点击"聚合" → 调 `POST /api/workspace/{id}/rules/aggregate`（不变）
