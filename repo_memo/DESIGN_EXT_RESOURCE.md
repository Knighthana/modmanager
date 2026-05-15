# DESIGN_EXT_RESOURCE — 外部资源服务模型

> Status: stable (初版冻结)
> Authority: authoritative
> Read-Tier: task-scoped
> Purpose: 定义外部资源（kmmrule 描述的 preview/readme 等本地文件）的获取模型、白名单机制、前后端契约。不涉及系统内部产物（SVG、mapping、工作区数据）。

创建：2026-05-16
实现状态：待实现

---

## 0. 前置决策

| Q# | 决策 |
|-----|------|
| Q1 | 独立包 `ext_resource`，位于 `src/ext_resource/`，与 `modmanager` 同级 |
| Q2 | 前端不传文件路径——传后端给的索引符（`rule_id` + `mixed_id` + `index`） |
| Q3 | 白名单用于**通用文件请求端点**（如未来的 `/ext-resource/file`），不用于业务特异性端点（preview/readme 自身就是门禁） |
| Q4 | MVP 阶段 `rule_id` = 文件路径（功能不变），前端视其为不透明字符串 |
| Q5 | 文档先行，TODO-66/67 后续实现 |

---

## 1. 核心模型

### 1.1 外部资源 vs 内部资源

| | 外部资源 | 内部资源 |
|------|---------|---------|
| **是什么** | kmmrule 文件描述的本地文件（preview 图片、README 文本） | 本系统产出的数据（SVG、mapping、工作区目录） |
| **谁管理** | `ext_resource` 包 + 白名单机制 | 业务端点（`/api/workspace/...` 等） |
| **前端知道什么** | 文件路径或访问符号（展示用 + 索引用） | 后端给的对象名字 |
| **如何获取** | 通过外部资源端点 + 白名单验证 | 通过业务端点 |
| **白名单** | ✅ `repo_spec/resource_whitelist.json` | ❌ |

### 1.2 前端不假设路径

前端拿到 kmmrule 的 JSON 后看到 `preview: ["no smoke/预览图1.png"]`——但它不理解这个相对路径拼上什么基址才是真实文件位置。

端点契约：前端传它**知道的**三样东西，后端内部完成路径解析：

```
前端知道的信息：
  1. rule_id   — 哪个 kmmrule 文件（来自 rules/scan 返回的索引符）
  2. mixed_id  — 文件中的哪个条目
  3. index     — preview/readme 数组中的第几项

后端做的工作：
  1. 根据 rule_id 加载 kmmrule 文件
  2. 找到 mixed_id 对应的 operation
  3. 取出 preview[index] 或 readme[index] 的相对路径
  4. 从 database 查 mod.path → 拼接绝对路径
  5. 读文件 → 返回
```

MVP 阶段 `rule_id` 就是文件路径——功能零改动。但前端被约束为"这是不透明字符串"。

---

## 2. 架构拓扑

```
src/ext_resource/              ← 独立顶级包
├── __init__.py
├── manager.py                 # 资源生命周期管理（对外接口）
├── locator.py                 # 资源定位（本地文件系统解析）
├── cache.py                   # 内存缓存（MVP 占位，未来 LRU/TTL）
├── pipeline.py                # 预处理管线（MVP 占位，未来裁剪/放缩）
└── whitelist.py               # 白名单加载与验证

repo_spec/
└── resource_whitelist.json    # 白名单定义
```

**与已有模块的关系**：
- 不与 `modmanager` 互相依赖——`ext_resource` 独立
- `modmanager_web/routes/` 新建 `ext_resource.py` 路由，调用 `ext_resource.manager`
- CLI / Tauri 也可直接 `import ext_resource`

---

## 3. 端点规范

### 3.1 Preview 图片

```
POST /api/ext-resource/preview
Content-Type: application/json

请求：
{
  "rule_id": "the_opaque_rule_id",
  "mixed_id": "270150:3426079135",
  "index": 0,
  "database_name": "default"
}

响应：
200 OK
Content-Type: image/png (或 image/jpeg，后端根据文件头判断)

(图片二进制)

错误：
404 — 资源不存在
400 — 参数缺失
```

### 3.2 README 文本

```
POST /api/ext-resource/readme
Content-Type: application/json

请求：
{
  "rule_id": "the_opaque_rule_id",
  "mixed_id": "270150:3426079135",
  "index": 0,
  "database_name": "default"
}

响应：
200 OK
Content-Type: text/plain; charset=utf-8

(文本内容)

错误：
404 / 400 / 403 同上
```

### 3.3 数据库依赖

端点需要知道从哪里查 mod 路径。两种方式：

| 方式 | 请求体 | 说明 |
|------|--------|------|
| **database_name** | `{ ..., database_name: "default" }` | 直接指定 database |
| **workspace_id** | `{ ..., workspace_id: "abc123" }` | 从工作区 meta 读取 database_name |

