# 支持的文件类型参考

`reference-agent` 的 `LocalFileSource` 支持 16 种文件格式，分为文档格式
（需额外依赖）和基础文本格式（内置支持）两类。

## 文档格式（需安装 `[localfile]` 可选依赖）

| 扩展名 | 概念类型 | 解析方式 | 依赖 |
|--------|---------|---------|------|
| `.pdf` | PDF Document | pdfplumber 提取文本 | `pdfplumber` |
| `.docx` | Word Document | python-docx 提取段落 | `python-docx` |
| `.xlsx` / `.xls` | Excel Spreadsheet | pandas + openpyxl，限 50 行 | `pandas` + `openpyxl` |
| `.pptx` / `.ppt` | PowerPoint Presentation | python-pptx 提取幻灯片文本 | `python-pptx` |

安装依赖：

```bash
cd knowledge-catalog/okf
pip install --user -e ".[localfile]"
```

或单独安装：

```bash
pip install pdfplumber python-docx openpyxl python-pptx pandas
```

## 基础文本格式（内置支持，无需额外依赖）

| 扩展名 | 概念类型 | 解析方式 |
|--------|---------|---------|
| `.md` / `.markdown` | Document | 直接读取 UTF-8 |
| `.txt` | Document | UTF-8，回退 GBK |
| `.py` | Python Module | 读取，超 8000 字符截断 |
| `.ts` | TypeScript Module | 读取，超 8000 字符截断 |
| `.js` | JavaScript Module | 读取，超 8000 字符截断 |
| `.json` | Config File | 直接读取 |
| `.yaml` / `.yml` | Config File | 直接读取 |
| `.html` | HTML Document | 读取，超 8000 字符截断 |
| `.csv` | Data File | 采样前 5 行 |

## 文件类型 → 概念类型映射

```
.md / .markdown  → Document
.txt             → Document
.pdf             → PDF Document
.docx            → Word Document
.xlsx / .xls     → Excel Spreadsheet
.pptx / .ppt     → PowerPoint Presentation
.py              → Python Module
.ts              → TypeScript Module
.js              → JavaScript Module
.json            → Config File
.yaml / .yml     → Config File
.html            → HTML Document
.csv             → Data File
```

未识别的扩展名映射为通用类型 `File`。

## 解析行为细节

### PDF
- 使用 `pdfplumber` 逐页提取文本
- 自动抑制 pdfminer 的 "Could not get FontBBox" 警告
- 各页文本用 `\n\n` 连接

### Word (.docx)
- 使用 `python-docx` 提取所有非空段落
- 段落文本用 `\n\n` 连接

### Excel (.xlsx/.xls)
- 使用 `pandas` + `openpyxl`
- 读取所有 sheet，每 sheet 限制 50 行
- 输出为 Markdown 表格格式

### PowerPoint (.pptx/.ppt)
- 使用 `python-pptx`
- 逐幻灯片提取文本，跳过空内容
- 每页标题格式为 `## Slide N`

### 代码文件 (.py/.ts/.js/.html)
- 直接读取文本
- 超过 8000 字符截断，附加 `... [truncated, N chars total]`

### CSV
- 内置 `csv.DictReader` 读取
- `sample_rows` 方法采样前 5 行

### JSON
- 直接读取文本
- `sample_rows` 方法解析 JSON，列表取前 N 项

### 文本文件 (.txt)
- 优先 UTF-8 解码
- 失败时回退 GBK（兼容中文 Windows 编码）

## glob 模式示例

```bash
# 所有 PDF
--pattern "**/*.pdf"

# Markdown 和文本
--pattern "**/*.{md,txt}"

# 文档格式
--pattern "**/*.{pdf,docx,xlsx,pptx}"

# 代码文件
--pattern "**/*.{py,ts,js}"

# 所有支持的格式
--pattern "**/*"   # 默认值

# 特定目录
--pattern "docs/**/*.md"
```

## 限制

- 单文件上限：10MB
- 自动跳过目录：`.git`、`.venv`、`node_modules`、`__pycache__`、
  `.pytest_cache`、`dist`、`build`、`.idea`、`.vscode`、`okf-bundle`
- 代码文件截断阈值：8000 字符
- Excel 行数限制：50 行/sheet
