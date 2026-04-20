# Process Description (repo_memory authoritative)

这是当前阶段的执行总览文档，用于替代 `description/process_description.md` 的指挥作用。

## 业务目标
- 基于 Steam 库与工坊文件建立可计算的映射关系
- 对改动进行可追溯备份与恢复
- 在跨平台路径环境（Windows/Linux/WSL）下保持一致行为

## Discovery Pipeline
1. 定位候选 `steamapps` 路径
2. 标记 `contains_libraryfolders_vdf=true` 的主发现点
3. 解析主 `libraryfolders.vdf` 扩展全部库路径
4. 遍历每个库解析 `appmanifest_*.acf`
5. 默认仅对 `steamlib[].game` 范围内 appid 解析 `appworkshop_*.acf`
6. 生成 `database` 结构并保存

## 数据契约分工
- 术语冻结：`TERMINOLOGY.md`
- 扫描契约：`STEAM_DISCOVERY.md`
- 字段定义：`DATABASE_FIELDS.md`
- 示例数据：`*.example`
- 执行指令：`IMPLEMENTATION_BRIEF.md`

## 关键约束
- 单概念单字段名，禁止历史别名继续落库
- 文档先于实现：先冻结契约，再改代码
- 测试必须覆盖跨盘库发现，不允许仅验证默认安装位置

## 当前阶段任务
1. 文档对齐完成
2. 实现按契约回收
3. 测试补齐集成断言
