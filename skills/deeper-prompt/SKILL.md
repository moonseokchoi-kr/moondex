---
name: deeper-prompt
description: Reframe a user's task for deeper professional investigation using the original four-question prompt. Use when explicitly requested to deepen or rewrite a task; present the result for the user to decide, without executing it.
---

# Deeper Prompt

Use only when the user explicitly requests this skill or asks to deepen a task or prompt. Apply the following prompt verbatim as the guiding instruction:

> I want a deeper version of this task, not a bigger one. Before rewriting it: (1) say what a top professional in this field would do here that I’m not asking for; (2) name the rawest material they would start from instead of what has already been digested for me; (3) name the specific methods and tools they would use; (4) say what, other than you or me, would show the result is right. Then rewrite my prompt to ask for exactly that.

Identify the task from the user's request and relevant conversation. If it is unclear, ask for the task. Use the available context to answer all four questions concretely, distinguishing known facts from assumptions and identifying unavailable material or validation. Then present a self-contained rewritten prompt in the user's language, preserving the intended outcome without automatically enlarging the task. The quoted original remains unchanged.

This skill prepares a proposal: show the four answers and rewritten prompt, then let the user decide whether to use, change, or decline it. Do not execute the rewritten prompt, edit project files, or undertake the proposed investigation merely because the skill was invoked. If the user later chooses an option, follow that choice within its authorized scope. The skill requires no other Moondex skill, runtime, or configuration.

Source: user-provided blog text, author and URL not supplied.
