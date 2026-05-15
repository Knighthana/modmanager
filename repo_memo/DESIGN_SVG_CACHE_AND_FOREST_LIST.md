# SVG 缓存与森林列表设计

> Status: stable (初版冻结)
> Authority: authoritative
> Read-Tier: always
> Purpose: 规范 SVG 缓存、森林列表页、资源白名单的设计，为前后端实现提供完整契约

创建：2026-05-16
实现状态：待实现

---

## 0. 前置决策汇总

本文档基于以下场景确认：**单用户本地应用，无远程访问或多用户要求。**

| Q# | 决策 | 备注 |
|-----|------|------|
| Q1 | 参数哈希由后端独立计算，前端无需关心算法 | 前端传参数，后端返回svg_id；避免前端缓存索引脆弱性 |
| Q2 | SVG存储由后端统一管理，前端仅做本地缓存+渲染 | 便于权限管控、资源复用、版本管理 |
| Q3 | 单POST端点：`POST /api/svg/compute` + force_compute标志 | 避免多端点的额外复杂性；force_compute=true忽略缓存强制计算 |
| Q4 | 森林列表页介于计算准备与森林可视之间，后端维护映射 | 前端不再记忆参数；用户直观看到已生成的森林列表 |
| Q5 | 快照包含：params + 三文件sha256指纹 + 时间戳 + app_version | 无需存笛卡尔积；指纹不匹配时缓存自动失效 |
| Q6 | 白名单独立JSON文件 `repo_spec/resource_whitelist.json` | 代码和测试均从此文件加载；便于查询和管理 |
| Q7 | 缓存淘汰初期由用户手动删除，预留LRU/TTL配置点 | 单机不怕浪费空间；森林列表页提供删除UI |
| Q8 | 资源门禁以本地简化为主，无需复杂身份认证 | 预留白名单扩展点用于未来多用户场景 |

---

## 1. 设计目标与场景

### 设计目标
1. **高效缓存**：避免重复计算相同参数的SVG，减少磁盘IO和内存占用
2. **版本管理**：快照记录参数和底层数据版本，自动检测缓存失效
3. **用户可见**：森林列表页让用户直观查看、选择已生成的森林，而非通过前端状态推测
4. **可扩展**：为未来多用户/远程访问预留扩展点，但初期不实现

### 场景与假设
- **单用户本地应用**：无需复杂的身份认证和并发控制；本地进程间通信足够快
- **参数驱动**：同一参数集总是产生相同的SVG；底层数据变化时缓存失效
- **文件持久化**：SVG和快照保存在本地文件系统，不涉及数据库
- **前后端分离**：前端通过REST API调用后端；后端独立管理缓存

---

## 2. 系统架构

### 总体流程
```
前端用户
   ↓
[计算准备页] 用户配置参数
   ↓
点击"计算"按钮
   ↓
POST /api/svg/compute(params, force_compute=false)
   ↓
后端处理
  ├─ 规范化params，计算哈希 → svg_id
  ├─ 查询快照 cache_dir/{svg_id}.json
  ├─ 若存在且有效 且 force_compute=false
  │  └─ 返回 {svg_id, is_cached: true}
  └─ 否则
     ├─ 触发SVG计算
     ├─ 原子写入 svg_id.json (快照) + svg_id.svg (SVG文件)
     └─ 返回 {svg_id, is_cached: false}
   ↓
前端收到响应
  ├─ 显示进度或等待
  ├─ 获取svg_id
  └─ 跳转到森林列表页
   ↓
[森林列表页]
  ├─ GET /api/svg/list 获取所有缓存森林
  ├─ 展示表格：参数摘要、生成时间、数据状态
  ├─ 用户点选一行 → 进入森林可视页
  └─ 用户删除 → DELETE /api/svg/{svg_id}
   ↓
[森林可视页]
  ├─ GET /api/svg/{svg_id} 拉取SVG文件
  ├─ 前端渲染和交互
```

### 职责分工

**后端职责**
- 参数规范化与哈希计算
- 快照与SVG文件管理（原子写入、孤儿清理）
- 缓存失效检测（指纹比对）
- 资源端点的白名单验证
- SVG文件提供与删除

