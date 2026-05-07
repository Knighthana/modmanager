# 远期功能储备

## kmm_rule 生成器

提供一个用户友好的 kmm_rule 编辑器/生成器，降低手写规则的门槛和出错率。

## revert select（排除式选择）

`from` 目录中只有少数文件不需要搬移时，支持排除式写法："除了某几个文件以外，选中其他所有文件"。

## Base64 导入规则

WebUI 提供 textarea，允许粘贴 base64 编码的规则，decode 后可选持久化保存或仅本次使用。

## 自定义脚本调用

mod 安装前后可能需要执行自定义脚本（如汉化 mod 需调取脚本才能让 base 吃修改）。支持在规则中声明脚本调用，由资深用户撰写。

- customized restore function
- customized install function

当前状态：Pending，仅为未来扩展方向保留。
