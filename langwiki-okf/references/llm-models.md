# 多 LLM 模型参考（Agent 默认 + 用户输入回退）

## 核心约定

- **默认优先**：先用当前 Agent 会话可用默认模型执行，不额外安装 `litellm`。
- **失败回退**：若默认模型不可用，先走 `agent_pipeline.py --mode auto` 的分片重试；仅在需要立即完成时，再提示 API 配置。
- **按需扩展**：仅当用户明确要求 provider 风格模型（如 `deepseek/...`）时，才安装或配置对应依赖。
- **no-clone 前置**：先执行 `bash scripts/bootstrap_local.sh`，确保 `scripts/reference-agent` 可用。

## 模式 A：Agent 默认模式（推荐）

### 运行方式

```bash
reference-agent localfile /path/to/docs
```

### 失败时的标准提示

当出现 503/429 或“无可用模型”时，优先提示用户：

- 方案 1：请提供可执行配置命令（例如设置默认模型 API Key）
- 方案 2：请在对话里直接提供默认模型名称与 API Key

> 不默认建议安装 `litellm`，避免每次安装开销与环境污染。

## 模式 B：用户显式指定 provider 模型（可选）

仅当用户明确指定时，才使用：

```bash
reference-agent localfile /path/to/docs --model deepseek/deepseek-chat
```

若运行报错提示缺 provider 支持，再让用户确认是否安装依赖并补充环境变量。

## 模式 C：不安装 CLI，直接 API 调用（可选后备）

使用 `scripts/agent_pipeline.py --mode api`，仅需配置：

```bash
export OKF_API_BASE=https://api.openai.com/v1
export OKF_API_KEY=<your-key>
# 可选：export OKF_API_MODEL=gpt-4o-mini
python scripts/agent_pipeline.py --input /path/to/docs --out ./okf-bundle --mode api
```

说明：
- 默认不需要 `litellm`。
- 如需解析 PDF，建议安装轻量依赖 `pypdf`（比完整 CLI 依赖更小）。

## 本机独立运行（可选）

如果离开 Agent 在终端独立运行，按原项目文档配置：

- `knowledge-catalog/README.dev.md`
- `knowledge-catalog/okf/README.md`
