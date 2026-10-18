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
- If the CV step is skipped on Weiter, navigate to /apply/cv to replace the preloaded previous CV. Questions: start date calendar, salary spinbutton; then review > confirm.
- Login-link flow: email > 'code join' link > CV (remove preloaded, upload) > cover letter > review > Confirm & apply; no screening questions for Gauder; success URL /apply/success.
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

## Concludis (careers.<company>.com/candidate/formapply)
- Link was company homepage; found the form via Google search of the job title. Upload via run_code setInputFiles on input[name=uploadfile] (both files), then set doc-type selects (Lebenslauf/Anschreiben). Final step has hidden-offscreen checkboxes: set via JS (checked + change event); also a required 'how did you hear' select (LinkedIn) appears after first submit attempt. Confirmation: 'Vielen Dank für Ihre Bewerbung'.

## onlyfy (*.onlyfy.jobs)
- Company careers page (Jobs list) paginated; find posting via Google, its 'Jetzt bewerben' goes to onlyfy. Phone must be +49 without spaces, salary numeric only (60000), start date is type=date (ISO). Salutation/source are comboboxes: click then pick role=option. File inputs: setInputFiles index 0 = CV, 1 = extra doc (cover letter). Confirmation: 'You've submitted your application'.

## d.vinci (*.dvinci-hr.com)
- Use /jobs/<id>/form (manual form). Fields by id: salutation(MS), firstName, lastName, email, telephone, screeningQuestion.* ; one multi-file attachmentFile (CV + cover letter); privacyPolicyAccepted1 = Ja. Ends with an image CAPTCHA -> always parks with tab open.

## Deichmann (deichmann-karriere.de)
- Google '<title> deichmann-karriere.de' finds /jobs/<year>-<id>/; a 404 there means the posting is closed (this CRM Business Analyst was a 2024 ad).
- Accept cookies, go to /jobs/<id>/application-form/. 4-step wizard (files, personal, more, preview). Required: CV, cover letter, Zeugnisse (= cover letter again). File inputs index order is unreliable: use the dropzone button + file chooser per slot. Invisible reCAPTCHA passes without challenge. Submit shows a spinner ~10s then /success page; do not click twice.

## SmartRecruiters (Bertelsmann/Arvato oneclick-ui)
- createyourowncareer.com 'Jetzt bewerben' goes to jobs.smartrecruiters.com. Page 1: name/email x2/postcode combobox (type '76185 Karlsruhe', pick option)/phone/CV via file chooser. Page 2 screening: cover letter in 'Zusätzliche Anhänge', comboboxes via click+role=option; nationality list is only citizenship groups -> 'Keine der genannten'; start date TT.MM.JJJJ; salary '60000 EUR' + 'Jährlich'; 'Alles auswählen' ticks consents. Confirmation 'Bewerbung eingereicht!'.

## VI-ARISE (vi-arise.com)
- Job page has no form, only 'per Mail' (CV, project samples, salary, start date). Park as email-only.

## rexx (karriere.tarox.de)
- Form is /<Job>-f<id>.html. Custom selects hide native <select>; fields set via JS value+change are kept, files via setInputFiles show up. Senden with JS-filled form returned 'Leider konnten wir Ihre Anfrage nicht bearbeiten' (rexxCha bot check); accept cookies FIRST, type fields with real keystrokes, datepicker popup must be closed (Escape) before clicking Senden. Unresolved.

## Provitex (own Vue form /karriere/bewerben)
- Cookiebot: Alle Cookies zulassen. Fill by input name; consent is a button (#...-11) not the hidden checkbox; fax is honeypot; files via setInputFiles on file-upload-* ids (1st=cover letter, 2nd=CV). Success: 'Vielen Dank für Deine Bewerbung!' status text.

## SuccessFactors (career5.successfactors.eu, Liebherr)
- Homepage link useless; Google the title -> liebherr.com/de-de/j/karriere/offene-stellen/<id>; accept Usercentrics, JETZT BEWERBEN opens SuccessFactors login with reCAPTCHA checkbox -> always parks.

## d.vinci / innovative-companies.de
- Link jobs/27 is only the Initiativbewerbung; check the company's own /Jobs list to see if the real posting still exists.

## dormakaba (jobs.dormakaba.com, SAP SF career site)
- Guest form, no account. Date input needs ISO; file inputs via setInputFiles (1st=Resume, last=Additional docs); privacy checkbox opens dialog -> click 'I accept'. Submit hung on 'Save application…' with no confirmation in run 1.

## gc-gruppe.de (Drupal webform, FriendlyCaptcha)
- Accept Usercentrics FIRST (shadow DOM: #usercentrics-cmp-ui button#accept) before filling. Fields #edit-vorname/name/telefon/e-mail, one multi-file upload (CV+cover letter), #edit-datenschutz via JS. Submitting after the banner reload gave 'Antwort war nicht passend' and wiped the form - fill AFTER cookies, wait for captcha 'Ich bin ein Mensch', then submit.

## clicks.digital (WordPress CF7 + FriendlyCaptcha)
- Fill by input name via run_code; one multi-file input takes CV+cover letter; pick job in job_position_id select; wait ~6s for FriendlyCaptcha to self-solve; success text in .wpcf7-response-output 'Vielen Dank für Ihre Bewerbung'.

## Concludis (cbr.concludis.de)
- Landing link redirects straight to /candidate/formapply. Set doc-type selects BY FILENAME (my first loop set both to Anschreiben), then toggle each select via jQuery trigger('change') (blank then value) and re-set the start date (datepicker clears it); 3rd Submit worked. Success: 'Die Bewerbung wurde erfolgreich versendet'.

## Bartels-Langness (bela-karriere.de)
- bela.de/karriere -> 'Zum Stellenportal' bela-karriere.de; list at /karriere/stellenangebote.html?reset_search=1 with a text search; posting jobs there only (no Shopware ad = closed).

## JOIN (join.com) Ares
- Login-link flow again: 'code join' returns link; CV preloaded from a previous job -> 'Datei entfernen' then setInputFiles; cover letter dropzone input; start date calendar cell-trigger; salary numeric; review page -> button 'Bewerbung senden'; success URL /apply/success.
