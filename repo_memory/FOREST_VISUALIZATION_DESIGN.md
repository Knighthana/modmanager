# Forest Visualization Design

## 目标
在少动主干的前提下，为 `compute_mapping` 输出的 `forest` 提供最小可用的视觉表达能力。

## 近期范围
1. 核心模块：`forest_visual`
2. ASCII renderer
3. DOT renderer
4. DOT -> SVG renderer

## 当前不做
1. HTML fragment
2. HTML standalone
3. Plot renderer
4. GUI hover 整链高亮
5. 分叉节点超链接与用户选枝交互
6. 浏览器 fallback
7. 外部 annotator / transformer / custom visualizer 插件运行链

## 输入边界
1. 输入只读 `forest`，来源于 `compute_mapping` 输出。
2. 近期仅依赖最小必需字段：
   - `ForestNode.path`
   - `ForestNode.changerequest`
   - 可选 `ForestNode.destin_mixed_id`
   - 可选 `ForestNode.warning`
   - 可选 `ForestNode.candidates`
3. 不修改现有 `output_schema`。

## 输出边界
1. `ascii`：输出文本到 stdout 或文件。
2. `dot`：输出 DOT 文本到 stdout 或文件。
3. `svg`：通过 DOT 渲染得到 SVG 文件。

## 错误码建议
1. `0`：成功。
2. `2`：输入无效（JSON 或结构不合法）。
3. `3`：格式不支持。
4. `4`：外部依赖缺失（如 `dot` 不可用）。
5. `5`：渲染失败（内部异常）。
6. `6`：输出写入失败。

## 模块分层
1. `forest_visual` 核心模块负责：
   - 读取与规范化 `forest`
   - 构建中间图模型
   - 调度具体 renderer
2. ASCII renderer 负责文本树状输出。
3. DOT renderer 负责 Graphviz DOT 文本输出。
4. DOT -> SVG renderer 负责从 DOT 产出 SVG。

## 数据流（冻结）
1. 读取 JSON 并提取 `forest`。
2. 执行最小字段校验（`path` 与 `changerequest`）。
3. 标准化为中间图模型 `GraphModel`。
4. 按格式渲染：
   - `ascii`: `GraphModel -> text`
   - `dot`: `GraphModel -> dot`
   - `svg`: `GraphModel -> dot -> svg`

## 中间图模型（最小字段）
1. `nodes`：目标路径节点索引。
2. `edges`：由 `changerequest` 派生的边。
3. `branching_nodes`：`W_FOREST_BRANCHING` 节点集合。
4. `raw_node_ref`：原始节点引用。
5. `extra`：未知扩展字段容器（用于 trace/meta 兼容）。

## 兼容性原则
1. 可视化模块不得把输入绑定死到当前最小字段集合之外。
2. 未来 M1 patch 可能在 `forest` / `changerequest` 中增加 trace/meta 标签。
3. 出现未知扩展字段时：
   - 不报结构错误
   - 不丢弃原始信息
   - 允许透传到中间图模型，供后续 renderer 使用

## 里程碑排期
1. 近期：core + ASCII + DOT + DOT -> SVG。
2. M3：HTML fragment、HTML standalone、Plot renderer、trace/meta 扩展字段兼容验证。
3. M4：GUI 交互、高亮、超链接、用户选枝、插件运行链、老浏览器 fallback。

## 设计约束
1. 不改 `compute_mapping` 行为。
2. 不改 `forest` 当前 schema。
3. 先实现“让人能看见形状”，再进入 GUI 交互层。

## 预排查坑位（开工前逐条确认）
1. 分叉语义不可丢失：ASCII 与 DOT 必须显式标记分叉节点。
2. `delete` 哨兵路径（`!`）不可按普通路径处理。
3. DOT 需处理路径转义（引号、反斜杠、中文、换行）。
4. Python 依赖存在不代表系统 `dot` 可执行文件可用。
5. SVG 失败不能影响 ASCII/DOT 可用性。
6. `final_mapping` 为空时，`forest` 仍需可视化。
7. 未知扩展字段不能触发硬失败。

## Go / No-Go 门槛
### Go
1. 近期范围与延期范围无冲突。
2. 输入最小字段与扩展兼容策略已冻结。
3. 错误码与降级策略已冻结。
4. 验收用例已落盘。

### No-Go
1. 文档仍包含“本期实现 HTML/GUI 交互”的表述。
2. 计划要求改动 `compute_mapping` 或 `output_schema`。
3. 未定义分叉与 `delete` 哨兵展示规则。

## 最小验收用例
1. 空 `forest`：ASCII 与 DOT 可输出，SVG 给出空图或友好提示。
2. 单节点单请求：ASCII 结构正确，DOT 可被 `dot` 解析。
3. 分叉节点：ASCII 与 DOT 都能识别分叉。
4. 含 `delete` 哨兵：渲染不崩溃且语义可见。
5. 含未知字段：渲染成功，扩展字段保留在中间模型可访问范围。
6. 无 `dot` 环境：ASCII/DOT 可用，SVG 返回依赖缺失错误码。