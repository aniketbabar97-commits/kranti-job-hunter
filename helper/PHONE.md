# Apply from the phone

## Fully automatic (recommended): every night at 23:00
Once: double-click `helper\setup_nightly.bat` (answer `y` to also start a run now).
From then on the PC applies to the best-fit jobs every night, even from sleep: up to 50 jobs, score 75+, last 14 days.
In the morning: CAPTCHA tabs are open in Chrome, `out\parked_tonight.txt` lists what is left, and results are on GitHub.


## Once per evening, on the PC
1. Double-click `helper\start_remote.bat`. Chrome opens, and the window says "Ready". Leave both open and keep the PC awake.
2. The first time only, log in if Claude asks you to.

## On the phone (Claude app → Code → the "kranti-job-hunter" session)
Copy one of these:

- **Best-fit jobs (default):**
  `Read helper/CLAUDE_CODE_APPLY.md and follow it exactly. Apply to 10 jobs. Then commit and push APPLIED.md, helper/PLAYBOOK.md and data/.`
- **All open jobs (no score filter):**
  `Run every python -m helper.claude_jobs command with MIN_SCORE=0 and APPLY_SINCE= set empty. Read helper/CLAUDE_CODE_APPLY.md and follow it exactly. Apply to 10 jobs. Then commit and push.`
- **Only SAP Commerce / Hybris:**
  `Run every python -m helper.claude_jobs command with APPLY_ONLY="sap commerce|hybris|sap cx|spartacus" and MIN_SCORE=0. Read helper/CLAUDE_CODE_APPLY.md and follow it exactly. Apply to 10 jobs. Then commit and push.`
- **What is left for me (CAPTCHAs etc.):** `python -m helper.claude_jobs parked`
- **Status:** `How many jobs did you confirm today? One line per job.`

After 10 jobs, send the same message again for the next 10.
If the phone asks to allow a command, tap "Allow" (or "Always allow").

## CAPTCHA
Claude leaves those tabs open in Chrome on the PC. Solve them at the PC, or open the job link on the phone and apply there.