**前端职责**
- 参数输入与验证
- 调用后端端点
- 森林列表页展示与交互
- SVG文件本地缓存（可选）和渲染
- 不再维护参数状态作为缓存索引

---

## 3. 后端端点规范

### 3.1 计算或读取SVG

**端点**
```
POST /api/svg/compute
Content-Type: application/json

请求体：
{
  "params": {
    // 计算参数，结构由业务定义
    // 示例：
    "seed": 42,
    "rule_version": "v2.3",
    "mods": ["mod1", "mod2"]
  },
  "force_compute": false  // 可选，默认false；true则忽略缓存强制计算
}

响应：
200 OK
{
  "svg_id": "abc123def456",  // sha256(规范化后的params + 指纹)
  "is_cached": true,          // 是否来自缓存
  "message": "Successfully retrieved cached SVG" / "Computed new SVG"
}

错误：
400 Bad Request
{
  "detail": "Invalid parameters: missing required field 'seed'"
}
```

**后端行为**
1. 接收params，调用`normalize_params(params)` → params_normalized
2. 计算 `params_hash = sha256(json.dumps(params_normalized, sort_keys=True))`
3. 计算 `data_fingerprints = {
     "kmmrule": sha256(kmmrule_file_content),
     "database": sha256(database_file_content),
     "branch_decisions": sha256(branch_decisions_file_content)
   }`
4. 计算 `svg_id = sha256(params_hash + concat(data_fingerprints))`
5. 查找 `cache_dir/{svg_id}.json` 快照
6. 若快照存在 且 is_complete=true 且 指纹匹配 且 force_compute=false
   - → 返回 {svg_id, is_cached: true}
7. 否则
   - 触发SVG计算（独立异步任务或同步）
   - 生成快照JSON和SVG文件
   - 返回 {svg_id, is_cached: false}

**白名单检查**
```python
@app.post("/api/svg/compute")
async def compute_svg(request: ComputeRequest):
    if not whitelist.validate("forest", "compute_svg"):
        raise HTTPException(status_code=403, detail="Not authorized")
    # ... 业务逻辑
```

### 3.2 列表已缓存的森林

**端点**
```
GET /api/svg/list
Content-Type: application/json

响应：
200 OK
[
  {
    "svg_id": "abc123def456",
    "params": {
      "seed": 42,
      "rule_version": "v2.3",
      "mods": ["mod1", "mod2"]
    },
    "summary": "Seed 42, v2.3 rules, 2 mods",  // 人可读摘要
    "generated_at": "2026-05-16T10:30:00Z",
    "data_status": "valid"  // "valid" 或 "stale"
  },
  ...
]
// 按generated_at降序排列

错误：
500 Internal Server Error
{
  "detail": "Failed to list cached forests"
}
```

**后端行为**
1. 遍历 `cache_dir/` 目录，查找所有 `*.json` 快照文件
2. 对每个快照
   - 验证对应的 `{svg_id}.svg` 是否存在
   - 验证快照的 `is_complete` 标记
   - 重新计算当前数据的指纹，与快照中的指纹比对
   - 若缺失SVG或is_complete=false → 删除孤儿快照，跳过此项
   - 若指纹不匹配 → data_status="stale"
   - 否则 → data_status="valid"
3. 从快照提取params，调用`generate_summary(params)` 生成摘要
4. 返回列表，按generated_at降序排列

**白名单检查**
```python
@app.get("/api/svg/list")
async def list_forests():
    if not whitelist.validate("forest", "list_cached_forests"):
        raise HTTPException(status_code=403, detail="Not authorized")
    # ... 业务逻辑
```

### 3.3 删除缓存的森林

**端点**
```
DELETE /api/svg/{svg_id}

响应：
204 No Content
（或）
200 OK
{
  "message": "Forest cached successfully deleted"
}

错误：
404 Not Found
{
  "detail": "SVG not found"
}
```

**后端行为**
1. 查找 `cache_dir/{svg_id}.json` 和 `cache_dir/{svg_id}.svg`
2. 若都不存在 → 返回404
3. 删除两个文件（原子操作，或先删一个记录错误再删另一个）
4. 返回204或200

