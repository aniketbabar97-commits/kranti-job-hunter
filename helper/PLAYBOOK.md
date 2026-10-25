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
- Cookie banner: shadow DOM button#accept via JS. Mail-Login field is a web component - real mouse clicks by coordinates (scroll with mouse.wheel), then 'code dm-jobs'. Wizard fields by id; final button is 'Bewerbung absenden' (getByRole, JS click) - NOT button[type=submit] (that is the header search and discards the form). 409 ALREADY_EXISTS = application already on file. Logout timer 15 min; each slow tool call burns it.
- Apply wizard: fill step 1 with ISO date (type=date) via locators; Weiter link is covered by an error overlay - click via JS .dm-apply-page__btn-next. Existing profile for the email -> send magic link, 'code dm-jobs', open link immediately; profile prefill has wrong birth year/address, re-fill them. Old CV and 'Weitere Dokumente' carry over: Datei entfernen, then Dokument hochladen > tab 'Von meinem Gerät' (scope #cv / #coverLetter) > file chooser. Success text only shown after scrolling to bottom: 'Deine Bewerbung ist erfolgreich bei uns eingegangen'.
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
- Existing account: Forgot password works (SignInWithEmailButton -> forgotPasswordLink -> 'code Accenture myworkdayjobs.com' returns passwordreset link -> set default password -> sign in). Use [data-automation-id=click_filter] to click submits. Earlier 'sign-in failed' was a wrong password, not a missing verification mail. Signed in, job page showed 'You've already applied for this job'.
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
- Site search and /jobs/ are unreliable. Open the department page (e.g. /omnichannelcommerce/) and read a[href*='/jobs/20'] hrefs, verify title by fetching /jobs/<id>/ and reading <title>, then go to /jobs/<id>/application-form/. Wizard: 3 dropzones + Zeugnisse(=cover letter), personal (Telefon = digits only, Geburtsjahr only), more (date is ISO), Datenschutz #invalidCheck via JS, submit via #submit-btn_zent_berf; spinner ~25s then /success.
- Google '<title> deichmann-karriere.de' finds /jobs/<year>-<id>/; a 404 there means the posting is closed (this CRM Business Analyst was a 2024 ad).
- Accept cookies, go to /jobs/<id>/application-form/. 4-step wizard (files, personal, more, preview). Required: CV, cover letter, Zeugnisse (= cover letter again). File inputs index order is unreliable: use the dropzone button + file chooser per slot. Invisible reCAPTCHA passes without challenge. Submit shows a spinner ~10s then /success page; do not click twice.

## SmartRecruiters (Bertelsmann/Arvato oneclick-ui)
- createyourowncareer.com 'Jetzt bewerben' goes to jobs.smartrecruiters.com. Page 1: name/email x2/postcode combobox (type '76185 Karlsruhe', pick option)/phone/CV via file chooser. Page 2 screening: cover letter in 'Zusätzliche Anhänge', comboboxes via click+role=option; nationality list is only citizenship groups -> 'Keine der genannten'; start date TT.MM.JJJJ; salary '60000 EUR' + 'Jährlich'; 'Alles auswählen' ticks consents. Confirmation 'Bewerbung eingereicht!'.

## VI-ARISE (vi-arise.com)
- Job page has no form, only 'per Mail' (CV, project samples, salary, start date). Park as email-only.

## rexx (karriere.tarox.de)
- WORKED with cronos recipe: pressSequentially per field by id, native selects via JS value+change, setInputFiles on #fld_ ids for anschreiben+lebenslauf, #agb_checkbox via JS, then JS/force click on last a:has-text('Senden') (role link lookup fails). Title 'Bewerbung abgeschlossen'.
- Form is /<Job>-f<id>.html. Custom selects hide native <select>; fields set via JS value+change are kept, files via setInputFiles show up. Senden with JS-filled form returned 'Leider konnten wir Ihre Anfrage nicht bearbeiten' (rexxCha bot check); accept cookies FIRST, type fields with real keystrokes, datepicker popup must be closed (Escape) before clicking Senden. Unresolved.

## Provitex (own Vue form /karriere/bewerben)
- Cookiebot: Alle Cookies zulassen. Fill by input name; consent is a button (#...-11) not the hidden checkbox; fax is honeypot; files via setInputFiles on file-upload-* ids (1st=cover letter, 2nd=CV). Success: 'Vielen Dank für Deine Bewerbung!' status text.

## SuccessFactors (career5.successfactors.eu, Liebherr)
- Homepage link useless; Google the title -> liebherr.com/de-de/j/karriere/offene-stellen/<id>; accept Usercentrics, JETZT BEWERBEN opens SuccessFactors login with reCAPTCHA checkbox -> always parks.

## d.vinci / innovative-companies.de
- Link jobs/27 is only the Initiativbewerbung; check the company's own /Jobs list to see if the real posting still exists.

## dormakaba (jobs.dormakaba.com, SAP SF career site)
- WORKED: form is in shadow DOM (page.locator pierces; frame refs prefixed f12e..). Dropdowns = button + li (referral list: use .last()); date input ISO; file inputs: setInputFiles on input[type=file] nth0=Resume nth1=Additional docs (chooser never opens); a required salary textarea appears after first Apply attempt; consent radio via label text, checkbox via JS click. Success = full-page modal 'Thank you for your application!'.
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

## Musik Meyer (TYPO3 powermail)
- Form /bewerbungsformular: name, email, ONE single-file upload (merge cover letter+CV with pypdf), consent; Absenden then a confirm page -> click 'Weiter'. Success: 'Vielen Dank. Wir haben Ihre Nachricht erhalten'.

## SuccessFactors (jobs.innomotics.com / career5)
- No CAPTCHA seen. Accept Usercentrics (shadow DOM button[data-testid=uc-accept-all-button]) first; Jetzt bewerben > Konto anlegen > emailed passcode ('code innomotics') > profile page. Upload CV/cover via 'Von Gerät hochladen' then file chooser. CV parse prefills; delete empty education row, set Degree/Major comboboxes via click + role=option, DOB TT.MM.JJJJ. Disability combobox has no 'Nein' - left blank. Bewerben -> title 'Erfolgreich angewendet'.

## JOIN (join.com) Holz-Richter
- Company /karriere/casando page links to JOIN. Direct URL join.com/companies/<co>/<id>/apply works; email > 'code join' link > remove preloaded CV, dropzone button name 'dropzone' + file chooser > cover letter > start-date calendar (2x next month, cell-trigger) > screening questions (salary number, city textarea, on-site Ja) > 'Bestätigen & bewerben'.

## Personio (*.jobs.personio.de) ValueNet
- Direct /job/<id>/apply?display=en works. Fill by #field-<name> ids via fill_form (selects by option text); 'Add file' click opens chooser, a 2nd file lands in the same CV slot (fine). Screening selects may ask skills not in CV (Odoo/Python) - answer truthfully. Confirmation 'THANK YOU'.

## Personio (amplio.jobs.personio.de)
- Direct /job/<id>/apply?display=de; fill_form by #field-* ids (birthday is type=date ISO, experience select '5–6 Jahre'); each 'Datei hinzufügen' (nth 0 cover, 1 CV) opens chooser. No CAPTCHA. Confirmation 'Wir haben deine Bewerbung erhalten'.

## Piazza Blu (piazzablu.com contact form)
- Job page has a form (position select #position-contact, name, email, phone, message, multi-file label[for=job-contact-input]). Click 'Alle akzeptieren' cookie modal first. Success = Senden button text becomes 'Gesendet' (no thank-you page); Turnstile is invisible.

## Workday (Philips)
- Guest 'Apply Manually' works, no account/CAPTCHA. Open <job>/apply then Apply Manually. 'How did you hear' multiselect: click box, TYPE 'LinkedIn', Enter (clicking an option then Enter picks a wrong item). Step2 'Select files' accepts CV+cover letter in one file_upload. Questionnaire dropdowns: click button by id then role=option. Terms checkbox #termsAndConditions--acceptTermsAndAgreements, Submit = pageFooterNextButton. Title 'Congratulations'.

## JOIN (join.com) Nordason
- Already logged in: /apply lands on /apply/cv with previous CV -> Datei entfernen, dropzone, upload; same flow. German-level question options A-F: B1 = 'Gute Kenntnisse'; optional multi-checkbox question can be skipped.

## Heizungsdiscount24 (own site)
- Homepage link -> /jobs.html -> 'Zur Stellenbeschreibung'; posting page has no form, only a mailto for PDFs. Park as email-only.

## Ensinger (jobs.ensingerplastics.com, Persis engage)
- Cookies > Jetzt bewerben x2 > page1 privacy+pool checkboxes > page2 form. File inputs overlaid: click input[type=file] by class (fieldMandatory = CV; .multiuploadFile = extra, pick category Anschreiben first, then Hinzufügen). Free-text Kündigungsfrist/Eintritt. Confirm: title 'Danke'.

## Concludis (cbr.concludis.de) CBR 2
- LinkedIn link has no external URL: use www.cbr.de/career/job-search?searchTerm=<title> > job page > 'Jetzt online bewerben' (landingpage.php?prj=115P<id>) > formapply. Filled all via one evaluate (set value+change); Verfügbarkeit radio value 1 'Ab dem...' reveals start date; after setInputFiles set each .file-row select by its .filename (Cover->Anschreiben, CV->Lebenslauf). 1st submit worked.

## Personio (brandung.jobs.personio.de)
- /apply?display=en; fill_form by #field-*; setInputFiles #doc-input-cv and #doc-input-other (cover letter); no consent checkbox; screening 'C1 German?' answered Nein (B1, truthful) and was accepted. Confirmation 'VIELEN DANK'.

## softgarden (ampelmann.softgarden.io)
- ONLINE BEWERBEN opens a NEW tab (/applications/<id>): single page. CV via the visible 'PDF / DOC' <a> (not the hidden input) + file chooser, page re-renders so re-snapshot refs; cover letter = 'Other attachments' button + chooser; salutation is a chosen.js select (click #id1_chosen then li 'Ms.'); no captcha, no consent checkbox. Success URL /applySuccess.

## rexx (www.cronos.de/jobs, f<id>.html)
- WORKED: accept cookies first, then pressSequentially per field (close/hide #ui-datepicker-div before clicking later fields), setInputFiles by id, tick #agb_checkbox via JS, set required select wie_gefunden (Arbeitsagentur) via JS+change, click 'Senden' link. Success 'Bewerbung abgeschlossen'.
- Same rexxCha rejection as tarox: submit returns 'Leider konnten wir Ihre Anfrage nicht bearbeiten' 2x with JS-filled fields. Uploads use ajax (setInputFiles works; filenames then shown; input names are swapped: name=anschreiben is CV slot, anlage3 Zeugnisse, lebenslauf = Anschreiben). Cookie 'Alle akzeptieren' (save_all_settings) reloads the page - do it BEFORE filling. Treat as captcha: park with tab open.

## Arbeitsagentur link / Die Tech Recruiter
- arbeitsagentur.de hides the employer contact behind a Sicherheitsabfrage (captcha) - don't use it; search the employer's own site instead. dietechrecruiter.de/jobs/ is paginated with ?paged=2 (fetch it); job page /jobs/<slug>-vac-<id>/ has firstName/lastName/email/phone, single CV file input name=cv, dataprivacycheck; Cookiebot accept first. Success /thank-you-cv/.

## Noerr Solutions (noerr-solutions.de, WP AWSM job form)
- Link was homepage: Cookies (cmplz) > /jobs/ > /job/<slug>/. Form fields awsm_*; date is type=date ISO; one multi-file input takes CV+cover letter; privacy awsm_form_privacy_policy; invisible reCAPTCHA v3 passed. Success text 'Vielen Dank für Deine Bewerbung' shown inline.

## QUIS AG (quis.ag)
- Real site is quis.ag (quis.de is an unrelated Hamburg proptech). Jobs at /stellenangebote/; absent from list + wp-sitemap.xml = closed.

## d.vinci / innovative-companies.de (MACS HOLDING)
- macs-holding.de/stellenangebote lists the job linking to innovative-companies.de/de/jobs/<id>/...; go straight to /de/jobs/<id>/form. Fill by name (salutation MS, sourceId 13=LinkedIn, videoPitch0=Nein, privacyPolicyAccepted1, extendedUseAccepted1), one multi-file attachmentFile takes CV+cover letter. NO image CAPTCHA this time: Absenden went to /applied 'Wir haben die Bewerbung erhalten. Vielen Dank.'

## rexx (telekom-mms.com)
- Same recipe as cronos works (cookies first, pressSequentially, setInputFiles by id, JS-tick #agb_checkbox, click 'Senden'). After submit page shows only 'Eine Bewerbung pro Stellenausschreibung ist nur einmal möglich' - no thank-you text.

## SuccessFactors (rehau.jobs / career5 rehauagco)
- 2nd+ application: profile stays logged in/prefilled; just replace CV (pencil button -> Von Gerät hochladen) and cover letter (löschen -> OK -> Anschreiben anhängen), then re-fill the job-specific salary/currency/frequency/permit/source fields (they reset per requisition; Währung is a native select -> selectOption) and click Bewerben.
- Job page 'Jetzt bewerben' dropdown is LinkedIn-only; run JS click on a.dialogApplyBtn to reach career5 login. Register link -> Konto anlegen (needs radio searPref + accept privacy dialog). Then profile page: CV/cover letter via 'Von Gerät hochladen' + filechooser (use page.waitForEvent filechooser), custom comboboxes: click then li in ul.sf-list-select (clicking twice toggles it closed; check count). CV parse adds experience/education rows with required Bereich(IT)/Führungserfahrung(Nein)/Dauer/Von dates/Abschluss(Bachelor) - fill them, then Bewerben. Success: 'Vielen Dank! Wir haben Ihre Bewerbung erhalten'.

## SuccessFactors (jobs.all-for-one.com / career2 all41Group)
- Job page -> JS click a.dialogApplyBtn -> guest form on career2 (also creates account). If 'Konto bereits vorhanden': open 'Hast du dein Kennwort vergessen?' href in a NEW tab, submit email, 'code All for One successfactors.eu' returns reset link, set default password, then log in on the form tab ('Bitte melde dich hier an.'): profile form shows with an old CV -> pencil to replace CV, 'Motivationsschreiben anhängen' for cover letter (chooser needs browser_file_upload after the click), fill Anrede/Land/source combos (ul.sf-list-select li), salary/notice, Bewerben. Success 'Ihre Bewerbung wurde abgeschickt. Vielen Dank!'.

## Vesterling AG (vesterling.com JobBox)
- LinkedIn link has no company URL: vesterling.com/jobs-finden/technologie-stellenmarkt/ lists the job -> job page 'Online bewerben' -> /jobs-finden/jetzt-bewerben/ (form says 'Sie bewerben sich für folgende Position'). Fields by id: salutation select, lastName, firstName, tel, email, #privacy, #newsletter, linkXingOrLinkedIn, radio sendingPapersInput_1 + #files takes CV+cover letter; button 'Bewerbung absenden'. Success text 'Vielen Dank für Ihre Bewerbung bei Vesterling!' appears in place; ignore the separate nf- contact form below.

## BTC AG (karriere.btc-ag.com/?jobid=...)
- LinkedIn link -> karriere.btc-ag.com home lists job -> /?jobid=<id>; accept Cookiebot, click first 'Jetzt bewerben' to open the inline form (no <form> tag). Phone field is digits only (+49 prefix is fixed). Two file inputs: CV, 'Weitere Unterlagen' (cover letter). Selects: residence 'innerhalb der EU', langLevel B1, disability nein. Submit = the 'Jetzt bewerben' <a> inside .application__mainContainer (click via DOM, overlays block pointer). The Einstiegsdatum date input mangles typed dd.mm.yyyy (became 04/12/2027) - leave it empty and put start date in the message instead. Success: 'Bewerbung wurde erfolgreich versendet'.

## EPAM (careers.epam.com)
- epam.com/careers link is useless: use careers.epam.com/en/jobs/germany?query=<title> (default geo is India), open /en/vacancy/<slug>, click APPLY (JS) -> modal. Fields #name,#surname,#email, country react-select (focus #react-select-4-input, type Germany, Enter), 'Experience*' = CV file input, #coverLetter is a single-line text (paste why_us), tick both checkboxes via getByRole+JS click, SUBMIT; invisible reCAPTCHA passes. Success modal 'Thank you! Your application has been submitted'.

## Bader (bader-karriere.de, WordPress)
- bader.de/karriere -> bader-karriere.de/stellenmarkt lists jobs; job page 'Jetzt online bewerben' -> /bewerbung/?job-titel=<title>. Fields #vorname #nachname #email #bewerbungstext, setInputFiles on #bader-verstecktes-datei-input (both PDFs), #datenschutz-checkbox, click #bader-absenden-button; bader_website is honeypot (leave empty). No captcha. Success 'Vielen Dank! Ihre Bewerbung wurde erfolgreich versendet'.

## foobar Agency (foobar.agency)
- foobar-agency.com does not resolve; real site foobar.agency/en/team lists jobs -> /en/jobs/<slug>. Apply Now opens a HubSpot contact form (iframe, needs Cookiebot accept-all) that blocks gmail.com addresses and requires a company name, no file upload -> park as email-only (recruiter address on the team page).

## eBakery (ebakery.de/karriere)
- Job listed in accordion on /karriere/; 'JETZT BEWERBEN' is only mailto:kontakt@ebakery.de, no form -> email-only.

## Bayard GmbH (Köln)
- bayard-consulting.com times out and bayard.de is an unrelated placeholder; the Indeed ad only offers Indeed Schnellbewerbung -> park.

## Birkenstock (careers.birkenstock-group.com)
- jobs.birkenstock-group.com redirects to careers.birkenstock-group.com/us/en; search-results?keywords=<x> and /c/ecommerce-digital-jobs list all openings; absent = closed.

## GetYourGuide (getyourguide.careers, Greenhouse embed)
- careers.getyourguide.com -> getyourguide.careers/open-roles; job /jobs/<id> embeds greenhouse iframe (job-boards.greenhouse.io/embed/job_app). Work in that frame: #first_name #last_name #email #phone (country react-select: focus, ArrowDown, type Germany, click option; phone national digits), setInputFiles on input[type=file] resume then #cover_letter (the cover input stays after CV upload); select questions are react-selects: focus, ArrowDown, click role=option by name; submit button[type=submit]. Success: frame URL /confirmation 'And...sent!'. reCAPTCHA enterprise is invisible.

## ABOUT YOU (corporate.aboutyou.de)
- Jobs list at /en/career/jobs has a text search (type + Enter); job pages are /en/career/jobs/<slug>; title absent from list and slug 404 = closed.

## SoftServe (career.softserveinc.com)
- Search via #vacancies-search or URL /en-us/vacancies/q-<keywords>; role absent from results = closed.

## Cegeka (jobs.cegeka.de, JobCenter iframe)
- LinkedIn link has no apply URL: jobs.cegeka.de/vacancy/?search=<kw> lists jobs; accept cookies, form is inline iframe #JobCenter (Anrede, DOB, name, email, phone, note, CV browse, 'Weiteres Dokument' type Sonstiges = cover letter, consent). Datepicker popup clears DOB if you click a day: type TT.MM.JJJJ then Tab. Success 'Vielen Dank für Ihre Bewerbung!'.

## LinkedIn recruiter posts
- Public post page (no login) shows full text; extract the email with a regex on document.body.innerText and park with 'email: <addr>'. Many are India-based roles.

## Kugellager-Express (kugellager-express.de)
- Site sits behind a Cloudflare 'Performing security verification' challenge (403) in the automated browser; treat as captcha and park.

## softgarden (karriere.schaefer-shop.de)
- Job page Jetzt-bewerben href goes to /application/<guid>/<id>/. Step 1: click Lebenslauf-hochladen label + file chooser; Weitere-Anhaenge zone = cover letter. Step 3 questions are text inputs + button lists; FriendlyCaptcha self-solves; Bestaetigen shows the thank-you.

## Markant (jobs.markant.com, Rexx-like own portal)
- jobad id -> Jetzt online bewerben -> Apply without registration -> applicationform_privacy page already has a visible reCAPTCHA checkbox before the form; always parks.

## Ensinger (Persis engage)
- Job list at jobs.ensingerplastics.com/engage/jobexchange/showJobOfferList.do?j=jobexchange (30 hits, homepage shows only some). Page 1 = two checkboxes then submit; page 2 fill by name suffix via JS (name01=Vorname, name02=Nachname, offerKnownBy select, intOrExternAgency radio Nein); click input[type=file].fieldMandatory for CV, select category Anschreiben then click input[type=file].multiuploadFile + Hinzufuegen for cover letter; Bewerbung absenden -> title Danke.

## Recruitee (abriogmbh.recruitee.com)
- Job list via /api/offers/ (JSON, careers_url); apply at <careers_url>/c/new. Fill by name (candidate.name etc.), file inputs need JS input.click() then file chooser (sticky logo blocks real clicks); phone: type with +49 prefix, digits alone are read as +1; Senden triggers a puzzle captcha -> parks.

## CGI (cgi.njoyn.com, njoyn)
- Jobs list: cgi.njoyn.com/corp/xweb/xweb.asp?CLID=21001&page=joblisting&CountryID=DE&lang=4 (rows have title text). Apply button is hidden input #BTN_ApplyNow (JS click) -> clients.njoyn.com login needing a session from the job page (direct URL gives 'Invalid request'). Login/register forms fire a 'Pflichtfelder' alert even when filled; default password gave invalid credentials. Unresolved: try Passwort vergessen with 'code CGI njoyn'.

## d.vinci (hansgrohe.dvinci-hr.com)
- Form /de/jobs/<id>/form: ids salutation(MS), firstName, lastName, email, telephone, screeningQuestion.*, privacyPolicyAccepted1, attachmentFile (click then one file_upload with CV+cover letter); image captcha text field #captcha -> always parks. Cookie btn is div.btn-cookie-light.

## HUBER SE (karriere.huber.de, finest jobs)
- Job list /stellenangebote.html -> job page ...-j<id>.html -> apply form ...-f<id>.html. Fill by id (gender, vorname, ..., berufsausbildung_m_sb=German level, wie_gefunden, whatsapp_opt), #agb_checkbox, leave 'website' honeypot empty; upload by JS-clicking fld_ file inputs (anschreiben, lebenslauf) + file chooser; 'Senden' link; no captcha; success title 'Bewerbung abgeschlossen'.

## softgarden (einhell.softgarden.io)
- karriere.einhell.com dead; einhell.softgarden.io/en/vacancies lists job -> 'Online bewerben' opens NEW tab einhell.career.softgarden.de/application. Cookie modal .ccm-root: buttons are ALLES ABLEHNEN then ALLES AKZEPTIEREN (pick the 2nd). Salutation react-select: click the visible 'Keine Angabe' text then role=option. Extra questions: salary textarea, start text, ja/nein radio, source buttons; FriendlyCaptcha self-solves; Bestätigen shows full-page thank-you.

## gc-gruppe.de (Drupal webform)
- Worked 2nd time: open job URL, JS-click Usercentrics #accept, wait 2s, fill by #edit-* ids, setInputFiles with both PDFs on #edit-bewerbungsunterlagen-upload (ajax), tick #edit-bestaetigung + #edit-datenschutz via JS, wait ~6s for captcha, click #edit-actions-submit force. Success text 'Vielen Dank für deine Bewerbung.' (form disappears).

## Tabris UG (Magento, Berlin)
- No employer site found via Google; aggregator php-entwickler.de/job/...-166305/extern redirects to learn4good.com behind Cloudflare -> park.

## Stroetmann (karriere.stroetmann.de, talentsconnect)
- Homepage link ok: /search?q=<kw> lists job -> job page has inline form (click 'Jetzt bewerben!' to reveal). Fill by type (select Anrede, text x2, email, tel, start select by Kündigungsfrist, salary number), one multi-file input takes CV+cover letter, tick both consent checkboxes via JS click, button 'Jetzt bewerben!' force click -> /success. No captcha.

## AF-mediaGROUP (af-mediagroup.it/karriere)
- Arbeitsagentur-only link: Google 'AF-mediaGROUP Full Stack Entwickler' finds af-mediagroup.it/karriere with Elementor contact form (name,email,message, no upload) -> sent why_us; success 'Deine Übermittlung war erfolgreich.' Docs address karriere@af-mediagroup.com.

## FAHMODA (fahmoda.de)
- Site has no careers/job page (only student admission); the Shopware/myfactory job exists only on aggregators -> park.

## Umantis (recruitingapp-*.de.umantis.com)
- Indeed link is Cloudflare-blocked; google title -> company career page -> Jetzt bewerben -> /Application/New. Fill by role; DOB mm/dd/yyyy; upload via button + file chooser (check input[type=file].files); privacy checkbox; 'Bewerbung definitiv einreichen' -> /Confirmation.

## Ernsting's family
- ernstings-family.com/karriere and career.ernstings-family.com give CloudFront 403 in the automated browser; jobs.de mirror has botchallenge -> park.

## Quellwerke (karriere.quellwerke.de, TYPO3 form)
- Indeed->quellwerke.de->karriere portal; /standard-bewerbung form takes ONE archive upload (ZIP CV+cover letter via python zipfile); cookie panel needs locator click on [data-omcookie-panel-save=all]; success URL /danke.

## Pro-Discount (pro-discount-werbeartikel.de)
- pro-discount.de redirects to pro-discount-werbeartikel.de/Jobs; posting titled 'E-Commerce Developer / Projektleiter', no form, apply by email jobs@pro-discount.one -> park email-only.

## MHW Bike-House (jobs.mhw-bike.de, WP CF7)
- Link was shop homepage: shop footer 'Karriere' -> jobs.mhw-bike.de -> /marketing -> job page has inline form; ONE PDF upload (merge cover letter+CV with pypdf); no captcha; success in .wpcf7-response-output.

## Leogra (leogra.de/karriere, Elementor form)
- Form on /karriere page: accept Borlabs 'Zustimmen und schließen'; fields by form_fields[...]; phone must be +49 digits without spaces (spaces -> 'nur Zahlen' error, submit fails); lebenslauf + zeugnisse[] (= cover letter) file inputs via click + chooser; success message 'Danke für deine Bewerbung!'.

## Umantis (flyeralarm)
- 2nd+ application: account persists in session; /Vacancies/<id>/Application/CheckLogin/1 goes to short FurtherApplication form: one merged PDF (cover letter+CV via pypdf) in 'Bewerbungsschreiben / Lebenslauf', source select, submit. Job titles on flyeralarm.com/karriere/de/alle-jobs may differ slightly from Arbeitsagentur (no 'E-Commerce' suffix).

## D-I-S (d-i-s.de/kontakt-bewerbung)
- Karriere page 'Jetzt bewerben' -> CF7 contact form, no upload, Firma* required (Privatperson), invisible reCAPTCHA v3 passes; success 'Vielen Dank für Ihre Nachricht'. Docs address jobs@d-i-s.de.

## apvento (apvento.de/career)
- Staffing firm; /career lists only a few roles (Framer site); absent Magento Entwickler = closed.

## AEET (aeet-energy.com / aeet24.com)
- Career pages list only office/sales/digital-marketing roles, no E-Commerce Manager and no form; apply address bewerbung@aeet24.com -> park with email.

## talentstorm (severin-elektrogeraete.talentstorm.de)
- Indeed->severin.com/de-de/karriere->blogazine/vacancies/<slug>->'Jetzt bewerben' -> /bewerbung/<slug>-<id>. 2 steps (Daten with ISO DOB; Unterlagen: CV, Anschreiben via chooser), then 'Bewerbung senden' opens dialog -> click 'Senden'. No thank-you page (redirects to /stellenangebote); confirmation = PIN mail (code Severin talentstorm.de).

## rexx (career.check24.de)
- LinkedIn link is authwall: jobs.check24.de/de/jobs/?q=Teamleiter lists jobs -> career.check24.de/...-f<id>.html. Selects are custom (set native select via JS+change); each upload opens a 'KI Hinweis' jQuery dialog (Akzeptieren/Ablehnen) that re-opens and keeps an overlay; 'anschreiben' input lands in the CV preview slot (replaces CV) - upload one merged PDF (cover+CV) into the CV slot only, and handle the dialog before the next click. Unresolved: parked.

## WMF (Groupe SEB)
- wmf.com is only the shop; careers at aboutwmf.com/de/karriere/ -> groupeseb.taleo.net jobsearch; no initiative form, contact karriere@groupeseb.com

## Westernacher
- westernacher.com/join lists jobs on jobs.eu.lever.co/westernacher; only Asia roles + a Japanese general application, no German initiative form

## Weidmüller (weidmueller.de jobboard, finest jobs)
- Initiative form at /de/jobboard/bewerben-sie-sich-initiativ-de-f3213.html, inline; fill by name bewerbung_form[...] via JS; Einsatzort select required; uploads via JS input.click()+file chooser (anschreiben, lebenslauf); click 'Senden' link; title 'Bewerbung abgeschlossen'

## Wacker (jobs.wacker.com)
- SuccessFactors career site; search?q=Commerce returned no jobs; wacker.com careers overview has no initiative form or email

## Würth (wuerth.de)
- Initiativbewerbung link goes to career.wuerth.com (dead); jobs now on career5.successfactors.eu wrthitinteP2 -> career.witglobal.net/search?q=<kw>; Commerce search only Italy/India

## Vorwerk (jobs.vorwerkgroup.com)
- vorwerk.com -> Karriere -> career-vorwerkgroups.com -> jobs.vorwerkgroup.com (SuccessFactors, search?q=<kw>&locale=de_DE); 'Commerce' = 0 hits, 'SAP' only unrelated fuzzy hits; no initiative form

## Villeroy & Boch (Workday)
- villeroyboch.wd3.myworkdayjobs.com/de-DE/careers?q=<kw>; only initiative posting is site-bound (Treuchtlingen); Commerce hits are UK sales/trainee roles

## valantic (valantic.com WP form -> SuccessFactors)
- Initiative form inline at /de/karriere/stellenangebote/initiativbewerbung-217/; no captcha; fill by name (cust_REC_*, firstName...), uploads via JS input.click()+chooser (resume, coverletter), range slider id field-salary, privacy #field-privacy-policy; submit reloads page with no visible thank-you (pending)

## TWT Digital (twt.de)
- careers at /unternehmen/karriere/, jobs apply via greven-twt-gruppe.jobs.personio.de; only 2 non-dev postings, no initiative form; HR address on job page

## TRUMPF (Workday)
- trumpf.com/de_DE/karriere/stellenangebote -> trumpf.wd3.myworkdayjobs.com/de-DE/TRUMPF_Graduates_and_Professionals?q=<kw>; initiative applications exist only as postings titled 'Initiativbewerbung ...' for some areas; none found for IT/Commerce

## Thalia (jobs.thalia.de)
- thalia.de/karriere is 404; jobs at jobs.thalia.de (talents-connect), IT list at /it-digitalisierung; ?q= search param is ignored; no initiative form

## team neusta
- karriere portal (HR Works) has no initiative form; offene-stellen lists only SAP Finance/FI-CO roles; no HR email on site; www homepage returned 500 once

## Tchibo (tchibo-karriere.de)
- FAQ says Initiativbewerbung not possible; job list /jobsuche/suche (243 jobs, only first ~12 render); contact recruiting@tchibo.de

## Sybit (sybit.com)
- sybit.de->sybit.com; /de/karriere/offene-stellen has 'Schnellbewerbung' iframe form (Anrede dropdown, fields as text inputs, source dropdown; Usercentrics Alles Akzeptieren). Single file input: setInputFiles one file at a time (CV, then cover letter); chooser never opens. Submit then wait ~10s: 'Vielen Dank für deine Bewerbung'.

## STIHL (SuccessFactors career5 STIHLPROD)
- corporate.stihl.de initiativbewerbung page -> Jetzt initiativ bewerben (jobId=53380 Waiblingen). Apply -> Create account (privacy dialog link #dataPrivacyId, then Accept button). Profile page: click Upload a Resume / Attach a Cover Letter then setInputFiles on the file input. Job-Specific section: source=Job Posting, Detail=Job Posting: LinkedIn, previously employed=No; address and phone via pressSequentially. Success: Thank you for applying to STIHL.

## SQLI (sqli.com)
- Spontaneous application form at /int-en/spontaneous-application (Drupal): country select Germany, one file only (merge cover letter+CV with pypdf, 2MB limit), #edit-rgpd via JS; visible reCAPTCHA v2 -> always parks.

## Sartorius (Workday)
- Careers at sartorius.com/en/company/careers -> sartorius.wd3.myworkdayjobs.com/sartoriuscareers?q=<kw>; fuzzy search, 'SAP Hybris' gives unrelated hits; no initiative application posting.

## Salzgitter AG
- jobs at salzgitter-ag.com/de/jobs-karriere/stellenangebote.html (SuccessFactors gesisgesel); no initiative form, no SAP Commerce roles (only SAP SD / FI-CO inhouse).

## Rittal / Friedhelm Loh Group
- rittal.com/de-de/Unternehmen/karriere -> career.friedhelm-loh-group.com (talentsconnect), /search?q=<kw>; no initiative form, no SAP Commerce roles.

## Q_PERIOR / Wavestone
- q-perior.com redirects to wavestone.com; jobs on germany-career.wavestone.com (softgarden), no initiative form, only SAP S/4/Finance/Security roles; contact recruiting@wavestone.com.

## Q CELLS (q-cells.de)
- Jobs at q-cells.de/1/ueber-uns/jobs (Leiter IT + PV/solar roles); careers.qcells.com is the US site; no initiative form.

## PIKON (pikon.com)
- Initiative form at /de/job/initiativbewerbung/: modal hidden until button.jp-apply-button is clicked (the 'Jetzt bewerben!' link opens a contact popup instead). Fill by #input-* ids, 'Datei hinzufügen' label + chooser twice (cover letter, CV); Borlabs 'Cookies akzeptieren' first. Success inline: 'Vielen Dank für Deine Bewerbung!'

## Phoenix Contact
- Jobs at jobboerse.phoenixcontact.com (d.vinci, 45 jobs, ?q ignored; 'Weitere' loads more); no initiative form, no SAP Commerce roles (only SAP SD/integration); HR mail recruitingservice@phoenixcontact.com

## ORBIS (jobs.orbis.de, SuccessFactors career5 orbisag)
- CORRECTION: the 'kein Roboter' message on Konto anlegen cleared by itself (invisible captcha); a few seconds later the tab was logged in on the apply form - re-check the tab before parking. Form: CV via 'Lebenslauf' button > Von Gerät hochladen; cover letter via 'Weitere Dokumente' button; expand sections; fill phone/street/zip/city by id prefix, Kündigungsfrist/Eintritt text, salary; DOB is a ui5 date widget (type TT.MM.JJJJ, Tab). Success title 'Erfolgreich angewendet'.
- Initiativbewerbung posting on jobs.orbis.de/job/...-66115/1026893001/ -> Jetzt bewerben needs a career5 account; Konto anlegen has a reCAPTCHA ('kein Roboter') -> always parks. HR mail infohr@orbis.de

## Netformic (netformic.com, Personio)
- netformic.de -> netformic.com/de/karriere lists 2 Personio jobs (no initiative form); applied to Shopify Developer via netformic.jobs.personio.de/job/288131/apply?display=de. Fill #field-*; 'Datei hinzufügen' buttons nth0=cover, nth1=CV; 'VIELEN DANK' confirmation

## Netconomy (Recruitee general application)
- netconomy.net/careers/job-openings 'Send us a general application' -> netconomy.recruitee.com/o/general-application/c/new. Phone: type +49... slowly to switch country; choices via label >> text=; privacy box: JS click on input.nextElementSibling.firstElementChild (real click opens privacy tab); date input ISO; files via chooser. Submit shows hCaptcha -> parks.

## Merkle / Namics (merkle.com)
- Jobs search at merkle.com/en/careers/jobs.html (keyword+location boxes, invisible reCAPTCHA); 'SAP Commerce' returns no results; only German role was Principal Consultant DXP (München); no initiative form or HR email

## mindsquare (Greenhouse job-boards.eu)
- mindsquare.de/karriere has Initiativbewerbung link grnh.se/57bb5772teu -> job-boards.eu.greenhouse.io/mindsquareag/jobs/4592446101. Only one CV slot (merge cover+CV with pypdf); react-selects via click combobox then role=option; country Deutschland +49; German level options A1-A2/B1-B2/C1/C2 (B1-B2). Success /confirmation 'Vielen Dank für deine Bewerbung'.

## Mindcurv / Accenture
- mindcurv.com redirects to accenture.com; jobs search accenture.com/de-de/careers/jobsearch?jk=hybris. Workday apply: accept cookies > Apply Manually > Sign in with email works with the default password (JS-click [data-automation-id=click_filter]); job R00278881 SAP CX/CRM Consultant already applied.

## Miele (karriere.miele.de, talentsconnect)
- miele.de footer -> karriere.miele.de/deutschland; /search ignores ?q= and lists 10 jobs at a time; no initiative form seen; contact recruiting-operations@miele.de

## Melitta (Workday wd3.myworkdaysite.com melittagroup)
- melitta.de is Cloudflare-blocked; use melitta-group.com/de/karriere/melittajobportal. Workday search ?q=initiativ finds Initiativbewerbung R100164; /apply > Apply Manually is GUEST (no account, 5 steps). Pick country Germany FIRST (it wipes address fields), then fill; phone code auto +49; source LinkedIn (type+Enter); upload CV+cover in one chooser; questions: locations/fields checkboxes, termination text, talent-pool consent Yes, disability No; terms checkbox; Submit -> 'Congratulations'.

## Liebherr
- liebherr.com/de-de/karriere has no Initiativbewerbung link in snapshot; guessed initiative URLs 404; park.

## Lemundo (Personio)
- lemundo.de/uber-uns/jobs -> 'Jetzt initiativ bewerben' = lemundo.jobs.personio.de/job/714658/apply?display=de; fields Verfügbar ab (text TT.MM.JJJJ), Stunden, Gehalt; CV + Anschreiben via Datei hinzufügen chooser; no captcha; 'VIELEN DANK'.

## Lapp (lappcareer.com, rexx/finest jobs)
- lapp.com->Google 'Lapp Karriere Initiativbewerbung' -> lappcareer.com/Initiativbewerbung-de-f60.html; accept cookies, native selects hidden: set via JS value+change; pressSequentially text; setInputFiles cv_lebenslauf + anschreiben (UI shows only one filename at a time); #agb_checkbox click; JS click 'Senden'. Title 'Bewerbung abgeschlossen'.

## Krones (jobs.krones.group, d.vinci)
- krones.com/de/karriere/faq.php 'initiativ' link -> jobs.krones.group/de/jobs/16/form; set fields by id via JS (dateOfBirth TT.MM.JJJJ, multiselects by option value), radios 56-0/193-0 Nein, consents *Accepted1, one attachmentFile takes CV+cover; no captcha; success /applied.

## KPS (career.kps.com, Teamtailor)
- kps.com/de/karriere -> career.kps.com/jobs lists ~16 SAP/freelance roles, no initiative form, no Commerce roles; contact info@kps.com.
