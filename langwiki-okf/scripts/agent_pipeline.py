#!/usr/bin/env python3
"""
Agent-Orchestrated OKF Pipeline

目标：
1) 将“需要大模型处理”的步骤独立出来（Prompt 构建 + LLM 调用）。
2) 由 Agent 编排调用，接收结果后再执行后续落盘与校验。
3) 提供无需安装 reference-agent CLI 的替代路径（--mode api）。

模式：
- cli  : 使用 reference-agent localfile（已有链路）
- api  : 直接调用 OpenAI 兼容 API，生成 OKF 文档
- auto : 优先 cli，不可用则回退 api

示例：
  python agent_pipeline.py \
    --input /path/to/docs \
    --pattern "**/*.pdf" \
    --out /path/to/okf-bundle \
    --mode auto

API 模式环境变量：
- OKF_API_BASE   例如 https://api.openai.com/v1
- OKF_API_KEY    API Key
- OKF_API_MODEL  可选，默认 gpt-4o-mini
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
import re
import shutil
import subprocess
import sys
import textwrap
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
from urllib import request, error

# 允许大多数语言路径字符（包含中文）
CONCEPT_ID_RE = re.compile(r"[^\w/]+", re.UNICODE)

SUPPORTED_TEXT_EXTS = {
    ".md", ".txt", ".rst", ".json", ".yaml", ".yml", ".toml",
    ".csv", ".tsv", ".xml", ".html", ".htm",
    ".py", ".js", ".ts", ".tsx", ".jsx", ".java", ".go", ".rs", ".c", ".cpp",
}


@dataclass
class PipelineConfig:
    input_dir: Path
    out_dir: Path
    pattern: str
    mode: str
    model: str | None
    request_pack: Path | None
    max_chars: int
    cli_retries: int
    retry_wait: int
    dry_run: bool
    mock_response: bool
    verbose: bool


class PipelineError(RuntimeError):
    pass


def log(msg: str, verbose: bool = True):
    if verbose:
        print(msg)


def safe_concept_id(input_dir: Path, file_path: Path) -> str:
    rel = file_path.relative_to(input_dir).with_suffix("")
    raw = str(rel).replace("\\", "/")
    raw = raw.replace("-", "_").replace(" ", "_")
    cleaned = CONCEPT_ID_RE.sub("_", raw)
    cleaned = re.sub(r"/+", "/", cleaned).strip("/_")
    return cleaned or "concept"


def extract_text(file_path: Path, max_chars: int) -> str:
    suffix = file_path.suffix.lower()

    if suffix in SUPPORTED_TEXT_EXTS:
        text = file_path.read_text(encoding="utf-8", errors="ignore")
        return text[:max_chars]

    if suffix == ".pdf":
        try:
            from pypdf import PdfReader  # type: ignore
        except Exception as exc:
            raise PipelineError(
                "API 模式读取 PDF 需要轻量依赖 pypdf。请执行: pip install --user pypdf"
            ) from exc

        reader = PdfReader(str(file_path))
        chunks: list[str] = []
        for page in reader.pages:
            chunks.append(page.extract_text() or "")
        text = "\n".join(chunks)
        return text[:max_chars]

    mime, _ = mimetypes.guess_type(str(file_path))
    raise PipelineError(f"暂不支持该文件类型: {file_path.name} ({mime or 'unknown'})")


def render_prompt(concept_id: str, source_name: str, content: str) -> str:
    return textwrap.dedent(
        f"""
        你是 OKF（Open Knowledge Format）知识整理助手。
        请把输入内容整理为一个“可直接落盘的 Markdown 概念文件”，严格输出 Markdown，不要附加解释。

        必须满足：
        1) 文件开头为 YAML frontmatter，至少包含：
           - type: concept
           - concept_id: {concept_id}
           - title: <简短标题>
           - source: {source_name}
           - summary: <100字内摘要>
        2) 正文包含以下小节：
           - ## Key Points
           - ## Details
           - ## References
        3) 若原文信息不足，保留小节但写“待补充”。
        4) 使用简体中文输出。

        输入原文如下：
        ---
        {content}
        ---
        """
    ).strip()


def call_openai_compatible_messages(messages: list[dict], model: str, base_url: str, api_key: str, timeout: int = 90) -> str:
    endpoint = base_url.rstrip("/") + "/chat/completions"
    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.2,
    }

    data = json.dumps(payload).encode("utf-8")
    req = request.Request(
        endpoint,
        method="POST",
        data=data,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
    )

    try:
        with request.urlopen(req, timeout=timeout) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="ignore")
        raise PipelineError(f"API 请求失败: HTTP {exc.code} - {raw[:300]}") from exc
    except error.URLError as exc:
        raise PipelineError(f"API 连接失败: {exc.reason}") from exc

    try:
        return body["choices"][0]["message"]["content"].strip()
    except Exception as exc:
        raise PipelineError(f"API 响应格式异常: {json.dumps(body)[:300]}") from exc


def call_openai_compatible(prompt: str, model: str, base_url: str, api_key: str, timeout: int = 90) -> str:
    messages = [
        {"role": "system", "content": "你是严谨的知识结构化助手。"},
        {"role": "user", "content": prompt},
    ]
    return call_openai_compatible_messages(messages=messages, model=model, base_url=base_url, api_key=api_key, timeout=timeout)


def ensure_frontmatter(md: str, concept_id: str, source_name: str) -> str:
    if md.lstrip().startswith("---"):
        return md

    fallback = textwrap.dedent(
        f"""
        ---
        type: concept
        concept_id: {concept_id}
        title: {concept_id.split('/')[-1]}
        source: {source_name}
        summary: 自动生成，建议人工复核。
        ---

        ## Key Points
        待补充

        ## Details
        {md.strip() or '待补充'}

        ## References
        待补充
        """
    ).strip()
    return fallback + "\n"


def write_index(out_dir: Path, concept_files: list[Path]):
    lines = [
        "---",
        "type: index",
        "okf_version: v0.1",
        "---",
        "",
        "# Index",
        "",
    ]

    for file in sorted(concept_files):
        rel = file.relative_to(out_dir).as_posix()
        title = file.stem
        lines.append(f"- [{title}]({rel})")

    (out_dir / "index.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_validator(out_dir: Path, verbose: bool):
    script = Path(__file__).with_name("validate_bundle.py")
    if not script.exists():
        log("[WARN] 未找到 validate_bundle.py，跳过校验", verbose)
        return

    cmd = [sys.executable, str(script), str(out_dir)]
    if verbose:
        cmd.append("--verbose")

    result = subprocess.run(cmd, check=False)
    if result.returncode not in (0, 2):
        raise PipelineError("OKF 校验失败，请检查输出内容。")


def _first_nonempty_env(keys: list[str]) -> str:
    for k in keys:
        v = os.getenv(k, "").strip()
        if v:
            return v
    return ""


def resolve_api_credentials() -> tuple[str, str]:
    base_url = _first_nonempty_env([
        "OKF_API_BASE",
        "OPENAI_BASE_URL",
        "OPENAI_API_BASE",
    ])
    api_key = _first_nonempty_env([
        "OKF_API_KEY",
        "OPENAI_API_KEY",
    ])
    return base_url, api_key


def resolve_model(cfg: PipelineConfig) -> str:
    if cfg.model:
        return cfg.model
    model = _first_nonempty_env([
        "OKF_API_MODEL",
        "CODEBUDDY_MODEL",
        "OPENAI_MODEL",
    ])
    return model or "gpt-5.3-codex"


def _has_api_credentials() -> bool:
    base_url, api_key = resolve_api_credentials()
    return bool(base_url and api_key)


def _config_command_hint() -> str:
    return textwrap.dedent(
        """
        请先配置 skill 变量（可重复执行覆盖旧值）：
          export OKF_API_MODEL=<your-model>
          export OKF_API_BASE=<openai-compatible-base-url>
          export OKF_API_KEY=<your-api-key>

        说明：
        - 建议按模型上下文窗口控制输入长度，使用 --max-chars（默认 20000）
        - 如果文档很长，请减小 --max-chars 或分片执行，避免超出模型上下文上限
        """
    ).strip()


def resolve_reference_agent_command() -> str:
    """优先返回 skill 内置 wrapper，其次回退系统 PATH 中的 reference-agent。"""
    script_dir = Path(__file__).resolve().parent
    local_wrapper = script_dir / "reference-agent"
    if local_wrapper.exists() and os.access(local_wrapper, os.X_OK):
        return str(local_wrapper)

    system_cmd = shutil.which("reference-agent")
    if system_cmd:
        return system_cmd

    raise PipelineError(
        "未找到可用 reference-agent 命令。请先执行: bash scripts/bootstrap_local.sh"
    )


def _run_cli_once(cfg: PipelineConfig, concept_id: str | None = None):
    cli_cmd = resolve_reference_agent_command()
    cmd = [
        cli_cmd,
        "localfile",
        str(cfg.input_dir),
        "--pattern",
        cfg.pattern,
        "-o",
        str(cfg.out_dir),
    ]
    if cfg.model:
        cmd.extend(["--model", cfg.model])
    if concept_id:
        cmd.extend(["--concept", concept_id])

    label = f"concept={concept_id}" if concept_id else "full"
    log(f"[CLI:{label}] 执行: " + " ".join(cmd), cfg.verbose)
    return subprocess.run(cmd, check=False)


def _list_concept_files(out_dir: Path) -> list[Path]:
    if not out_dir.exists():
        return []
    md_files = list(out_dir.rglob("*.md"))
    return [p for p in md_files if p.name not in {"index.md", "log.md"}]


def run_cli_mode(cfg: PipelineConfig):
    result = _run_cli_once(cfg)
    if result.returncode != 0:
        raise PipelineError(f"reference-agent 执行失败，退出码: {result.returncode}")

    concept_files = _list_concept_files(cfg.out_dir)
    if not concept_files:
        raise PipelineError("CLI 执行结束但未生成概念文档（可能是 503/429 或上游假成功）。")

    run_validator(cfg.out_dir, cfg.verbose)


def iter_files(input_dir: Path, pattern: str) -> Iterable[Path]:
    for p in sorted(input_dir.glob(pattern)):
        if not p.is_file():
            continue
        if p.name in {"index.md", "log.md"}:
            continue
        yield p


def run_cli_sharded_mode(cfg: PipelineConfig):
    files = list(iter_files(cfg.input_dir, cfg.pattern))
    if not files:
        raise PipelineError(f"未匹配到文件: pattern={cfg.pattern}")

    failures: list[str] = []
    cfg.out_dir.mkdir(parents=True, exist_ok=True)

    for src in files:
        concept_id = safe_concept_id(cfg.input_dir, src)
        expected = cfg.out_dir / f"{concept_id}.md"

        if expected.exists():
            log(f"[SHARD] 已存在，跳过: {concept_id}", cfg.verbose)
            continue

        ok = False
        for attempt in range(1, cfg.cli_retries + 1):
            log(f"[SHARD] 处理 {concept_id} (第 {attempt}/{cfg.cli_retries} 次)", cfg.verbose)
            result = _run_cli_once(cfg, concept_id=concept_id)
            if result.returncode == 0 and expected.exists():
                ok = True
                break
            if attempt < cfg.cli_retries:
                time.sleep(cfg.retry_wait)

        if not ok:
            failures.append(concept_id)

    concept_files = _list_concept_files(cfg.out_dir)
    if not concept_files:
        raise PipelineError("分片重试后仍无概念文档产出。")

    run_validator(cfg.out_dir, cfg.verbose)

    if failures:
        failed = ", ".join(failures)
        raise PipelineError(f"以下概念分片重试后仍失败: {failed}")


def _mask_base_url(base_url: str) -> str:
    if not base_url:
        return ""
    return re.sub(r"(https?://[^/]+).*", r"\1", base_url)


def _build_request_pack(concept_id: str, src: Path, prompt: str, model: str) -> dict:
    return {
        "concept_id": concept_id,
        "source": src.as_posix(),
        "source_name": src.name,
        "model": model,
        "messages": [
            {"role": "system", "content": "你是严谨的知识结构化助手。"},
            {"role": "user", "content": prompt},
        ],
    }


def _load_request_pack(pack_file: Path) -> dict:
    if not pack_file.exists() or not pack_file.is_file():
        raise PipelineError(f"request-pack 文件不存在: {pack_file}")

    try:
        pack = json.loads(pack_file.read_text(encoding="utf-8"))
    except Exception as exc:
        raise PipelineError(f"request-pack 解析失败: {pack_file}") from exc

    concept_id = str(pack.get("concept_id", "")).strip()
    source_name = str(pack.get("source_name", "")).strip()
    messages = pack.get("messages")
    if not concept_id:
        raise PipelineError("request-pack 缺少 concept_id")
    if not source_name:
        raise PipelineError("request-pack 缺少 source_name")
    if not isinstance(messages, list) or not messages:
        raise PipelineError("request-pack 缺少有效 messages")

    return pack


def _mock_answer(concept_id: str, source_name: str) -> str:
    return textwrap.dedent(
        f"""
        ---
        type: concept
        concept_id: {concept_id}
        title: mock_{concept_id}
        source: {source_name}
        summary: mock-response 生成，仅用于端到端流程验证。
        ---

        ## Key Points
        - 已启用 `--mock-response`，本次未调用外部模型。

        ## Details
        该结果用于验证 request-pack 回放、落盘与校验流程。

        ## References
        - source: {source_name}
        """
    ).strip() + "\n"


def run_api_mode(cfg: PipelineConfig):
    base_url, api_key = resolve_api_credentials()
    model = resolve_model(cfg)

    if not model:
        raise PipelineError(
            "未检测到默认模型（OKF_API_MODEL）。\n" + _config_command_hint()
        )

    if not cfg.dry_run and not cfg.mock_response and (not base_url or not api_key):
        raise PipelineError(
            "API 模式需要 OKF_API_BASE 与 OKF_API_KEY。\n" + _config_command_hint()
        )

    cfg.out_dir.mkdir(parents=True, exist_ok=True)

    concept_files: list[Path] = []

    if cfg.request_pack:
        pack = _load_request_pack(cfg.request_pack)
        concept_id = str(pack["concept_id"]).strip()
        source_name = str(pack["source_name"]).strip()
        source_path = str(pack.get("source", source_name)).strip()
        messages = pack["messages"]
        final_model = cfg.model or model

        target = cfg.out_dir / f"{concept_id}.md"
        target.parent.mkdir(parents=True, exist_ok=True)

        if cfg.dry_run:
            dry_md = textwrap.dedent(
                f"""
                ---
                type: concept
                concept_id: {concept_id}
                title: dry_run_{concept_id}
                source: {source_name}
                summary: dry-run 请求编排测试产物（request-pack 直跑），未调用模型。
                ---

                ## Key Points
                - 请求包文件：`{cfg.request_pack.as_posix()}`
                - 当前模型字段：`{final_model}`
                - Base URL(脱敏)：`{_mask_base_url(base_url) or '未设置'}`

                ## Details
                本文件为 request-pack 直跑的 dry-run 占位结果。实际生成内容请关闭 `--dry-run` 后执行。

                ## References
                - source: {source_path}
                """
            ).strip() + "\n"
            target.write_text(dry_md, encoding="utf-8")
            concept_files.append(target)
            write_index(cfg.out_dir, concept_files)
            run_validator(cfg.out_dir, cfg.verbose)
            return

        if cfg.mock_response:
            answer = _mock_answer(concept_id=concept_id, source_name=source_name)
        else:
            answer = call_openai_compatible_messages(messages=messages, model=final_model, base_url=base_url, api_key=api_key)
        content = ensure_frontmatter(answer, concept_id=concept_id, source_name=source_name)
        target.write_text(content, encoding="utf-8")
        concept_files.append(target)
        write_index(cfg.out_dir, concept_files)
        run_validator(cfg.out_dir, cfg.verbose)
        return

    files = list(iter_files(cfg.input_dir, cfg.pattern))
    if not files:
        raise PipelineError(f"未匹配到文件: pattern={cfg.pattern}")

    request_pack_dir = cfg.out_dir / "request-pack"
    request_pack_dir.mkdir(parents=True, exist_ok=True)

    for src in files:
        concept_id = safe_concept_id(cfg.input_dir, src)
        target = cfg.out_dir / f"{concept_id}.md"
        target.parent.mkdir(parents=True, exist_ok=True)

        log(f"[API] 处理: {src}", cfg.verbose)
        text = extract_text(src, cfg.max_chars)
        prompt = render_prompt(concept_id, src.name, text)
        pack = _build_request_pack(concept_id=concept_id, src=src, prompt=prompt, model=model)
        pack_file = request_pack_dir / f"{concept_id}.json"
        pack_file.parent.mkdir(parents=True, exist_ok=True)
        pack_file.write_text(json.dumps(pack, ensure_ascii=False, indent=2), encoding="utf-8")

        if cfg.dry_run:
            dry_md = textwrap.dedent(
                f"""
                ---
                type: concept
                concept_id: {concept_id}
                title: dry_run_{src.stem}
                source: {src.name}
                summary: dry-run 请求编排测试产物，未调用模型。
                ---

                ## Key Points
                - 已生成请求编排文件：`request-pack/{concept_id}.json`
                - 当前模型字段：`{model}`
                - Base URL(脱敏)：`{_mask_base_url(base_url) or '未设置'}`

                ## Details
                本文件为 dry-run 占位结果。实际生成内容请关闭 `--dry-run` 后执行。

                ## References
                - source: {src.as_posix()}
                """
            ).strip() + "\n"
            target.write_text(dry_md, encoding="utf-8")
            concept_files.append(target)
            continue

        if cfg.mock_response:
            answer = _mock_answer(concept_id=concept_id, source_name=src.name)
        else:
            answer = call_openai_compatible(prompt, model=model, base_url=base_url, api_key=api_key)
        content = ensure_frontmatter(answer, concept_id=concept_id, source_name=src.name)

        target.write_text(content, encoding="utf-8")
        concept_files.append(target)

    write_index(cfg.out_dir, concept_files)
    run_validator(cfg.out_dir, cfg.verbose)


def run_auto_mode(cfg: PipelineConfig):
    # dry-run 场景优先走 API 编排：可生成 request-pack 与占位产物，不依赖 CLI 可用性。
    if cfg.dry_run:
        run_api_mode(cfg)
        return

    try:
        run_cli_mode(cfg)
        return
    except Exception as full_error:
        log(f"[AUTO] Agent/CLI 全量失败，转分片重试: {full_error}", cfg.verbose)

    try:
        run_cli_sharded_mode(cfg)
        return
    except Exception as shard_error:
        log(f"[AUTO] Agent/CLI 分片失败: {shard_error}", cfg.verbose)

    if _has_api_credentials():
        model = resolve_model(cfg)
        log(f"[AUTO] 检测到会话/API凭据，回退 API 路径（model={model}）", cfg.verbose)
        run_api_mode(cfg)
        return

    raise PipelineError(
        "Agent/CLI 路径暂不可用，且当前未检测到 OKF_API_BASE/OKF_API_KEY。\n"
        + _config_command_hint()
    )


def parse_args() -> PipelineConfig:
    parser = argparse.ArgumentParser(description="Agent 编排 OKF 生成流程（Agent优先 + API可选）")
    parser.add_argument("--input", required=True, help="输入目录")
    parser.add_argument("--out", required=True, help="输出目录")
    parser.add_argument("--pattern", default="**/*", help="文件匹配模式，默认 **/*")
    parser.add_argument("--mode", choices=["auto", "cli", "api"], default="auto", help="执行模式")
    parser.add_argument("--model", default=None, help="模型名（可选）")
    parser.add_argument("--request-pack", default=None, help="直接执行已生成的 request-pack JSON 文件")
    parser.add_argument("--max-chars", type=int, default=20000, help="单文件最大输入字符数")
    parser.add_argument("--cli-retries", type=int, default=3, help="CLI分片重试次数，默认3")
    parser.add_argument("--retry-wait", type=int, default=8, help="重试间隔秒数，默认8")
    parser.add_argument("--dry-run", action="store_true", help="仅做请求编排并输出测试产物，不调用模型")
    parser.add_argument("--mock-response", action="store_true", help="生成本地 mock 结果，不调用外部模型")
    parser.add_argument("-v", "--verbose", action="store_true", help="显示详细日志")

    args = parser.parse_args()

    return PipelineConfig(
        input_dir=Path(args.input).resolve(),
        out_dir=Path(args.out).resolve(),
        pattern=args.pattern,
        mode=args.mode,
        model=args.model,
        request_pack=Path(args.request_pack).resolve() if args.request_pack else None,
        max_chars=args.max_chars,
        cli_retries=max(1, args.cli_retries),
        retry_wait=max(1, args.retry_wait),
        dry_run=args.dry_run,
        mock_response=args.mock_response,
        verbose=args.verbose,
    )


def main():
    cfg = parse_args()

    if not cfg.input_dir.exists() or not cfg.input_dir.is_dir():
        raise SystemExit(f"输入目录不存在或不是目录: {cfg.input_dir}")

    try:
        if cfg.mode == "cli":
            run_cli_mode(cfg)
        elif cfg.mode == "api":
            run_api_mode(cfg)
        else:
            run_auto_mode(cfg)
    except PipelineError as exc:
        print(f"❌ {exc}")
        raise SystemExit(1)

    print(f"✅ OKF 生成完成: {cfg.out_dir}")


if __name__ == "__main__":
    main()