**白名单检查**
```python
@app.delete("/api/svg/{svg_id}")
async def delete_forest(svg_id: str):
    if not whitelist.validate("forest", "delete_cached_forest"):
        raise HTTPException(status_code=403, detail="Not authorized")
    # ... 业务逻辑
```

### 3.4 读取单个SVG文件

**端点**
```
GET /api/svg/{svg_id}

响应：
200 OK
Content-Type: image/svg+xml

<svg>...</svg>

错误：
404 Not Found
{
  "detail": "SVG not found"
}
```

**后端行为**
1. 查找 `cache_dir/{svg_id}.svg`
2. 若不存在 → 返回404
3. 读取文件内容，返回SVG (Content-Type: image/svg+xml)

**白名单检查**（非关键，但建议一致性）
```python
@app.get("/api/svg/{svg_id}")
async def get_svg(svg_id: str):
    if not whitelist.validate("forest", "read_cached_svg"):
        raise HTTPException(status_code=403, detail="Not authorized")
    # ... 业务逻辑
```

---

## 4. 数据结构设计

### 4.1 快照文件 (Snapshot)

**文件位置**：`cache_dir/{svg_id}.json`

**结构**
```json
{
  "snapshot_version": "1",
  "svg_id": "abc123def456",
  
  "params_original": {
    "seed": 42,
    "rule_version": "v2.3",
    "mods": ["mod1", "mod2"]
  },
  "params_normalized": {
    "mods": ["mod1", "mod2"],
    "rule_version": "v2.3",
    "seed": 42
  },
  
  "data_fingerprints": {
    "kmmrule": "sha256:abc...xyz",
    "database": "sha256:def...uvw",
    "branch_decisions": "sha256:ghi...rst"
  },
  
  "generated_at": "2026-05-16T10:30:00Z",
  "app_version": "1.0.0",
  "is_complete": true
}
```

**字段说明**

| 字段 | 类型 | 说明 |
|------|------|------|
| `snapshot_version` | string | 快照格式版本；升级时用于迁移旧快照 |
| `svg_id` | string | 本快照对应的SVG ID（由后端计算） |
| `params_original` | object | 前端提交的原始参数，用于UI展示 |
| `params_normalized` | object | 规范化后的参数，用于计算哈希 |
| `data_fingerprints` | object | 三个底层文件的SHA256指纹 |
| `generated_at` | string | ISO 8601时间戳，用于列表排序 |
| `app_version` | string | 生成此快照时的应用版本 |
| `is_complete` | bool | 是否完整写入（防止部分写） |

**指纹计算规则**（见第5章）

### 4.2 缓存目录结构

```
$WORKSPACE/.cache/svg/
├── abc123def456.json         # 快照1
├── abc123def456.svg          # SVG文件1
├── xyz789uvw123.json         # 快照2
├── xyz789uvw123.svg          # SVG文件2
└── ...
```

**目录初始化**
- 后端启动时，若 `.cache/svg/` 不存在，自动创建
- 首次计算时触发

**清理策略**
- LIST端点遍历时自动清理孤儿文件（缺SVG或is_complete=false的快照）
- 用户通过DELETE端点手动删除
- 未来可支持自动LRU/TTL（预留配置参数）

### 4.3 文件命名规则

**SVG ID计算**
```
params_normalized = normalize_params(params)
params_json = json.dumps(params_normalized, sort_keys=True)
params_hash = sha256(params_json)

data_fingerprints_str = concat([
  data_fingerprints["kmmrule"],
  data_fingerprints["database"],
  data_fingerprints["branch_decisions"]
])
// 或使用JSON格式：
data_fingerprints_json = json.dumps(data_fingerprints, sort_keys=True)

svg_id = sha256(params_hash + data_fingerprints_json)
// 取前24个字符（可选，便于人工识别）：
svg_id = sha256(...)[0:24]
```

**参数摘要生成**
```python
def generate_summary(params: dict) -> str:
    """生成人可读的参数摘要"""
    parts = []
    if "seed" in params:
        parts.append(f"Seed {params['seed']}")
    if "rule_version" in params:
        parts.append(f"{params['rule_version']} rules")
    if "mods" in params:
        parts.append(f"{len(params['mods'])} mods")
    return ", ".join(parts)
```

