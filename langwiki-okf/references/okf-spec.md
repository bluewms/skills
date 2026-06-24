# OKF v0.1 规范摘要

> 译自 [OKF SPEC.md](https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md)
> 本文件是规范的精简摘要，供快速查阅。

## 核心理念

OKF 是一种开放的、对人和智能体都友好的知识表示格式。设计目标：

- 对人**可读**，无需工具（能 `cat` 就能读）
- 对智能体**可解析**，无需定制 SDK
- 在版本控制中**可 diff**
- 跨工具、跨组织、跨时间**可移植**

格式刻意极简：**一个目录，里面是带 YAML 头信息的 Markdown 文件**。没有 schema
注册表，没有中央权威，不需要任何工具链。

## 术语

| 术语 | 定义 |
|------|------|
| 知识包 (Bundle) | 自包含的、层级化的知识文档集合。分发的基本单位。 |
| 概念 (Concept) | 包内一个知识单元，表示为一份 Markdown 文档。 |
| 概念 ID | 概念文件在包内的路径，去掉 `.md` 后缀。如 `tables/users.md` → `tables/users`。 |
| 头信息 (Frontmatter) | Markdown 文件顶部由 `---` 界定的 YAML 元数据块。 |
| 正文 (Body) | 头信息之后的全部内容。 |
| 链接 (Link) | 从一个概念指向另一个概念的标准 Markdown 链接。 |
| 引用 (Citation) | 从一个概念指向外部来源的链接。 |

## 包结构

```
path/to/bundle/
├── index.md          # 可选。目录清单，支持渐进式展开。
├── log.md            # 可选。变更时间线历史。
├── <concept>.md      # 包根目录下的一个概念。
└── <subdirectory>/   # 子目录分组。
    ├── index.md
    └── <concept>.md
```

分发方式：git 仓库（推荐）、tarball/zip、更大仓库的子目录。

### 保留文件名

| 文件名 | 用途 |
|--------|------|
| `index.md` | 目录清单（§6） |
| `log.md` | 更新历史（§7） |

**禁止**将保留文件名用作概念文档。

## 概念文档

每个概念是 UTF-8 Markdown 文件，由两部分组成：
1. YAML 头信息块（`---` 界定）
2. Markdown 正文

### 头信息字段

```yaml
---
type: <类型名>              # 必须。短字符串，标识概念种类。
title: <显示名>             # 推荐。人类可读名称。
description: <一句话摘要>    # 推荐。用于 index.md 和搜索摘要。
resource: <资产 URI>        # 推荐。底层资产的规范 URI。
tags: [标签1, 标签2]        # 可选。横切分类。
timestamp: <ISO 8601>       # 可选。最后修改时间。
# 其他自定义键值对          # 允许。消费者应保留未知键。
---
```

**唯一硬要求：** `type` 非空。

`type` 取值不做中央注册。示例：`BigQuery Table`、`API Endpoint`、`Metric`、
`Playbook`、`PDF Document`、`Word Document`、`Config File` 等。

### 正文章节（约定标题）

| 标题 | 用途 |
|------|------|
| `# Schema` | 对资产的列/字段的结构化描述。 |
| `# Examples` | 具体的使用示例。 |
| `# Citations` | 支撑正文论断的外部来源。 |

正文无必须章节，应偏好结构化 Markdown（标题、列表、表格、代码块）。

### 示例：绑定资源的概念

```markdown
---
type: BigQuery Table
title: Customer Orders
description: One row per completed customer order across all channels.
resource: https://console.cloud.google.com/bigquery?p=acme&d=sales&t=orders
tags: [sales, orders, revenue]
timestamp: 2026-05-28T14:30:00Z
---

# Schema

| Column        | Type      | Description                              |
|---------------|-----------|------------------------------------------|
| `order_id`    | STRING    | Globally unique order identifier.        |
| `customer_id` | STRING    | Foreign key into [customers](/tables/customers.md). |
| `total_usd`   | NUMERIC   | Order total in US dollars.               |

# Citations

[1] [BigQuery table schema](https://console.cloud.google.com/bigquery?p=acme&d=sales&t=orders)
```

## 交叉链接

两种形式：

1. **绝对（包内相对）链接** — 以 `/` 开头，相对于包根。推荐形式。
   ```markdown
   See the [customers table](/tables/customers.md).
   ```

2. **相对链接** — 标准 Markdown 相对路径。
   ```markdown
   See the [neighboring concept](./other.md).
   ```

链接是**无类型**的——关系种类由周围散文表达。消费者**必须**容忍坏链接。

## 索引文件 (index.md)

不含头信息（除非在包根目录声明 `okf_version`）。用章节分组枚举内容：

```markdown
# Section Heading

* [Title 1](relative-url-1) - short description
* [Title 2](relative-url-2) - short description
```

条目应带上所链概念的 `description`。

## 日志文件 (log.md)

按日期分组、最新在前的扁平列表，日期用 ISO 8601 `YYYY-MM-DD`：

```markdown
## 2026-05-22

* **Update**: Added new table reference for [Customer Metrics](/tables/customer-metrics.md).
* **Creation**: Established the [Dataplex Playbook](/playbooks/dataplex.md).
```

## 引用 (Citations)

正文中源自外部材料的论断，列在 `# Citations` 下并编号：

```markdown
# Citations

[1] [Source Title](https://example.com/...)
[2] [Another Source](https://example.com/...)
```

## 符合性（OKF v0.1）

一个包**符合** OKF v0.1，当且仅当：

1. 目录树中每个非保留的 `.md` 文件，都含有可解析的 YAML 头信息块。
2. 每个头信息块都含有一个非空的 `type` 字段。
3. 每个保留文件名（`index.md`、`log.md`）在出现时，分别遵循对应结构。

消费者**绝不可**因为以下原因拒绝包：缺少可选字段、未知 `type`、未知额外键、
坏链接、缺少 `index.md`。

> 整份规范的硬要求核心就这三条。门槛几乎为零——任何带 `type` 的 `.md` 都合规。
> 互操作靠的是约定与作品质量，而非校验器。

## i18n 扩展（向后兼容提案）

基于"生产者可加入任意额外键"，提出多语言约定：

```yaml
---
type: BigQuery Table
title: 订单表
lang: zh                        # BCP 47 语言标签
canonical: /tables/orders.md    # 指向主语言版本
---
```

完全向后兼容：不认识 `lang`/`canonical` 的消费者按 §4.1 忽略未知键即可。
`reference-agent` 的语言自动匹配功能会根据源内容语言自动选择输出语言。
