# M1 Execution Contract (Summary)

来源：/memories/session/m1_spec.md
更新时间：2026-04-21

## M1 不变量
1. final mapping 只允许单文件到单文件，不允许通配符残留。
2. 环检测基于具体文件链路，mod 级依赖环不直接判错。
3. 森林允许分枝，但分枝必须告警并等待用户决策。
4. hashtype 当前仅支持 sha256。

## 输入与路径约束
1. mixed_id 必须是 appid:modid。
2. workingpathstyle 与 steamlibpathstyle 不一致时，先统一路径风格再参与计算。
3. selection 为空时禁止触发 filemap 计算。

## 错误与告警（执行级）
- E_AGGREGATED_RULE_SET_INVALID_RULE
- E_CONFIG_UNEXPANDABLE_GLOB
- E_ENV_SELECTION_EMPTY
- E_ENV_PATH_NOT_FOUND
- E_FILE_CIRCULAR_DEP
- W_FOREST_BRANCHING

## 验收关键点
1. 输出无通配符。
2. 文件级防环有效。
3. 分枝可识别并可决策。
4. 同输入同输出。