---

## 5. 参数规范化规则

**目的**：确保前后端对同一参数集计算的哈希一致，避免缓存命中失败。

### 5.1 序列化规则

1. **键排序**：所有对象类型的键必须按字母顺序排序
   ```python
   json.dumps(params, sort_keys=True)
   ```

2. **浮点精度**：所有浮点数精确到小数点后2位
   ```python
   def normalize_float(v: float) -> float:
       return round(v, 2)
   ```

3. **null和undefined处理**：null保留，undefined转为null
   ```python
   # JavaScript: undefined → JSON: null
   # Python: None → JSON: null
   ```

4. **日期格式**：统一为ISO 8601格式，UTC时区
   ```python
   datetime.isoformat() + "Z"
   ```

5. **数组排序**（若需要）：业务定义是否排序；默认保持原序
   - 若某字段的顺序无意义（如集合），必须排序并在本文档明确标记

6. **字符串大小写**：保持原值，不做大小写转换

7. **移除空字段**：不移除null，但移除undefined和空对象 `{}`
   ```python
   # 不移除：{"field": null}
   # 移除：{"field": undefined} 或 {"field": {}}
   ```

### 5.2 验证规则

计算哈希前，后端必须验证params的有效性：

```python
def validate_params(params: dict) -> bool:
    """
    必填字段检查
    类型检查
    范围检查（如seed应为非负整数）
    """
    required = ["seed", "rule_version"]
    if not all(k in params for k in required):
        raise ValueError(f"Missing required fields: {required}")
    
    if not isinstance(params["seed"], int) or params["seed"] < 0:
        raise ValueError("'seed' must be non-negative integer")
    
    if not isinstance(params["rule_version"], str):
        raise ValueError("'rule_version' must be string")
    
    return True
```

### 5.3 测试验证

**单测必须覆盖**
1. 参数 `{a:1, b:2}` 和 `{b:2, a:1}` 产生相同哈希
2. 浮点参数精度处理（如3.14159保留为3.14）
3. null和undefined的处理
4. 日期格式的标准化

---

## 6. 白名单设计

### 6.1 白名单文件

**文件位置**：`repo_spec/resource_whitelist.json`

**结构**
```json
{
  "whitelist_version": "1",
  "entries": [
    {
      "module": "forest",
      "purpose": "compute_svg",
      "description": "Forest visualization SVG generation - compute new or cached",
      "added_date": "2026-05-16",
      "status": "active"
    },
    {
      "module": "forest",
      "purpose": "list_cached_forests",
      "description": "Enumerate and inspect cached forest SVGs",
      "added_date": "2026-05-16",
      "status": "active"
    },
    {
      "module": "forest",
      "purpose": "delete_cached_forest",
      "description": "Delete cached forest by svg_id",
      "added_date": "2026-05-16",
      "status": "active"
    },
    {
      "module": "forest",
      "purpose": "read_cached_svg",
      "description": "Read SVG file content for rendering",
      "added_date": "2026-05-16",
      "status": "active"
    }
  ]
}
```

**字段说明**

| 字段 | 说明 |
|------|------|
| `whitelist_version` | 白名单格式版本 |
| `module` | 功能模块名（如"forest", "backup", "rules"） |
| `purpose` | 功能目的，唯一标识该请求的业务用途 |
| `description` | 人可读的功能描述 |
| `added_date` | 加入白名单的日期 |
| `status` | "active"（使用中）或"deprecated"（已废弃） |

### 6.2 代码中的验证

**后端初始化（启动时加载，缓存在内存）**
```python
# backend/core/resource_whitelist.py
import json
from pathlib import Path

class ResourceWhitelist:
    def __init__(self, whitelist_path: str = "repo_spec/resource_whitelist.json"):
        with open(whitelist_path) as f:
            data = json.load(f)
        self.entries = data["entries"]
        self._index = {
            (e["module"], e["purpose"]): e
            for e in self.entries
            if e["status"] == "active"
        }
    
    def validate(self, module: str, purpose: str) -> bool:
        """检查(module, purpose)是否在白名单中"""
        return (module, purpose) in self._index
    
    def get_entry(self, module: str, purpose: str) -> dict | None:
        """获取白名单条目，用于审计/日志"""
        return self._index.get((module, purpose))

# 全局实例
whitelist = ResourceWhitelist()
```

