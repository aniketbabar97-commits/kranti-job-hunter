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

## JOIN (join.com)
- Second+ application: already logged in, steps are skipped/prefilled. JOIN auto-loads the PREVIOUS job's CV - click 'Datei entfernen' and upload this job's CV (and check cover letter). Date question is a calendar: click inner [id$=cell-trigger:YYYY-MM-DD] (not the gridcell) after 'next month'. Success: 'Bewerbung gesendet' / 'Application sent'.
- Apply now > email > CV upload (dropzone click then file chooser) > personal info (city combobox: type, pick option) > screening questions one per page > review > Confirm & apply > verify email link (use 'code join') > success page. Salary field numeric; use upper part of range.

## PS Direkt (own form)
- Link was homepage; job found by scanning /stellenangebote/pageN/ (title slightly renamed). File inputs hidden: click the label 'Datei auswählen', then file_upload. Tick #privacy via JS (label click opens privacy page). Confirmation: 'Vielen Dank für Ihre Bewerbung'.

## softgarden (karriere.<company>.de)
- Apply link redirects to React form; 3 steps: CV (click 'Lebenslauf hochladen' label, file chooser), extra attachments zone = cover letter, personal data (Anrede is react-select: click its container, pick option), extra questions + FriendlyCaptcha (self-completes, 'Ich bin ein Mensch'). Confirm: overlay 'Vielen Dank, die Bewerbung ist bei uns erfolgreich eingegangen'. Hidden thank-you text exists in DOM before submit - check screenshot.

## Greenhouse (job-boards.eu.greenhouse.io)
- ionos-group.com 'Jetzt bewerben' goes to Greenhouse. Uploads: click first 'Anhängen' per group (CV, Anschreiben). react-select: click 'Flyout umschalten' button then pick option; country list is localized ('Deutschland'); city needs typing then ArrowDown to show options. Multi-select ignores typed+Enter; click options. Confirmation: URL /confirmation 'Vielen Dank für Deine Bewerbung'.

## Workday (Accenture)
- Apply Manually > Sign in with email > Create Account; submit buttons are covered by a click_filter div (click [data-automation-id=click_filter]). After creating the account sign-in failed and no verification mail was found - needs manual check.

## Ashby (jobs.ashbyhq.com)
- Use /application URL. Fastest via run_code: fill by input id/name, setInputFiles on file inputs by id (cover letter input appears after choosing 'Upload a Cover Letter'), typeahead (city, how heard): fill then click role=option. Dates MM/DD/YYYY. 'Preferred Name' is required. Confirmation: 'Thank you for your application!'.

## netcare.de (own Contact Form 7)
- Form at /karriere/jetzt-bewerben/<slug>/. Fill by input name via run_code, setInputFiles on file inputs 0/1 (CV, cover letter). Datepicker popups block clicks: Escape + hide .datepicker, use click force. 'How heard' select has a second dependent select (channel-online) that is required. Success: redirect to /danke-fuer-deine-bewerbung/.

## Personio (*.jobs.personio.com)
- remotely.de job page has the real Personio link. Apply URL /job/<id>/apply?display=de. Fast via run_code: fill by name (first_name,last_name,email,phone,available_from,salary_expectations,custom_attribute_*), setInputFiles on documents.cv / documents.cover-letter. No CAPTCHA seen. Confirmation 'VIELEN DANK'.
