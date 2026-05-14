# Replace Service Design

> Status: future
> Authority: reference-only
> Read-Tier: on-demand
> Purpose: 记录替换执行层独立化的远期方案，供未来规划与演进预留参考

## 目标
提供一个只负责“替换执行”的接口层，保持单一职责。

## 非目标
- 不负责备份绑定
- 不负责凭证校验
- 不负责配置解析
- 不负责历史映射裁决

## 输入（建议）
- `resolved_mapping`：上游已决议好的替换映射
- `options`：dry-run、日志开关等执行级参数

## 输出（建议）
- `ok`、`applied`、`skipped`、`errors`
- 可选执行报告（统计与耗时）

## 历史映射影响处理
- replace_service 本身不判断“应使用 A 还是 E”。
- 上游历史映射解析层先给出“当前有效源”，replace_service 仅执行该决议。

## 与 backup 的关系
- replace_service 不直接调用 backup。
- 若业务需要“先备份再替换”，由编排层在调用前串联。

## 落地策略
1. 先以 M1 外模块实现，适配现有 CLI/HMI。
2. 稳定后再评估并入 M1 或保留为独立执行层。