**端点装饰器或前置检查**
```python
from fastapi import HTTPException

async def check_whitelist(module: str, purpose: str):
    """可作为FastAPI依赖注入"""
    if not whitelist.validate(module, purpose):
        raise HTTPException(
            status_code=403,
            detail=f"Resource {module}:{purpose} not in whitelist"
        )

@app.post("/api/svg/compute")
async def compute_svg(request: ComputeRequest, _=Depends(check_whitelist("forest", "compute_svg"))):
    # ... 业务逻辑
```

或简化为端点内显式检查：
```python
@app.post("/api/svg/compute")
async def compute_svg(request: ComputeRequest):
    if not whitelist.validate("forest", "compute_svg"):
        raise HTTPException(status_code=403, detail="Not authorized")
    # ... 业务逻辑
```

### 6.3 文档与测试

**文档更新**
- `repo_memo/DESIGN_REST_API.md` 补充"资源白名单机制"章节，说明：
  - 白名单文件位置和加载时机
  - module/purpose的定义规范
  - 新增资源时的更新流程

**测试覆盖 `tests/test_resource_whitelist.py`**
```python
def test_all_resource_endpoints_in_whitelist():
    """
    验证所有资源端点的(module, purpose)声明都在白名单中。
    """
    whitelist = load_whitelist("repo_spec/resource_whitelist.json")
    
    # 通过grep或AST分析提取代码中的所有 whitelist.validate() 调用
    endpoints = extract_whitelist_calls("src/modmanager_web/")
    
    for module, purpose in endpoints:
        assert whitelist.validate(module, purpose), \
            f"Endpoint ({module}, {purpose}) not in whitelist"

def test_whitelist_no_duplicates():
    """验证白名单中无重复条目"""
    whitelist = load_whitelist(...)
    entries = [(e["module"], e["purpose"]) for e in whitelist.entries]
    assert len(entries) == len(set(entries)), "Whitelist has duplicates"

def test_whitelist_format():
    """验证白名单JSON格式正确"""
    whitelist = load_whitelist(...)
    assert "whitelist_version" in whitelist
    assert "entries" in whitelist
    # ... 更多格式检查
```

---

## 7. 前端职责与森林列表页

### 7.1 前端页面结构

```
┌──────────────────────────┐
│   计算准备页 (ComputePrepPage)  │
│  - 参数输入表单             │
│  - "计算"按钮               │
└──────────────────────────┘
           ↓
    POST /api/svg/compute
           ↓
┌──────────────────────────┐
│  森林列表页 (ForestListPage)  │  ← 新增
│  - 已缓存森林列表          │
│  - "查看"按钮 → 可视页      │
│  - "删除"按钮 → 清除缓存    │
│  - "刷新"按钮 → 重加载      │
└──────────────────────────┘
           ↓
┌──────────────────────────┐
│ 森林可视页 (ForestPage)    │
│  - SVG渲染与交互           │
└──────────────────────────┘
```

### 7.2 森林列表页实现

**职责**
1. 调用 `GET /api/svg/list` 获取缓存列表
2. 展示表格：svg_id / 参数摘要 / 生成时间 / 数据状态
3. 提供交互
   - "查看"：跳转到森林可视页（需传svg_id）
   - "删除"：调用 `DELETE /api/svg/{svg_id}`，刷新列表
   - "刷新"：重新GET /api/svg/list

