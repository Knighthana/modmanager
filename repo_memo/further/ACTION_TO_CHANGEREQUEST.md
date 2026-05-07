# Action → Changerequest 语义转换

> 状态：远期，待明确

## 问题

`action`（用户在规则中声明的操作意图）和 `changerequest`（引擎内部使用的映射条目）当初分开设计，因为实际转化后不一定彻底对齐。

示例：用户声明 `action: "replace"`，但目标文件不存在时，语义上更接近 `create`。

## 待决策

1. `action` 的完整枚举及相互转换规则
2. `changerequest` 的字段规范（目前由引擎隐式构建）
3. 哪些 action 在何种条件下转换为哪种 changerequest

## 与 Schema 的关系

此处依赖数据 Schema 的明确定义（TODO-14）。Schema 确定后，转换规则可据此固化。
