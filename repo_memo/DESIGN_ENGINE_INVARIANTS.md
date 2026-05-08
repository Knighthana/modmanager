# 引擎核心不变量

> 来源：repo_logs/2026-04-21_M1_EXECUTION_CONTRACT.md，经 P0 后更新

## 数据结构不变量
- `mixed_id` 格式：`appid:modid`（colon-separated）
- `hashtype` 当前仅支持 `sha256`
- final_mapping 只允许单文件到单文件，不允许通配符残留

## 行为不变量
- 文件级环检测：基于具体文件链路，mod 级依赖环不直接判错
- 森林允许分枝，分枝需告警（W_FOREST_BRANCHING）并等待用户决策
- 同输入同输出（确定性）

## 路径约定
- workingpathstyle 与 steamlibpathstyle 不一致时，先统一路径风格再参与计算
- 目录路径必须以 / 结尾，文件路径不得以 / 结尾（path_resolver 门禁）