**UI示例**
```vue
<template>
  <div class="forest-list-page">
    <h2>Cached Forests</h2>
    <button @click="refreshList" :disabled="loading">Refresh</button>
    
    <table v-if="forests.length">
      <thead>
        <tr>
          <th>SVG ID</th>
          <th>Summary</th>
          <th>Generated At</th>
          <th>Data Status</th>
          <th>Actions</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="forest in forests" :key="forest.svg_id">
          <td>{{ forest.svg_id.substring(0, 12) }}...</td>
          <td>{{ forest.summary }}</td>
          <td>{{ new Date(forest.generated_at).toLocaleString() }}</td>
          <td :class="'status-' + forest.data_status">
            {{ forest.data_status }}
          </td>
          <td>
            <button @click="viewForest(forest.svg_id)">View</button>
            <button @click="deleteForest(forest.svg_id)">Delete</button>
          </td>
        </tr>
      </tbody>
    </table>
    
    <p v-else>No cached forests yet.</p>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()
const forests = ref([])
const loading = ref(false)

async function refreshList() {
  loading.value = true
  try {
    const res = await fetch('/api/svg/list')
    forests.value = await res.json()
  } catch (e) {
    console.error('Failed to load forests:', e)
  } finally {
    loading.value = false
  }
}

async function viewForest(svgId: string) {
  router.push({ name: 'forest', params: { svg_id: svgId } })
}

async function deleteForest(svgId: string) {
  if (!confirm('Delete this forest?')) return
  try {
    await fetch(`/api/svg/${svgId}`, { method: 'DELETE' })
    await refreshList()
  } catch (e) {
    console.error('Failed to delete forest:', e)
  }
}

onMounted(refreshList)
</script>

<style scoped>
.status-valid { color: green; }
.status-stale { color: orange; }
</style>
```

### 7.3 计算准备页改动

**改动点**
1. "计算"按钮点击后，调用 `POST /api/svg/compute`，获得svg_id
2. 成功后，不直接跳转到森林可视页，而是跳到森林列表页
3. 或者，计算完成立即跳转到森林可视页，但允许用户从那里返回到列表

**代码示例**
```typescript
async function handleCompute() {
  const response = await fetch('/api/svg/compute', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      params: computeParams.value,
      force_compute: false
    })
  })
  
  if (response.ok) {
    const result = await response.json()
    // 跳转到森林列表或直接到可视页
    router.push({ name: 'forest-list' })
    // 或
    // router.push({ name: 'forest', params: { svg_id: result.svg_id } })
  }
}
```

### 7.4 森林可视页改动

**改动点**
1. 路由参数从 `params` 改为接收 `svg_id`
2. 以svg_id调用 `GET /api/svg/{svg_id}` 拉取SVG文件
3. 其余渲染逻辑不变

**代码示例**
```typescript
const route = useRoute()
const svgId = route.params.svg_id as string

onMounted(async () => {
  const response = await fetch(`/api/svg/${svgId}`)
  const svgContent = await response.text()
  // 渲染SVG
  document.getElementById('svg-container').innerHTML = svgContent
})
```

---

## 8. 文件组织与代码位置

### 8.1 后端文件

```
src/modmanager_web/
├── routes/
│   ├── __init__.py
│   └── svg_cache.py           # 新增：svg相关端点
├── core/
│   ├── __init__.py
│   └── resource_whitelist.py   # 新增：白名单加载与验证
├── schemas/
│   ├── __init__.py
│   └── svg_cache.py            # 新增：ComputeRequest, ListResponse等
└── utils/
    ├── __init__.py
    └── svg_normalizer.py        # 新增：参数规范化与哈希

repo_spec/
├── resource_whitelist.json     # 新增：白名单定义

tests/
├── test_svg_cache.py           # 新增：POST/GET/DELETE端点测试
├── test_resource_whitelist.py  # 新增：白名单验证测试
└── test_svg_normalizer.py      # 新增：参数规范化测试
```

### 8.2 前端文件

```
src/
├── pages/
│   ├── ComputePrepPage.vue     # 改动：计算后跳转到列表页
│   ├── ForestListPage.vue      # 新增：森林列表页
│   └── ForestPage.vue          # 改动：接收svg_id而非params
├── services/
│   └── svgApi.ts               # 新增：SVG相关API调用
├── types/
│   └── svg.ts                  # 新增：SVG相关类型定义
└── styles/
    └── forest-list.css         # 新增：森林列表样式
```

---

## 9. 实现步骤（推荐顺序）

### Phase 1: 后端基础（第1-3周）

