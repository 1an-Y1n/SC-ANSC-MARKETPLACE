# Upstream snapshot

- **repo**: http://172.21.1.202:8090/ai-tools/ai-code-review-skill.git
- **ref**: dev
- **commit**: 2817aa0f09c7cb1dc15e708653fffd28e6d0033e
- **fetched**: 2026-10-16 (upstream commit date 2026-10-13)
- **layout**: the whole upstream tree, verbatim, under `upstream/` (pristine baseline for `patches/`)

`upstream/` 是**只读基线**：本条目根下的 live 载荷（`SKILL.md` / `mcp/` / `scripts/` /
`config/` / `docs/`）恒等于「这份快照 + `patches/*.patch` 全部按序应用」。
刷新请跑 `./sync-upstream.sh --apply`，不要手改 `upstream/` 或 live 载荷里的上游内容。

`upstream/` is a read-only baseline: the live payload at the item root always equals this
snapshot with every patch in `patches/` applied in order. Refresh it with
`./sync-upstream.sh --apply` — do not hand-edit `upstream/` or the upstream parts of the
live payload.
