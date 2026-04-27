---
name: moondex-cmux
description: Use when running Moondex roles on cmux surfaces, registering role identities, capturing terminal evidence, or resolving dispatch delivery issues.
---

# Moondex cmux

Use this skill for Moondex operation across cmux role surfaces.

## Read First

- `../../docs/execution/cmux-operations-playbook.md`
- `../../docs/execution/cmux-runtime-alignment.md`

## Core Rule

cmux is not the source of truth. Use cmux for role separation, wake-up transport, and evidence capture. Use `.moondex/state` to decide what happened.

## Surface Setup

In each role surface:

```bash
moondex role register-current implementer --json
moondex role register-current code-reviewer --json
moondex role register-current compliance-reviewer --json
moondex role register-current tester --json
```

Verify state:

```bash
moondex status --json
moondex api list-stale-roles --input '{"older_than_seconds":900}' --json
```

## Dispatch Handling

Workers must ACK dispatch after reading their inbox:

```bash
moondex api ack-dispatch --input '{"request_id":"<dispatch-id>","role_id":"<role-id>"}' --json
```

If dispatch stalls:

- `ack_dispatch_wait`: worker reads inbox and ACKs, or operator checks role identity.
- `surface_ref_missing`: register the role in its current cmux surface, then retry dispatch.
- `retry_exhausted`: capture evidence, inspect dispatch state, and fix the underlying cmux or identity issue before creating fresh dispatch.

## Evidence

Capture terminal evidence when screen output matters:

```bash
moondex cmux capture --surface surface:2 --lines 120 --json
moondex api list-evidence --json
```

