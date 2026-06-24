# reference-agent CLI 完整参考

## 命令总览

| 命令 | 用途 |
|------|------|
| `localfile` | 从本地文件生成 OKF 包（快捷命令，最常用） |
| `enrich` | 从指定数据源生成 OKF 包（完整命令） |
| `visualize` | 为 OKF 包生成交互式 HTML 图谱 |
| `list-models` | 列出支持的 LLM 模型预设 |

## no-clone 启动（vendor 内置）

```bash
cd .codebuddy/skills/langwiki-okf
bash scripts/bootstrap_local.sh
scripts/reference-agent --help
```

说明：
- 默认优先使用 `scripts/reference-agent`（包装器）
- `agent_pipeline.py` 会优先调用该包装器，缺失时回退系统 `reference-agent`

---

## agent_pipeline.py（Agent 编排）

用于把“LLM 处理”与“执行流程”拆分，并支持三种模式：

```bash
python scripts/agent_pipeline.py --input /path/to/docs --out ./okf-bundle --mode auto
```

### 参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--input` | *(必填)* | 输入目录 |
| `--out` | *(必填)* | 输出目录 |
| `--pattern` | `**/*` | 文件匹配 glob |
| `--mode` | `auto` | `cli` / `api` / `auto` |
| `--model` | *(可选)* | 指定模型名 |
| `--max-chars` | `20000` | 单文件最大输入字符 |
| `-v, --verbose` | *(关闭)* | 详细日志 |

### API 模式环境变量

| 变量 | 必填 | 说明 |
|------|------|------|
| `OKF_API_BASE` | 是 | OpenAI 兼容 API Base URL |
| `OKF_API_KEY` | 是 | API Key |
| `OKF_API_MODEL` | 否 | 默认模型（未传 `--model` 时生效） |

---

## localfile

`enrich --source localfile --no-web` 的快捷方式，带位置参数和合理默认值。

### 语法

```bash
reference-agent localfile [path] [options]
```

### 参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `path` | `.`（当前目录） | 要扫描的本地目录（位置参数，可选） |
| `--pattern` | `**/*` | 文件匹配 glob 模式 |
| `-o, --out` | `./okf-bundle` | 输出目录 |
| `--model` | `gemini-flash-latest` | LLM 模型 ID |
| `--no-recursive` | *(关闭)* | 禁用递归扫描 |
| `--api-url` | *(无)* | 同时获取远程文件 URL（可重复，混合模式） |
| `--api-token` | *(无)* | 远程 URL 的 Bearer token（或设 `API_AUTH_TOKEN`） |
| `--concept` | *(全部)* | 仅处理指定概念 ID（可重复） |
| `-v, --verbose` | *(关闭)* | 详细日志 |

### 示例

```bash
# 最简形式
reference-agent localfile

# 指定目录和文件类型
reference-agent localfile /path/to/docs --pattern "**/*.pdf"

# 指定输出和 LLM
reference-agent localfile /path/to/docs \
  --pattern "**/*.{pdf,docx,md}" \
  --model deepseek/deepseek-chat \
  -o ./my-bundle

# 混合本地 + 远程
reference-agent localfile /local/docs \
  --pattern "**/*.pdf" \
  --api-url https://example.com/remote.pdf \
  -o ./mixed-bundle

# 仅处理特定概念
reference-agent localfile /path --concept "docs_api_guide"

# 非递归扫描
reference-agent localfile /path --pattern "**/*.pdf" --no-recursive
```

### 自动跳过的目录

`.git`、`.venv`、`node_modules`、`__pycache__`、`.pytest_cache`、`dist`、
`build`、`.idea`、`.vscode`、`okf-bundle`

### 单文件上限

10MB（`max_file_size = 10 * 1024 * 1024`）

---

## enrich

从指定数据源生成 OKF 包的完整命令。

### 语法

```bash
reference-agent enrich --source <source> --out <dir> [options]
```

### 通用参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--source` | *(必填)* | 数据源：`bq` / `localfile` / `api` |
| `--out` | *(必填)* | 输出目录 |
| `--model` | `gemini-flash-latest` | LLM 模型 ID |
| `--concept` | *(全部)* | 仅处理指定概念 ID（可重复） |
| `--no-web` | *(关闭)* | 跳过 Web 爬取轮 |
| `-v, --verbose` | *(关闭)* | 详细日志 |