**MVP 采用 `database_name`**——更直接，调用方（RulesOverviewPage）可从当前工作区上下文中获取。

---

## 4. 后端行为

### 4.1 路径解析

```python
# ext_resource/locator.py (伪代码)

def resolve_resource_path(
    rule_id: str,
    mixed_id: str,
    index: int,
    resource_type: "preview" | "readme",
    database: dict,
) -> str:
    """从 kmmrule 文件 + database 解析出资源的绝对路径。

    1. 加载 kmmrule 文件 (rule_id)
    2. 找到 operation.mixed_id == mixed_id
    3. 取出 operation[resource_type][index]
    4. 从 database.mod[] 中找到 mixed_id 对应的 mod.path
    5. 拼接 mod_path + 相对路径 → 绝对路径
    """
```

### 4.2 白名单验证（不用于 preview/readme 端点）

preview 和 readme 端点**自身就是门禁**——它们只能从 kmmrule 文件 + database 解析资源，其他模块无法通过这两个端点获取任意文件。**不需要白名单验证。**

白名单机制保留给未来的**通用文件请求端点**（如 `/ext-resource/file`），该端点接受任意模块提交的文件路径请求，必须通过白名单的 `(module, purpose)` 门禁确保开发过程不失控。

---

## 5. 前端使用

### 5.1 RulesOverviewPage 集成

用户在 RulesOverviewPage 展开一个 kmmrule 文件的详情时：
1. 已有 `rule_id`（来自 `rules/scan`）+ `mixed_id`（来自文件内容）
2. 展示 preview 缩略图：`GET /api/ext-resource/preview` 返回图片 → `<img>` 展示
3. 展示 README 文件名列表：可点击
4. 点击文件名：`GET /api/ext-resource/readme` → 弹出对话框显示文本

### 5.2 MVP 图片展示

前端用 CSS `object-fit: cover` + 固定尺寸容器限制显示——不做后端裁剪。以后再升级。

---

## 6. 白名单机制

### 6.1 适用范围

白名单**不用于** preview 和 readme 端点——这两个端点自身就是门禁（只能解析 kmmrule 文件 + database 中的路径，无法被滥用于任意文件访问）。

白名单用于未来的**通用文件请求端点**（如 `POST /api/ext-resource/file`），该端点接受任意模块提交的文件路径请求。每个调用方必须提供 `(module, purpose)`，后端比对白名单放行。

### 6.2 设计目的

**不是保护用户本地文件**——本地单人应用不存在越权访问问题。

**是开发纪律**——有了白名单机制后，每个新增的文件请求场景都需要在白名单中新增条目。这迫使开发者审视"调用模块是否合理""用途是否正当"，防止内部模块随意添加文件读取逻辑导致架构失控。

### 6.3 白名单文件

```json
{
  "whitelist_version": "1",
  "entries": [
    {
      "module": "rules-overview",
      "purpose": "read_kmmrule_file",
      "description": "Read raw kmmrule file content for display",
      "added_date": "2026-05-16",
      "status": "active"
    }
  ]
}
```

### 6.4 新增端点时的流程

1. 在 `repo_spec/resource_whitelist.json` 新增 `(module, purpose)` 条目
2. 在路由层加 `whitelist.validate(module, purpose)` 调用
3. 测试文件验证：所有 `validate` 调用的 `(module, purpose)` 都在白名单中

---

## 7. 扩展方向（不在此 MVP）

| 功能 | 说明 |
|------|------|
| **图片裁剪/放缩** | 后端预处理，产生裁剪后的小图缓存，匹配前端空位尺寸 |
| **内存缓存** | LRU/TTL 缓存已加载资源，避免重复磁盘 IO |
| **WebDAV / 网络协议** | `locator.py` 支持非本地文件系统协议 |
| **多用户白名单** | 动态加载 + 身份认证 |
| **哈希索引** | 资源请求命令归一化 → 哈希 → 缓存命中 |

---

## 8. 权威文档引用

| 文档 | 关系 |
|------|------|
| `DESIGN_WORKSPACE_MODEL.md` | 内部资源管理模型，外部资源属独立模块 |
| `DESIGN_REST_API.md` | 端点注册与响应格式 |
| `DESIGN_STORAGE.md` | `resource_whitelist.json` 文件位置 |
| `DOCUMENT_GOVERNANCE.md` | 文档治理规范 |

---

## 9. 实现步骤

| 步骤 | 内容 |
|:--:|------|
| 1 | 新建 `src/ext_resource/` 包（`manager.py`、`locator.py`、`whitelist.py`） |
| 2 | 新建 `repo_spec/resource_whitelist.json` |
| 3 | 新建 `modmanager_web/routes/ext_resource.py`（preview + readme 端点） |
| 4 | 注册路由到 `app.py` |
| 5 | 前端 RulesOverviewPage 调用新端点完成 TODO-66/67 |
