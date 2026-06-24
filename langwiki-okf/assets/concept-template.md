---
type: <ConceptType>              # 必须。如 BigQuery Table / PDF Document / API Endpoint
title: <显示名称>                 # 推荐。人类可读的显示名
description: <一句话摘要>         # 推荐。用于 index.md 和搜索摘要
resource: <资源URI>              # 可选。底层资产的规范 URI
tags: [标签1, 标签2]             # 可选。横切分类
timestamp: <ISO8601时间>         # 可选。最后修改时间，如 2026-06-23T12:00:00Z
# lang: zh                       # 可选。BCP 47 语言标签（i18n 扩展）
# canonical: /path/to/canonical  # 可选。指向主语言版本（i18n 扩展）
---

# 概述

1-3 段散文描述，说明这个概念是什么、代表什么、通常如何使用。

# Schema

如果概念有结构化字段，用表格描述：

| 字段名    | 类型   | 说明                        |
|----------|--------|----------------------------|
| `field1` | STRING | 字段说明                    |
| `field2` | NUMBER | 另一个字段                  |

# Examples

具体的使用示例，用围栏代码块：

```python
# 示例代码
```

# Citations

支撑正文论断的外部来源，编号列出：

[1] [来源标题](https://example.com/source1)
[2] [另一来源](https://example.com/source2)