### BigQuery 源 (`--source bq`)

| 参数 | 说明 |
|------|------|
| `--dataset` | BigQuery 数据集 ID（`project.dataset` 格式，必填） |
| `--billing-project` | 计费项目（默认用 ADC 默认项目） |

### 本地文件源 (`--source localfile`)

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--local-path` | *(必填)* | 本地目录路径 |
| `--local-pattern` | `**/*` | 文件 glob 模式 |
| `--local-no-recursive` | *(关闭)* | 禁用递归 |

### API 源 (`--source api`)

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--api-url` | *(无)* | 文件 URL（可重复） |
| `--api-endpoint` | *(无)* | API 端点，返回 JSON 文件列表 |
| `--api-url-field` | `url` | JSON 中文件 URL 的字段名 |
| `--api-url-file` | *(无)* | URL 列表文件路径（每行一个 URL） |
| `--api-token` | *(无)* | Bearer token（或设 `API_AUTH_TOKEN`） |

### Web 爬取参数（enrich 专用）

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--web-seed` | *(无)* | 种子 URL（可重复） |
| `--web-seed-file` | *(无)* | 种子 URL 文件（可重复） |
| `--web-max-pages` | `100` | 最大爬取页数 |
| `--web-allowed-host` | *(仅种子主机)* | 额外允许的主机（可重复） |
| `--web-allowed-path-prefix` | *(无限制)* | URL 路径前缀白名单（可重复） |
| `--web-denied-path-substring` | *(无)* | URL 路径黑名单子串（可重复） |
| `--web-max-depth` | `2` | 从种子的最大跳数 |

### 示例

```bash
# BigQuery 数据源
reference-agent enrich --source bq \
  --dataset my-project.sales \
  --out ./bq-bundle

# 本地文件（等价于 localfile 命令）
reference-agent enrich --source localfile \
  --local-path /path/to/docs \
  --local-pattern "**/*.pdf" \
  --out ./bundle --no-web

# API 源 — 直接 URL
reference-agent enrich --source api \
  --api-url https://example.com/doc1.pdf \
  --api-url https://example.com/doc2.docx \
  --out ./bundle --no-web

# API 源 — 端点模式
reference-agent enrich --source api \
  --api-endpoint https://api.example.com/files \
  --api-url-field download_url \
  --api-token <token> \
  --out ./bundle --no-web

# API 源 — URL 列表文件
reference-agent enrich --source api \
  --api-url-file urls.txt \
  --out ./bundle --no-web

# 带 Web 爬取（BigQuery + 网页丰富）
reference-agent enrich --source bq \
  --dataset my-project.sales \
  --web-seed https://example.com/docs \
  --web-max-pages 50 \
  --out ./enriched-bundle
```

---

## visualize

为 OKF 包生成 self-contained 交互式 HTML 知识图谱。

### 语法

```bash
reference-agent visualize --bundle <dir> [options]
```

### 参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--bundle` | *(必填)* | OKF 包根目录 |
| `--out` | `<bundle>/viz.html` | 输出 HTML 路径 |
| `--name` | 包目录名 | 显示名称 |

### 示例

```bash
reference-agent visualize --bundle ./my-bundle
reference-agent visualize --bundle ./my-bundle --out ./graph.html --name "My Knowledge Base"
```

---

## list-models

列出所有预设的 LLM 模型。

```bash
reference-agent list-models
```

输出示例：

```
支持的 LLM 模型预设：

  [google]
    gemini-flash-latest                      Google Gemini，默认模型
    gemini-2.0-flash                         Google Gemini 2.0 Flash

  [anthropic]
    claude-sonnet-4                          Anthropic Claude Sonnet 4
    ...
```

---

## 概念 ID 规则

文件路径转换为概念 ID 的规则：
- 去掉文件扩展名
- 路径分隔符变为概念 ID 的层级
- 空格替换为 `_`，连字符替换为 `_`
- 支持 Unicode（中文/日文等文件名）

示例：
- `/docs/api-guide.md` → 概念 ID `docs/api_guide`
- `/src/index.ts` → 概念 ID `src/index`
- `/文档/ERP百科.pdf` → 概念 ID `文档/ERP百科`
