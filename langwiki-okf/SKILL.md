---
name: langwiki-okf
description: "从本地文件（PDF/Word/Excel/PPT/Markdown/代码等 16 种格式）或远程 API 使用 reference-agent 生成 OKF（开放知识格式）知识包时使用此 skill。涵盖环境配置、多 LLM 选择（Gemini/Claude/OpenAI/DeepSeek/通义千问/Ollama）、localfile/enrich/visualize 命令、中文文件名与语言自动匹配、OKF 包验证和故障排查。当用户需要将文档批量转换为 AI 可读的结构化知识库、生成 OKF bundle、使用 reference-agent 工具、或询问 OKF 格式规范时触发。"
---

# LangWIKI OKF

## Overview

本 skill 封装了基于 Google Knowledge Catalog 扩展的 `reference-agent` 工具，
指导如何将本地文件和远程资源批量转换为 **OKF（Open Knowledge Format）知识包**。
OKF 是一种开放的、对人和 AI 智能体都友好的知识表示格式——一个目录，里面是带 YAML
头信息的 Markdown 文件，可由人撰写、可由智能体生成、可跨组织交换。

核心能力：
- 从 16 种文件格式（PDF/Word/Excel/PPT/Markdown/代码/配置/HTML/CSV）生成 OKF 知识包
- 支持远程 API 数据源和本地+远程混合模式
- 多 LLM 后端：Gemini/Claude/OpenAI/DeepSeek/通义千问/Ollama
- Unicode 文件名支持（中文/日文等）+ 语言自动匹配
- 生成交互式 HTML 知识图谱
- 提供 `scripts/agent_pipeline.py`：将“大模型处理”与“执行流程”解耦，支持 `cli/api/auto` 三种编排模式

## Prerequisites

### 0) 默认 no-clone（推荐）

本 skill 已内置 `vendor/reference_agent`，无需 `git clone knowledge-catalog`。

```bash
cd .codebuddy/skills/langwiki-okf
bash scripts/bootstrap_local.sh
```

`bootstrap_local.sh` 会：
- 自动选择 Python 3.11+
- 安装 `scripts/requirements-vendor.txt`
- 生成本地包装器 `scripts/reference-agent`

### 1) 验证本地 CLI 入口

```bash
.codebuddy/skills/langwiki-okf/scripts/reference-agent list-models
```

如需全局调用，可加入 PATH：

```bash
export PATH="$(pwd)/.codebuddy/skills/langwiki-okf/scripts:$PATH"
```

### 2) LLM 与 API Key 约定（单一逻辑）

- API 编排路径统一要求用户先配置 skill 变量：`OKF_API_MODEL`、`OKF_API_BASE`、`OKF_API_KEY`。
- 未配置时必须先提示用户执行配置命令；可重复执行同一组 `export` 覆盖旧值。
- 不再依赖会话默认模型，也不回退到 `OPENAI_*` / `CODEBUDDY_*` 环境变量。

## Workflow

### Step 0: 选择执行编排模式（推荐先选）

```bash
# auto：优先 CLI，失败自动回退到 API
python scripts/agent_pipeline.py \
  --input /path/to/docs \
  --pattern "**/*.pdf" \
  --out ./okf-bundle \
  --mode auto

# api：完全不依赖 reference-agent CLI
export OKF_API_BASE=https://api.openai.com/v1
export OKF_API_KEY=<your-key>
python scripts/agent_pipeline.py \
  --input /path/to/docs \
  --pattern "**/*.pdf" \
  --out ./okf-bundle \
  --mode api
```

说明：`agent_pipeline.py` 会把“文档提取/Prompt 构建/模型调用/结果落盘/OKF 校验”拆分执行，便于由 Agent 统一编排和回退。

### Step 1: 选择数据源与 LLM

根据源数据位置和可用 LLM，选择合适的命令和参数。参见
`references/cli-reference.md` 获取完整参数说明，`references/llm-models.md`
获取模型配置，`references/file-types.md` 获取支持的文件格式。

**数据源决策表：**

| 场景 | 命令 | 说明 |
|------|------|------|
| 本地文件 | `localfile <path>` | 最常用，一行命令完成 |
| 远程文件 URL | `enrich --source api --api-url` | 直接下载远程文件 |
| API 端点返回文件列表 | `enrich --source api --api-endpoint` | 批量获取 |
| URL 列表文件 | `enrich --source api --api-url-file` | 从文件读取 URL |
| 本地 + 远程混合 | `localfile <path> --api-url` | 合并处理 |

**LLM 选择指南：**

- **统一默认来源**：`OKF_API_MODEL`（可被 `--model` 覆盖）。
- 切换模型时，优先修改 `OKF_API_MODEL`；也可临时用 `--model`。
- 若缺少模型或凭据，先提示用户执行 `export OKF_API_*` 配置命令。
| 需求 | 推荐模型 | 备注 |
|------|---------|------|
| 默认稳定 | 当前 Agent 模型 | 零额外配置，推荐优先使用 |
| 国内可用、性价比 | `deepseek/deepseek-chat` | 需要时通过 `--model` 切换 |
| 完全离线 | `ollama/qwen2.5:7b` | 仅本机自托管场景需要 `ollama serve` |
| 高质量推理 | `claude-sonnet-4` | 本机独立运行时按参考文档配置 |
| 中文与综合能力 | `openai/qwen-plus` | 本机独立运行时按参考文档配置 |

