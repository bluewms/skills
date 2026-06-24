# no-clone bootstrap E2E 记录

## 执行环境

- 项目根目录：`<workspace>`
- skill 目录：`.codebuddy/skills/langwiki-okf`

## 执行步骤

```bash
cd .codebuddy/skills/langwiki-okf
bash scripts/bootstrap_local.sh
python scripts/agent_pipeline.py \
  --input <workspace>/docs \
  --pattern "**/*.pdf" \
  --out ./okf-test-no-clone \
  --mode auto \
  --dry-run
```

## 预期结果

- `scripts/reference-agent` 可执行
- `docs/okf-test-no-clone/request-pack/` 生成 `*.json`
- `docs/okf-test-no-clone/` 下生成 dry-run 概念文档与 `index.md`
- `python scripts/validate_bundle.py` 校验通过

## 验收判定

当以上 4 项均满足时，判定 no-clone 全流程通过。
