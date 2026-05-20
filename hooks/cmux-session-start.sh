#!/bin/bash
# Moondex: cmux 세션 시작 상태 표시
# Event: SessionStart
command -v cmux &>/dev/null || exit 0

cmux set-status codex "활성" --icon "sparkle" --color "#4CAF50" 2>/dev/null || true
exit 0
