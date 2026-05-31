# DESIGN_CONFIG_INDEX_PROTOCOL — config_index 传输协议

> Status: active
> Authority: authoritative
> Read-Tier: task-scoped
> Purpose: 规定 `config_index` 从前端到后端的传输方式——HTTP Header，不污染 URL 和请求体
> 创建: 2026-05-23

---

## 一、原则

`config_index` 是前后端之间的**透传索引**。前端存储，后端消费。不应出现在 URL query 或 JSON body 中。

## 二、传输方式

### 2.1 HTTP Header

所有 API 请求（GET / POST）必须携带：

```
X-UserConfig-Index: {"type":"path","string":"/home/user/.config/kmm/user_config.json"}
```

Header 值是 `config_index` 对象的 JSON 序列化字符串。保留 `type` 字段以支持未来扩展（如 `{"type":"url","string":"https://..."}`）。

### 2.2 前端注入

`apiGet` / `apiPost` / `streamSse` 在发出请求前按以下流程处理 `configIndex`：

1. 先读 sessionStorage（键：`modmanager:configIndex`）。
2. 若 sessionStorage 为空，则读 localStorage；若 localStorage 有值，先写回 sessionStorage，再从 sessionStorage 读取用于组装 header。
3. 若 sessionStorage 与 localStorage 都为空，前端调用 `GET /api/os/defaults` 获取默认 `userconfig_index`，并写穿到 sessionStorage + localStorage。
4. 后续请求只从 sessionStorage 读取并注入 `X-UserConfig-Index`。

说明：`/api/os/defaults` 仅提供默认值，前端无需感知后端内部路径推导细节。

### 2.3 后端提取

新增 FastAPI 依赖函数 `get_config_index()`，从请求 header 中提取并解析：

```python
from fastapi import Header, HTTPException

def get_config_index(
    x_userconfig_index: str = Header(..., alias="X-UserConfig-Index"),
) -> str:
    try:
        obj = json.loads(x_userconfig_index)
        return obj.get("string", "")
    except (json.JSONDecodeError, TypeError):
        raise HTTPException(status_code=400, detail="Invalid X-UserConfig-Index header")
```

返回 resolved 后的**文件路径字符串**，直接传给 `discover_user_config(config_index=...)`。

## 三、受影响范围

### 3.1 前端

| 文件 | 改动 |
|------|------|
| `client.ts` | `apiPost`/`apiGet`：加 header，删 body/query 注入 |
| `sse.ts` | `streamSse`：加 header，删 body 注入 |

### 3.2 后端

| 文件 | 改动 |
|------|------|
| `routes/config.py` | `discover_config`：用 `get_config_index()` 替代 body 中的 `config_index` |
| `routes/database.py` | 所有端点：用 `get_config_index()` 替代 body 中的 `config_index` |
| `routes/workspace.py` | `workspace_compute` 等：删 `config_index: str = Query(...)`，改用 `get_config_index()` |
| `routes/pipeline.py` | 同上 |
| `routes/rules.py` | 同上 |
| `schemas.py` | 所有 request schema：删 `config_index` 字段 |

### 3.3 不受影响

- `sessionStorage` / `localStorage` 的存储格式不变
- 前端其他页面对 `configIndex` 的使用不变
- `resolve_config_index()` 辅助函数仍然有用（parse header 值）

## 四、不变式

- `config_index` 对象的 JSON 序列化形式**仅**出现在 `X-UserConfig-Index` header 中
- URL query 和 JSON body 中**不再**包含 `config_index`
- 后端端点函数签名中**不再**有 `config_index` 参数
- 业务流程后端不猜测 `config_index`；仅消费 header 解析结果
