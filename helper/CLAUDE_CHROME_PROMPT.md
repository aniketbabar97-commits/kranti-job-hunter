# Claude in Chrome — batch prompt (Sonnet / Haiku)

**Once, before the first batch** — put all PDFs in one folder. Open PowerShell and paste (adjust the ZIP path if it is not in Downloads):

```
Expand-Archive "$HOME\Downloads\Kranti_Applications_166.zip" C:\Kranti\unzip -Force; mkdir C:\Kranti\pdfs -Force; Get-ChildItem C:\Kranti\unzip -Recurse -Filter *.pdf | Copy-Item -Destination C:\Kranti\pdfs -Force
```

Paste everything between the lines into Claude in Chrome. Change `JOBS 2-21` for the next batch (20 jobs).
It never waits for you: blocked jobs are parked, and all questions come together at the end. Done: #1 Maify.

---
Apply for Kranti Chavan to JOBS 2-21 of https://github.com/aniketbabar97-commits/kranti-job-hunter/blob/main/helper/CLAUDE_CHROME_LIST.md
Read only those job blocks. Be brief: no explanations, no screenshots unless stuck. NEVER wait for me during the batch: anything needing me → park the job (leave its tab open), note why, go on with the next job.

Candidate: Kranti Chavan, Frau (salutation; if only neutral wanted: "Ohne/keine Angabe"), Karlsruhe, Germany.
Email + phone: take them from the CV PDF header. LinkedIn: https://www.linkedin.com/in/kranti-chavan-84a155191
Work permit: yes (valid). Notice: serving, earliest start 16.12.2026. Salary + "Why us": from the job block.
Files: the two PDFs named in the job block, all in ONE folder: C:\Kranti\pdfs\ (full path = C:\Kranti\pdfs\<file name>). In the upload dialog type/paste that full path into the "File name" box and press Enter — do not browse folders. If the site's upload button won't open a dialog you can use → park as UPLOAD.

Per job:
1. Open Link. Find the matching position on the employer's own career page (search the title). If the job is gone, try the Original posting's apply button; else report CLOSED.
2. Prefer "apply without account"/quick apply. If an account is needed: register with her email, password needed → park as ACCOUNT (never invent or store a password).
3. Fill every required field; optional fields only if the data is above. Upload CV + Anschreiben/Cover letter. Motivation field → "Why us". Language of answers = language of the posting.
4. Only a contact form, no upload → message = "Why us" + "Lebenslauf und Anschreiben sende ich Ihnen zusätzlich per E-Mail." (EN: "I am sending my CV and cover letter by email as well.") and report NOUPLOAD.
5. Tick only mandatory consent boxes (privacy). Never tick newsletter/talent pool unless required.
6. CAPTCHA, verification code, unknown required question, or unclear → park the job (tab open, form filled as far as possible), continue. Max 3 min per job.
7. Submit. Wait for the confirmation text.

At the end:
A) QUESTIONS — one numbered list of everything parked, each: `<n> <Company>: <what you need from me>`. After I answer, finish those jobs in their open tabs.
B) Then print ONLY these lines (one per job), so I can paste them into APPLIED.md:
- 2026-MM-DD <Original posting URL> (<Company>, website via Claude – OK|NOUPLOAD|ACCOUNT)
For failures instead: `SKIP <n> <Company>: CLOSED|CAPTCHA|ERROR <5 words>`
---

## After the batch

1. Paste the `- 2026…` lines under "## My applications" in `APPLIED.md` on GitHub (pencil icon).
2. That's it: the next run (11:00 / 17:00 IST) emails HR **only for jobs logged here** — website first, email after.
