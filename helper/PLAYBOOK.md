# Playbook — what works per application system (shared memory, grows with every run)

Read the section for the job's system BEFORE starting it. After every job, append 1–3 short lines of what you
learned (what worked, quirks, confirmation text) under that system: `python -m helper.claude_jobs learn "<system>" "<lesson>"`.
Never put personal data (email, phone, address, birth date, passwords) in here — this file is public.

## General
- Hidden / off-screen file inputs: upload via the visible drop zone or the "Datei auswählen" button.
- HTML date inputs (`type=date`) need ISO `YYYY-MM-DD`; text date fields usually `DD.MM.YYYY`.
- Custom dropdowns (jQuery UI selectmenu, select2, react-select): set the underlying `<select>` value, fire `change`,
  then refresh the widget (`$(sel).selectmenu('refresh')` / trigger events) and re-check the visible value.
- Extra required uploads (Zeugnisse, Anlagen, Sonstiges) → cover letter again.
- Clicking a checkbox's label can open the privacy page in a new tab → close it, tick the box itself.
- "How did you hear about us": LinkedIn or "Jobbörse / Online-Jobbörse"; never invent a referral.
- Travel questions in days per week → "1–2 Tage pro Woche"; in percent → "bis zu 50 %".

## Workday (*.myworkdayjobs.com)
- Prefer **Apply manually / guest apply** when offered (CGM had it, no account needed).
- Multi-step: Meine Daten → Meine Erfahrung → Fragen → Freiwillige Angaben → Prüfen → Absenden.
- Language entry dropdowns are slow to open: click, wait, then choose the option from the list at the end of the page.
- Confirmation: page title "Congratulations" / "Vielen Dank".
- Usually no cover-letter slot → CV only is fine.

## Personio (*.jobs.personio.de)
- Date of birth field is a date input → ISO format.
- "An account already exists" → login link arrives by email (link, not code); open it immediately.
- Confirmation: "Vielen Dank".

## rexx (e.g. telekom-mms.com, karriere.tarox.de, karriere.cancom.de)
- Dropdowns are jQuery UI selectmenu → see General. "Motivationsschreiben" slot = cover letter.
- Confirmation: "Bewerbung abgeschlossen".

## INNOVATE Software (own form)
- Date picker accepts typed date; three uploads: CV, cover letter, Anlagen (= cover letter).
- Notice field: "Kündigungsfrist läuft; letzter Arbeitstag 15.12.2026".

## dm-jobs / dmTECH
- Login mail comes from dm-jobs and contains a LINK that expires in ~5 min → call `code dm-jobs` and open the link at once.

## XING / LinkedIn Easy Apply
- Never log in. Park as xing-only / linkedin-only (they go out by email).