**步骤1.1：参数规范化与哈希**
- 实现 `svg_normalizer.py`: `normalize_params()`, `compute_params_hash()`, `compute_fingerprints()`, `compute_svg_id()`
- 单测覆盖上述函数，验证规范化规则
- 参考：TERMS_FIELD_FREEZE.md（若需补充浮点、日期等规则）

**步骤1.2：快照数据结构**
- 定义 `schemas/svg_cache.py`: `ComputeRequest`, `ComputeResponse`, `ForestInfo`, `ListResponse`
- 实现快照JSON读写函数
- 单测快照序列化/反序列化

**步骤1.3：资源白名单**
- 创建 `repo_spec/resource_whitelist.json`
- 实现 `core/resource_whitelist.py`: `ResourceWhitelist` 类
- 单测白名单加载和验证

### Phase 2: 后端端点（第4-5周）

**步骤2.1：POST /api/svg/compute**
- 实现 `routes/svg_cache.py` 中的 `compute_svg()` 端点
- 调用规范化、哈希、快照查询和写入
- 白名单验证装饰器
- 单测：缓存命中、缓存未命中、force_compute=true、invalid params

**步骤2.2：GET /api/svg/list**
- 实现 `list_forests()` 端点
- 目录遍历、快照验证、孤儿清理
- 生成摘要和data_status
- 单测：正常列表、缺SVG的快照、指纹不匹配

**步骤2.3：DELETE 和 GET**
- 实现 `delete_forest()` 和 `get_svg()` 端点
- 单测：删除存在/不存在的项、读取SVG文件

### Phase 3: 前端页面（第6-8周）

**步骤3.1：森林列表页**
- 创建 `ForestListPage.vue`
- 实现刷新、查看、删除逻辑
- 样式和用户交互
- 单测：列表加载、删除确认、导航

**步骤3.2：改动计算准备页和森林可视页**
- `ComputePrepPage.vue`: 计算后跳转到列表页
- `ForestPage.vue`: 改为接收svg_id参数
- 单测路由导航

### Phase 4: 全链路测试（第9周）

**步骤4.1：端到端测试**
- 参数输入 → 计算 → 列表 → 可视化 → 删除
- 缓存命中场景
- 数据版本变化后缓存失效

**步骤4.2：性能测试**
- 大SVG文件传输
- 缓存目录有大量文件时的列表速度
- 指纹计算性能

**步骤4.3：文档同步**
- `DESIGN_REST_API.md`: 补充SVG端点和白名单章节
- `TERMS_FIELD_FREEZE.md`: 补充参数规范化规则
- `DESIGN_GUI_WORKSPACE.md`: 说明森林列表页职责

---

## 10. 扩展方向

### 10.1 自动缓存淘汰

**场景**：缓存文件数量或大小超出阈值。

**实现方式**
1. 配置化参数：`SVG_CACHE_MAX_COUNT=100`, `SVG_CACHE_MAX_SIZE_MB=1000`
2. 淘汰策略：LRU（最久未使用） 或 TTL（30天未访问）
3. 触发时机：
   - 计算新SVG时，写入前检查是否超限，若超限执行淘汰
   - 后台定时任务（可选）

**代码示例**
```python
def cleanup_cache_if_needed():
    """检查缓存大小和数量，超限时执行LRU淘汰"""
    cache_dir = Path(CACHE_ROOT)
    snapshots = sorted(
        cache_dir.glob("*.json"),
        key=lambda p: p.stat().st_mtime  # 按修改时间排序
    )
    
    # LRU淘汰：保留最新的N个
    if len(snapshots) > MAX_COUNT:
        for snapshot in snapshots[:-MAX_COUNT]:
            svg_file = snapshot.with_suffix(".svg")
            snapshot.unlink()
            if svg_file.exists():
                svg_file.unlink()
```

### 10.2 参数历史与对比

**场景**：用户想看某个参数集的历史修改，或对比两个森林的差异。

**实现方式**
1. 快照中添加 `parent_svg_id` 和 `diff_from_parent` 字段
2. 森林列表页支持"显示历史链"
3. 对比页面展示参数差异

### 10.3 多工作区缓存隔离

**场景**：用户同时打开多个工作区，缓存应该隔离。