### Step 2: 生成 OKF 知识包

#### 本地文件（最常用）

```bash
# 最简形式：扫描当前目录
reference-agent localfile

# 指定目录和文件类型
reference-agent localfile /path/to/docs --pattern "**/*.pdf"

# 指定输出目录和 LLM
reference-agent localfile /path/to/docs \
  --pattern "**/*.{pdf,docx,md}" \
  --model deepseek/deepseek-chat \
  -o ./my-bundle
```

#### 远程文件

```bash
# 方式1：直接指定 URL
reference-agent enrich --source api \
  --api-url https://example.com/doc1.pdf \
  --api-url https://example.com/doc2.docx \
  --out ./bundle --no-web

# 方式2：URL 列表文件
echo "https://example.com/doc1.pdf" > urls.txt
reference-agent enrich --source api \
  --api-url-file urls.txt \
  --out ./bundle --no-web

# 方式3：API 端点（返回 JSON，含文件 URL 列表）
reference-agent enrich --source api \
  --api-endpoint https://api.example.com/files \
  --api-url-field download_url \
  --api-token <bearer-token> \
  --out ./bundle --no-web
```

#### 混合模式（本地 + 远程）

```bash
reference-agent localfile /local/docs \
  --pattern "**/*.pdf" \
  --api-url https://example.com/remote-doc.pdf \
  -o ./mixed-bundle
```

### Step 3: 后处理

#### 生成可视化图谱

```bash
reference-agent visualize --bundle ./my-bundle
# 生成 self-contained HTML，默认输出到 <bundle>/viz.html
open ./my-bundle/viz.html
```

#### 验证 OKF 包符合性

运行验证脚本检查包是否符合 OKF v0.1 规范：

```bash
python scripts/validate_bundle.py ./my-bundle
```

验证项：
- 每个非保留 `.md` 文件都有可解析的 YAML 头信息
- 每个头信息块都含非空 `type` 字段
- `index.md` / `log.md` 格式正确（如存在）

参见 `references/okf-spec.md` 了解完整规范。

### Step 4: 检查输出

生成的 OKF 包结构示例：

```
my-bundle/
├── index.md              # 自动生成的目录清单
├── viz.html              # 交互式知识图谱（visualize 后）
├── docs/
│   ├── index.md
│   └── api_guide.md      # 概念文档（带 YAML frontmatter）
└── tables/
    ├── index.md
    └── orders.md
```

每个概念文档的格式参见 `assets/concept-template.md`。

## Troubleshooting

### Gemini API 限流 (429)

先等待 30 秒重试；若仍失败，按以下顺序处理：

1. 使用 `agent_pipeline.py --mode auto`（全量 + 分片重试）
2. 继续使用当前 Agent 默认模型重试，不强制要求手动 key
3. 仅当用户明确要求或需要立即完成时，再提供 API 配置命令或“模型名 + API Key”
4. 用户明确要求 provider 风格模型时，再补充对应依赖与环境变量

### 中文文件名报错

确保已完成 no-clone bootstrap（包含 Unicode 文件名支持所需版本）：

```bash
cd .codebuddy/skills/langwiki-okf
bash scripts/bootstrap_local.sh
```

### 缺少文档解析依赖

文档格式（PDF/Word/Excel/PPT）需要额外依赖：

```bash
pip install --user -e ".[localfile]"   # 安装 pdfplumber/python-docx/openpyxl/python-pptx
```

### Ollama 本地模型

```bash
ollama serve &           # 启动服务
ollama pull qwen2.5:7b   # 拉取模型
reference-agent localfile /path --model ollama/qwen2.5:7b
```

### 未安装 CLI 时的替代方案

可直接走 API 编排路径（无需安装 `reference-agent`）：

```bash
export OKF_API_MODEL=gpt-4o-mini
export OKF_API_BASE=https://api.openai.com/v1
export OKF_API_KEY=<your-key>
python scripts/agent_pipeline.py --input /path/to/docs --out ./okf-bundle --mode api --max-chars 20000

# 文档超长时可降低 --max-chars（如 12000/8000）避免超出模型上下文窗口
```

如需处理 PDF，建议安装轻量依赖：

```bash
pip install --user pypdf
```

### 自动跳过的目录

`reference-agent` 自动跳过：`.git`、`.venv`、`node_modules`、`__pycache__`、
`okf-bundle`（防止递归扫描把生成的 `.md` 当源文件）。

## Resources

### references/

- `okf-spec.md` — OKF v0.1 规范摘要（包结构、概念文档、交叉链接、符合性要求）
- `cli-reference.md` — `reference-agent` 全部命令和参数的完整参考
- `llm-models.md` — 多 LLM 模型预设、环境变量和安装说明（主要用于本机独立运行场景）
- `file-types.md` — 支持的 16 种文件格式及解析方式
- `vendor-maintenance.md` — vendor 源码同步与版本维护说明

### scripts/

- `agent_pipeline.py` — Agent 编排入口：分离 LLM 处理步骤并支持 `cli/api/auto` 模式
- `validate_bundle.py` — 验证 OKF 包是否符合 v0.1 规范
- `quick_start.sh` — no-clone 一键安装和快速验证脚本
- `sync_vendor_from_upstream.sh` — 从上游目录同步 vendor 并更新版本信息

### assets/

- `concept-template.md` — OKF 概念文档模板（含 frontmatter 和正文结构）
- `index-template.md` — OKF 索引文件模板
