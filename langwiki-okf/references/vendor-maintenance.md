# vendor 维护说明（langwiki-okf）

## 目标

保持 `vendor/reference_agent` 与上游 `knowledge-catalog/okf/src/reference_agent` 同步，同时维持本 skill 的 no-clone 体验。

## 前置条件

- 上游源码已在本地可访问（例如 `<workspace>/knowledge-catalog/okf/src/reference_agent`）
- 已安装 `rsync`

## 同步命令

```bash
cd .codebuddy/skills/langwiki-okf
bash scripts/sync_vendor_from_upstream.sh --upstream <workspace>/knowledge-catalog/okf/src/reference_agent
```

## dry-run 预览

```bash
cd .codebuddy/skills/langwiki-okf
bash scripts/sync_vendor_from_upstream.sh --upstream <workspace>/knowledge-catalog/okf/src/reference_agent --dry-run
```

## 同步后检查

1. `vendor/VERSION.txt` 已更新 `snapshot_date` 与 `upstream_commit`
2. `vendor/_upstream_filelist.txt` 已更新（不包含 `__pycache__` 与 `*.pyc`）
3. 运行：

```bash
bash scripts/bootstrap_local.sh
python -m unittest discover scripts/tests -v
```

## 说明

- 同步脚本默认 `--delete`，会删除 vendor 中上游已不存在的文件
- 同步逻辑会自动排除 Python 缓存目录和 `.pyc` 文件
- `scripts/quick_start.sh --sync-vendor --upstream <path>` 是同一能力的快捷入口
