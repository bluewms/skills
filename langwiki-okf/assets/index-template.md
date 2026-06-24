# 目录分组标题

* [概念标题1](relative-url-1.md) - 概念的一句话描述
* [概念标题2](relative-url-2.md) - 另一个概念的描述

# 另一个分组

* [子目录](subdir/) - 子目录的描述
* [概念标题3](subdir/concept3.md) - 子目录中的概念

# 注意事项

- index.md 不含头信息（除非在包根目录声明 okf_version）
- 条目应带上所链概念头信息中的 description
- 使用相对于当前目录的相对路径
- 每个目录可以有自己的 index.md

## 包根 index.md 示例（带 okf_version）

```yaml
---
okf_version: "0.1"
---
```

放在文件最顶部，然后是正文内容。
