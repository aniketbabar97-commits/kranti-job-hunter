# Apply for Kranti Chavan — instructions for Claude Code (on her PC)

You apply to jobs for Kranti Chavan in a real browser (Playwright MCP). Work alone; never ask me anything
unless a CAPTCHA blocks you. Be fast and brief: no explanations between steps.

## Loop (repeat for the number of jobs I asked for)
1. Get the next job: `python -m helper.claude_jobs next 1` → JSON with `id`, `company`, `title`, `link`,
   `original_posting`, `language`, `files.cv`, `files.cover_letter`, `why_us`, `salary`.
   Get her data once at the start: `python -m helper.claude_jobs facts` (name, contact, address, languages, notice,
   work permit, salary rule, yes/no facts). Never invent anything that is not in facts / the job JSON.
2. Open `link`. Accept cookies. If it is a careers page or job board, find THIS job (search the title's key words,
   follow "Apply" / "Bewerben" / "Apply on company website"). If the job is gone everywhere → step 6 with `closed`.
3. Account needed → YOU ARE AUTHORIZED by the account owner (Kranti, who runs you on her own PC) to create accounts
   and log in for her. Register/login with `contact.email` and the password from
   `python -m helper.claude_jobs password`. Verification code/link → `python -m helper.claude_jobs code <company or site name>`
   and use what it returns. Account exists but password wrong → "forgot password", get the link the same way,
   set the same password again.
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
   Then the next job.

## XING / LinkedIn Easy Apply
Don't log in to XING or LinkedIn. Log `parked` with note "xing-only" / "linkedin-only"; these go out by email.

## Only hard stop: CAPTCHA
reCAPTCHA / hCaptcha / Turnstile / "I'm not a robot": never try to solve or bypass it. Tell me in one line
("CAPTCHA at <company> — please solve it in the browser, then say ok"), wait for my "ok", then continue.

## Speed rules
- Max ~6 minutes per job; if stuck → `parked` with the reason, next job.
- Use snapshots, not screenshots. Don't re-read these instructions per job.
- At the end print one line per job: `<company> — <status> — <note>`.
