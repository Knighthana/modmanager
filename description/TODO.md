TODO LIST
=========

# untracked tag in rules

应该允许放一些不解析的标签进tag，毕竟在自动化kmmrule.json的编辑器做出来之前，这玩意都得手写；

累死了；

但有一点是确认的，那就是要用的名字必须统一；

# convert action to changerequest

对于`replace`操作，当所指向的目标文件不存在时，应该在changerequst中标记这是一个create操作

# rule_set.json

## preview应该用列表

`aggregated_rule_set.json`的`mod[].preview`应该用列表而不是一个字符串段；

到时候WebUI做轮换展示；

## delete方法

应该允许在"action"中直接使用`delete`作为操作方法；

既然`from`计划被做成表，那么应该用`from`列表表示需要删除的文件；

`into`字段填`void`，算作`delete`的规范；

应该特别注意，解析`delete`的行动是将`from`作为目标的`path`，给目标挂一个类型为`delete`的`changerequest`的

# action rule comlex

## `"from"` list

应该考虑把`action`的`from`做成列表，这样可以少写好几次`action`；

## revert select

如果整个`from`目录中只有少数几个文件或者目录是“不需要搬移的”，

应该引入“排除式写法”的支持？

除了某几个文件以外，选中其他所有文件？

# customized operations

这两个方案涉及到脚本调用，脚本调用是一个危险的操作；

而且脚本调用很复杂，比如环境变量传谁的？支持自定义配置吗，那是写一个公共规则，还是按照脚本配置？

但是这个工具默认用户具有计算机常识，并且rule和脚本原本就只由资深用户撰写；

因此可以考虑作为“未来能够支持的功能”

## customized restore function

有时候modder自己已经提供了备份方法，

这时候我们可以写一些调用规则来满足modder自己提供的备份方案；

最简单的restore action是把modder提供的“还原”文件再覆盖到指定位置；

还有一些restore action是……删除某些文件？

但是从哪里拿到这个文件是从哪来的信息呢？

## customized install function

有时候一些mod在安装完之后需要手动调取脚本；

不然base或者其他mod不吃修改；

比如某些汉化mod；

如果能增加一个执行自定义脚本的功能，这样的话modder只需要把rule放在content页面，让用户复制粘贴就好；

# base64导入规则

WebUI上面可以弄个textarea，允许用户把特定的base64编码粘贴在这里；

decode之后可以获取原始的rule；

可以选择保存rule以供未来继续使用，或者仅本次使用；

随便，这都是UI上的事情；得到相当后期才轮到考虑了；

# 
