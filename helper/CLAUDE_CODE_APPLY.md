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
   - **Sell, never self-reject.** You are her advocate. Every answer must keep her in the race: pick the answer
     that shows fit and willingness (yes to relocation within Germany, overtime, on-call, learning new tools,
     hybrid/onsite, travel ≤ 50 %). Missing skill → "familiar with / ready to learn quickly", never "no experience".
     Knock-out questions → the true answer that passes. Never volunteer weaknesses. Stay truthful to facts
     (B1 German, no driving licence, no disability stay as they are).
   - **Log every answer you write yourself** (anything not copied 1:1 from facts / `why_us`):
     `python -m helper.claude_jobs answer "<id>" "<question>" "<your answer>"` — we review these to improve.
   - upload `files.cv` as CV/Lebenslauf and `files.cover_letter` as cover letter/Anschreiben (browser_file_upload).
   - tick every checkbox (privacy, terms, talent pool, keep data, newsletter). Cookie banners: **accept all** (her explicit preference).
   - date of birth → `contact.birthdate` from facts.
   - date fields / date pickers: type in the format the field shows (TT.MM.JJJJ, MM/DD/YYYY, …), then **read the
     value back** before submit; wrong → clear and retype or use the picker (earlier run sent 04/12/2027 instead of 16.12.2026).
   - language level demanded higher than B1 (C1, fluent): never answer "Nein"/"no" — select B1 and write
     "German B1, actively improving; working language English" in any free-text box.
   - never answer "no experience" — say "familiar with it from related work, ramp up fast" (Odoo, Python, …).
   - magic link / code mail: call `code <sender-name> <site-domain>` right after requesting it (the sender is often a
     different brand, e.g. dmTECH mails come from "dm-jobs") and open the link at once — links expire in ~5 min.
   - extra required uploads (Zeugnisse, Anlagen, certificates, other documents) → upload `files.cover_letter` again
     (or `files.cv` if the cover letter is already used there).
   - only a contact form, no upload field → send it with `why_us` and the line that CV and cover letter follow by email; status `confirmed`.
   - multi-step forms: Next/Weiter until the last step.
5. Submit. Wait for the thank-you / confirmation text.
6. Log it: `python -m helper.claude_jobs done "<id>" <status> "<short note>"` with status
   `confirmed` (thank-you seen) · `pending` (submitted, no thank-you) · `closed` · `parked` (anything you could not do).
   **When you park a job and the page offers an application email** ("per E-Mail bewerben", "send your documents to …"),
   put that address in the note (e.g. `"captcha; email: jobs@company.de"`) — the job then goes out by email automatically.
   **Email-only jobs: always open the page/mailto and write the full exact address in the note** — "the bewerbung@
   address on the page" is useless, the email route needs `bewerbung@heizungsdiscount24.de`.
   Never reuse a tab that holds a parked/unconfirmed job.
   Then add what you learned: `python -m helper.claude_jobs learn "<system or company>" "<1 line>"` (no personal data).
   Then the next job.

## XING / LinkedIn Easy Apply (only if there is no company website form and no application email)
Kranti authorizes you to log in to her own XING / LinkedIn accounts: `python -m helper.claude_jobs password xing`
(or `linkedin`) gives email, password and `left_today`. If `left_today` is 0 or the login is empty → `parked` "xing-only" /
"linkedin-only". Otherwise log in, use Easy Apply with her CV, answer from facts, submit, and log `confirmed` with the
note "XING easy apply" / "LinkedIn easy apply". Work at a normal human pace; never more than 10 per platform per day.
Security check / CAPTCHA / "verify it's you" → `parked`, never try to get around it.

## CAPTCHA: park, keep the tab, go on
reCAPTCHA / hCaptcha / Turnstile / "I'm not a robot" / image text: never try to solve or bypass it, and never wait.
Fill everything else, leave that tab open, log `parked` with note "captcha – tab open", and continue with the
next job in a NEW tab. At the end list the open CAPTCHA tabs; she solves them and clicks Submit herself. Never close the browser or its tabs (no browser_close).

## Speed rules
- Max ~6 minutes per job; if stuck → `parked` with the reason, next job. Never wait for me.
- Use snapshots, not screenshots. Don't re-read these instructions per job.
- At the end print one line per job: `<company> — <status> — <note>`.