**实现方式**
1. 缓存路径改为 `$WORKSPACE_PATH/.cache/svg/`，而非全局路径
2. 后端启动时从当前工作区目录读取缓存
3. 前端切换工作区时，森林列表自动刷新

### 10.4 缓存导出与导入

**场景**：用户想备份或分享某个森林。

**实现方式**
1. 导出端点：`GET /api/svg/{svg_id}/export` 返回.zip包含快照和SVG
2. 导入端点：`POST /api/svg/import` 接收.zip，解压到缓存目录

### 10.5 远程访问与多用户（未来）

**场景**：Phase 3或更后期，引入远程管理或多用户支持。

**改动点**
1. 白名单改为动态加载（支持热更新或配置文件）
2. 身份认证与授权（OAuth、API Key等）
3. 缓存共享策略（全局vs用户隔离）
4. 审计日志（谁、什么时候、做了什么操作）

---

## 11. 决策与权衡

### 参数哈希后端计算 vs 前端计算

**决策**：后端计算。

**理由**
- 前端作缓存索引不可靠（状态易丢失）
- 后端计算便于溯源和调试
- 支持force_compute覆盖，无需前端介入

### 快照JSON vs 数据库

**决策**：JSON文件。

**理由**
- 单机应用无需数据库复杂性
- 与SVG文件共存，便于备份和分享
- 人可读，便于调试

### 单POST端点 vs 多端点

**决策**：单POST端点 + force_compute标志。

**理由**
- 简化API设计，减少认知负担
- force_compute清晰表达意图
- 避免多端点带来的额外问题（如GET副作用）

### 指纹 vs 版本号

**决策**：指纹。

**理由**
- 无需手动维护版本号
- 自动检测任何文件变化
- 更可靠

---

## 12. FAQ

**Q: 如果参数很复杂（嵌套很深），规范化会很慢吗？**

A: 规范化（JSON序列化+排序）成本很低。即使参数10级嵌套，也是毫秒级。哈希计算（SHA256）略慢，但仍在可接受范围。若性能成瓶颈，可缓存规范化结果。

**Q: 指纹不匹配时，是自动重算还是提示用户？**

A: 自动重算。data_status="stale"时，LIST页面展示"需更新"标记，但不强制用户重算。用户可选择继续看旧版本，或force_compute=true重新生成。

**Q: 多个前端实例同时访问缓存会怎样？**

A: 单机应用通常只有一个前端实例（或浏览器tab）。若有多个实例同时计算同一参数，可能产生竞态（两个都触发计算）。解决方案：临时文件+rename（原子操作）、或计算时加文件锁。初期可忽略，量级不大时不成问题。

**Q: SVG文件太大（100MB+）怎么办？**

A: 这表示计算本身可能有问题（参数导致输出爆炸）。建议：
1. 参数验证时加上下限检查，拒绝明显会导致大文件的参数
2. 计算前估算输出大小，超过阈值拒绝
3. 计算时设超时，防止无限循环

**Q: 白名单改了，代码不改是否可以动态生效？**

A: 初期（第1版）白名单启动时加载，不动态重加载。若要支持动态，需要：
1. 后台watch文件变化，自动重加载
2. 或提供内部调试端点 `/api/__internal__/reload-whitelist`（仅本地开发使用）

推荐初期保持静态，简单可靠。

---

## 13. 版本控制与迭代

**当前版本**：1.0（初版冻结，2026-05-16）

**预计下一版本**：2.0（增加自动淘汰、多工作区隔离）

**关键变更点标记**
- `snapshot_version: "1"` — 快照格式版本
- `whitelist_version: "1"` — 白名单格式版本
- 未来升级需要迁移脚本

---

## 14. 权威文档引用

本文档引用以下权威文档，如有冲突，权威文档优先：

- `repo_memo/DESIGN_REST_API.md` — REST API基础设计
- `repo_memo/TERMS_FIELD_FREEZE.md` — 字段冻结（本文档补充参数规范化规则）
- `repo_memo/DESIGN_GUI_WORKSPACE.md` — GUI工作区设计
- `repo_memo/DOCUMENT_GOVERNANCE.md` — 文档治理规范

若发现冲突，需先更新相关权威文档，再推进实现。
