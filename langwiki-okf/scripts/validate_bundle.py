#!/usr/bin/env python3
"""
OKF Bundle Validator — 验证 OKF 包是否符合 v0.1 规范。

符合性要求（OKF v0.1 §9）：
  1. 每个非保留的 .md 文件都含有可解析的 YAML 头信息块。
  2. 每个头信息块都含有一个非空的 type 字段。
  3. 每个保留文件名（index.md、log.md）在出现时遵循对应结构。

用法：
  python validate_bundle.py <bundle-dir>
  python validate_bundle.py <bundle-dir> --verbose
  python validate_bundle.py <bundle-dir> --fix-index   # 尝试修复缺失的 index.md

退出码：
  0 — 全部通过
  1 — 有错误
  2 — 有警告但无错误
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

# 保留文件名
RESERVED_FILES = {"index.md", "log.md"}

# YAML 头信息正则：--- 开头，--- 结尾
FRONTMATTER_RE = re.compile(
    r"\A---\s*\n(.*?)\n---\s*(?:\n|$)",
    re.DOTALL,
)

# type 字段正则（支持 "type: value" 和 "type: 'value'" 和 "type: \"value\""）
TYPE_RE = re.compile(
    r'^type\s*:\s*["\']?(.+?)["\']?\s*$',
    re.MULTILINE,
)

# ISO 8601 日期格式（用于 log.md 检查）
DATE_RE = re.compile(r"^##\s+(\d{4}-\d{2}-\d{2})\s*$")


class ValidationResult:
    def __init__(self):
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.passed: list[str] = []

    @property
    def ok(self) -> bool:
        return len(self.errors) == 0

    @property
    def has_warnings(self) -> bool:
        return len(self.warnings) > 0

    def report(self, verbose: bool = False) -> str:
        lines = []
        if self.passed and verbose:
            lines.append("✅ Passed checks:")
            for p in self.passed:
                lines.append(f"   {p}")
        if self.warnings:
            lines.append("⚠️  Warnings:")
            for w in self.warnings:
                lines.append(f"   {w}")
        if self.errors:
            lines.append("❌ Errors:")
            for e in self.errors:
                lines.append(f"   {e}")
        return "\n".join(lines)


def extract_frontmatter(content: str) -> str | None:
    """提取 YAML 头信息内容，返回 None 如果不存在。"""
    match = FRONTMATTER_RE.match(content)
    if match:
        return match.group(1)
    return None


def get_type_field(frontmatter: str) -> str | None:
    """从头信息中提取 type 字段值。"""
    match = TYPE_RE.search(frontmatter)
    if match:
        return match.group(1).strip()
    return None


def validate_concept_file(path: Path, result: ValidationResult, verbose: bool):
    """验证概念文档（非保留文件）。"""
    rel = path.relative_to(path.parents[len(path.parents) - 1]) if len(path.parents) > 0 else path
    try:
        content = path.read_text(encoding="utf-8")
    except Exception as e:
        result.errors.append(f"{path}: 无法读取文件 — {e}")
        return

    # 检查 1：必须有可解析的 YAML 头信息
    fm = extract_frontmatter(content)
    if fm is None:
        result.errors.append(f"{path}: 缺少 YAML 头信息块（--- ... ---）")
        return

    # 检查 2：必须有非空 type 字段
    type_val = get_type_field(fm)
    if not type_val:
        result.errors.append(f"{path}: 头信息缺少非空 'type' 字段")
        return

    if verbose:
        result.passed.append(f"{path.name} (type={type_val})")


def validate_index_file(path: Path, result: ValidationResult):
    """验证 index.md 文件。"""
    try:
        content = path.read_text(encoding="utf-8")
    except Exception as e:
        result.warnings.append(f"{path}: 无法读取 — {e}")
        return

    # index.md 不应有头信息（除非在包根目录声明 okf_version）
    fm = extract_frontmatter(content)
    if fm:
        # 检查是否有 okf_version（仅包根 index.md 允许）
        if "okf_version" not in fm:
            result.warnings.append(
                f"{path}: index.md 通常不应有头信息（除非声明 okf_version）"
            )

    # 检查是否有内容（非空）
    body = FRONTMATTER_RE.sub("", content).strip() if fm else content.strip()
    if not body:
        result.warnings.append(f"{path}: index.md 内容为空")


def validate_log_file(path: Path, result: ValidationResult):
    """验证 log.md 文件。"""
    try:
        content = path.read_text(encoding="utf-8")
    except Exception as e:
        result.warnings.append(f"{path}: 无法读取 — {e}")
        return

    lines = content.splitlines()
    date_count = 0
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("## "):
            match = DATE_RE.match(stripped)
            if match:
                date_count += 1
            elif not stripped.startswith("## ") or stripped == "## ":
                # 非日期的二级标题，可能是 "Directory Update Log" 等
                pass

    if date_count == 0 and any(l.strip() for l in lines):
        result.warnings.append(
            f"{path}: log.md 未检测到 ISO 8601 日期标题（YYYY-MM-DD）"
        )


def validate_bundle(bundle_dir: Path, verbose: bool = False) -> ValidationResult:
    """验证整个 OKF 包。"""
    result = ValidationResult()

    if not bundle_dir.exists():
        result.errors.append(f"目录不存在: {bundle_dir}")
        return result

    if not bundle_dir.is_dir():
        result.errors.append(f"不是目录: {bundle_dir}")
        return result

    # 遍历所有 .md 文件
    md_files = sorted(bundle_dir.rglob("*.md"))
    if not md_files:
        result.warnings.append("包中没有 .md 文件")
        return result

    concept_count = 0
    index_count = 0
    log_count = 0

    for md_path in md_files:
        filename = md_path.name

        if filename in RESERVED_FILES:
            if filename == "index.md":
                index_count += 1
                validate_index_file(md_path, result)
            elif filename == "log.md":
                log_count += 1
                validate_log_file(md_path, result)
        else:
            concept_count += 1
            validate_concept_file(md_path, result, verbose)

    # 汇总信息
    result.passed.insert(0, f"扫描完成: {concept_count} 个概念, "
                            f"{index_count} 个索引, {log_count} 个日志")

    # 检查是否有根 index.md
    root_index = bundle_dir / "index.md"
    if not root_index.exists():
        result.warnings.append("包根目录缺少 index.md（可选但推荐）")

    return result


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    bundle_dir = Path(sys.argv[1]).resolve()
    verbose = "--verbose" in sys.argv or "-v" in sys.argv

    print(f"验证 OKF 包: {bundle_dir}\n")

    result = validate_bundle(bundle_dir, verbose=verbose)

    print(result.report(verbose=verbose))

    print(f"\n{'='*50}")
    if result.ok and not result.has_warnings:
        print(f"✅ 全部通过 — {bundle_dir} 符合 OKF v0.1 规范")
        sys.exit(0)
    elif result.ok and result.has_warnings:
        print(f"⚠️  通过（有警告） — {bundle_dir} 基本符合规范")
        sys.exit(2)
    else:
        print(f"❌ 验证失败 — {len(result.errors)} 个错误")
        sys.exit(1)


if __name__ == "__main__":
    main()
