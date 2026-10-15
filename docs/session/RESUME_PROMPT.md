# Resume Prompt — paste this in any new chat

I am continuing a multi-unit cleanup of a Python project at:
/mnt/Data/Python Project/learning

Before responding, please read these files in order:
  1. docs/session/CONTINUATION.md   ← current state, conventions, decisions
  2. PROJECT_MAP.md                 ← project structure and known issues
  3. git log --oneline -10          ← recent commit history

You will act as my technical co-pilot for a staged cleanup. Rules are in
CONTINUATION.md under "Working Conventions". Do not deviate from them.

Current position: see "Current Status" in CONTINUATION.md.
Next action: see "Next Unit Plan" in CONTINUATION.md.

For every new unit, follow this pattern:
  Stage A — Discovery (read-only, produce inventory)
  Stage B — Plan (I approve before any edits)
  Stage C — Apply (move/fix only what was approved)
  Stage D — Verify + I commit manually

For every Antigravity agent action, give me the exact prompt to paste — never
run commands yourself.

At the end of each unit, remind me to update docs/session/CONTINUATION.md with:
  - New commit hash added to Commit History
  - Current Status moved forward
  - New decisions logged
  - Any new known issues discovered

Confirm you have read CONTINUATION.md and PROJECT_MAP.md, then tell me which
unit we are on and what the next step is.
