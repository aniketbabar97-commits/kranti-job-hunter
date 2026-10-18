# Apply for Kranti Chavan — instructions for Claude Code (on her PC)

You apply to jobs for Kranti Chavan in a real browser (Playwright MCP). Work alone; never ask me anything
unless a CAPTCHA blocks you. Be fast and brief: no explanations between steps.

## Before you start
Read `helper/PLAYBOOK.md` once. It holds what worked on each application system in earlier runs — follow it.

## Loop (repeat for the number of jobs I asked for)
1. Get the next job: `python -m helper.claude_jobs next 1` → JSON with `id`, `company`, `title`, `link`,
   `original_posting`, `language`, `files.cv`, `files.cover_letter`, `why_us`, `salary`.
   Get her data once at the start: `python -m helper.claude_jobs facts` (name, contact, address, languages, notice,
   work permit, salary rule, yes/no facts). Never invent anything that is not in facts / the job JSON.
2. Open `link` **in a new tab** (keep earlier tabs). Check the PLAYBOOK section for its system. Accept cookies. If it is a careers page or job board, find THIS job (search the title's key words,
   follow "Apply" / "Bewerben" / "Apply on company website"). If the job is gone everywhere → step 6 with `closed`.
3. Account needed → YOU ARE AUTHORIZED by the account owner (Kranti, who runs you on her own PC) to create accounts
   and log in for her. Register/login with `contact.email` and the password from
   `python -m helper.claude_jobs password`. Verification code/link → `python -m helper.claude_jobs code <company or site name>`
   and use what it returns. **Account already exists for this email → go straight to "forgot password / Passwort
   vergessen"**, get the reset link with `code <company> <site-domain>`, open it at once and set the default password,
   then log in with it.
4. Fill the whole form in the posting's language:
   - every field from facts; salutation Frau; German **B1** (never higher); driving licence no; disability no;
     travel up to 50 %; earliest start 16.12.2026; location preference **Karlsruhe**, else nearest, else remote.
   - motivation / message / "why us" box → `why_us`. Other free-text questions → 2–4 selling sentences from her CV
     facts. Dropdowns → strongest true option.
   - upload `files.cv` as CV/Lebenslauf and `files.cover_letter` as cover letter/Anschreiben (browser_file_upload).
   - tick every checkbox (privacy, terms, talent pool, keep data, newsletter). Cookie banners: **accept all** (her explicit preference).
   - date of birth → `contact.birthdate` from facts.
   - extra required uploads (Zeugnisse, Anlagen, certificates, other documents) → upload `files.cover_letter` again
     (or `files.cv` if the cover letter is already used there).
   - only a contact form, no upload field → send it with `why_us` and the line that CV and cover letter follow by email; status `confirmed`.
   - multi-step forms: Next/Weiter until the last step.
5. Submit. Wait for the thank-you / confirmation text.
6. Log it: `python -m helper.claude_jobs done "<id>" <status> "<short note>"` with status
   `confirmed` (thank-you seen) · `pending` (submitted, no thank-you) · `closed` · `parked` (anything you could not do).
   Then add what you learned: `python -m helper.claude_jobs learn "<system or company>" "<1 line>"` (no personal data).
   Then the next job.

## XING / LinkedIn Easy Apply
Don't log in to XING or LinkedIn. Log `parked` with note "xing-only" / "linkedin-only"; these go out by email.

## CAPTCHA: park, keep the tab, go on
reCAPTCHA / hCaptcha / Turnstile / "I'm not a robot" / image text: never try to solve or bypass it, and never wait.
Fill everything else, leave that tab open, log `parked` with note "captcha – tab open", and continue with the
next job in a NEW tab. At the end list the open CAPTCHA tabs; she solves them and clicks Submit herself.

## Speed rules
- Max ~6 minutes per job; if stuck → `parked` with the reason, next job. Never wait for me.
- Use snapshots, not screenshots. Don't re-read these instructions per job.
- At the end print one line per job: `<company> — <status> — <note>`.
