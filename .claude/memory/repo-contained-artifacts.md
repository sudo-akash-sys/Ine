---
name: repo-contained-artifacts
description: All artifacts and Claude-generated files stay inside the project repo, never in user home directory
metadata:
  type: project
---

All Claude-generated artifacts, temporary files, and scratchpad content must be written inside this repository at `E:\VS Code\Projects\MyLanguage\.tmp\` or another project-relative path.

**Why:** Each project repo should be self-contained. Files in the C drive user directory are invisible to git, not version-controlled, and scattered across machines. Keeping everything in the repo ensures portability, traceability, and single-source-of-truth.

**How to apply:**
- When the Artifact tool or any file output is needed, write to `.tmp/` (gitignored) or another repo-relative path
- Never write to `C:\Users\A-pc\.claude\` or any user-home location
- The memory directory at `C:\Users\A-pc\.claude\projects\E--VS-Code-Projects-MyLanguage\memory\` is the one exception, managed by the harness for session-persistent memories
- For artifacts, prefer `.tmp/artifacts/` within the repo over the harness scratchpad directory
