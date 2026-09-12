#!/bin/bash
# Advisory compatibility entrypoint. The active controller-first SDD path does
# not register or invoke this script. It deliberately performs no persistence:
# lifecycle decisions and durable transitions belong to the orchestrator and
# the project-local controller.

set -euo pipefail

# Consume optional compatibility input so callers do not receive a broken pipe.
if [ ! -t 0 ]; then
  while IFS= read -r _line; do :; done
fi

printf '%s\n' \
  'Rate-limit advisory received; no project files were changed.' \
  'Return the interruption evidence to the orchestrator, then use the project-local controller status/resume commands.'
