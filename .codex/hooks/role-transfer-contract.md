# Role Transfer Contract Hook

This hook validates role transfer payloads against the repository contract in `docs/execution/role-transfer-contracts.md`.

Entrypoint:

```bash
.codex/hooks/validate-role-transfer.sh '<json-payload>'
.codex/hooks/validate-readiness.sh '<json-payload>'
```

The hook delegates validation to:

```bash
moondex api validate-role-transfer --input '<json-payload>' --json
moondex api validate-readiness --input '<json-payload>' --json
```

Policy:

- hard contract errors return `valid: false` and make the hook exit non-zero
- advisory warnings return `valid: true` and keep the hook exit zero
- readiness validation exits zero only when `decision` is `READY`
- the hook does not mutate `.moondex/state`

Runtime integration:

- `write-mailbox` runs role output validation before writing canonical role output
- `dispatch` runs lifecycle hard guards before writing a dispatch request
- warning-only lifecycle results are stored in `.moondex/state/hooks/warnings.json`
