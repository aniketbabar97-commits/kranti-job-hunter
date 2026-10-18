# Greenhouse, Lever, Ashby, SmartRecruiters, Workable, iCIMS, JazzHR, Personio, Recruitee

These come mainly from Amro212/job-copilot-extension (MIT, very active, live-tested) and jayant99acharya/PINGx969 (MIT). The small selector tables below are copied with attribution under MIT.

## Greenhouse
- Detect: host `greenhouse.io` (boards, job-boards), or `#grnhse_app`, `form#application_form`, `form#application-form`, `form.job__form`, `input[name=action][value="gh_application_submission"]`, `form[action*="greenhouse.io"]`.
- Embedded boards use an iframe (`#grnhse_iframe`, src `boards.greenhouse.io/embed/job_app?for=<board>&token=<id>`). Navigate straight to `https://job-boards.greenhouse.io/<board>/jobs/<id>` instead of working inside the iframe.
- Classic ids: `#first_name`, `#last_name`, `#email`, `#phone`, `#resume` / `input[type=file]` in `#resume_fieldset`, `#job_application_location` (Google Places `.pac-container`; type, wait for `.pac-item`, then click the first one).
- New React boards use `.select-shell` / `.select__container` (react-select). Click the control, type, then pick `.select__option`. Some are async typeaheads (Location (City)). Multi-selects render chips.
- Phone: inside `.phone-input` there is a country select plus a national number.
- Repeating sections: `#employment_section .employment`, `[data-name="employments"] > ul > li`. Add with `#add_employment`, `#add_education`, `.add-another-button`.
- Legacy select2: `.select2-container`. Click it, type into `.select2-input`, then pick `.select2-result`.
- Question containers: `.field`, `.form-group`, `fieldset`, `.demographic_question`. Required checkbox groups use `fieldset.checkbox[aria-required=true]`.
- Submit: `input[type=submit][data-trackingid="job-application-submit"]`, `button[type=submit].submit-step`, or `#submit_app`.
- Confirmation: `.confirmation__content`, or URL `/confirmation`, or text "Thank you for applying". Email verification code fields appear on some boards (security code, 8 chars).
- Public API: `https://boards-api.greenhouse.io/v1/boards/<token>/jobs[/<id>?content=true]`. The questions list is at `?questions=true`.

## Lever
- Detect: host `jobs.lever.co` / `jobs.eu.lever.co`, or `input.location-input[name=location]` + hidden `selectedLocation`.
- Form fields by name: `name`, `email`, `phone`, `org` (current company), `urls[LinkedIn]`, `urls[GitHub]`, `urls[Portfolio]`, `resume` (file, `#resume-upload-input`), `comments`, custom questions `cards[<uuid>][field0]`, EEO `eeo[gender]`, `eeo[race]`, `eeo[veteran]`.
- The location typeahead `.dropdown-location` writes JSON into the hidden `selectedLocation`. Type, then click `.dropdown-location .dropdown-results div`.
- Section headers are uppercase (LOCATION, PERSONAL INFORMATION). Labels sit in `.application-label`, and the question wrapper is `.application-question`.
- Submit: `#btn-submit` / `button[data-qa="btn-submit"]`. hCaptcha appears frequently on submit.
- Confirmation: URL ends `/thanks`, text "Application submitted!" / "Thanks for applying".
- API: `https://api.lever.co/v0/postings/<company>?mode=json` (EU: `api.eu.lever.co`).

## Ashby
- Detect: host `jobs.ashbyhq.com`, or `#ashby_embed`, `[data-ashby-root]`, `.ashby-application-form`, `.ashby-application-form-field-entry`.
- Apply: `a[href$="/application"]` (the "Application" tab). Submit: `.ashby-application-form-submit-button`. Success: `[class*="application-form-success-container"]`.
- Yes/No questions render as `.ashby-application-form-input-yesno` buttons (not inputs). Click the button whose text is Yes or No.
- Selects are custom (`.ashby-select-input`) and do not always expose ARIA. Floating UI hides sibling questions while a menu is open, so close it with Escape (OK on Ashby, unlike Workday).
- The resume "autofill from resume" widget is separate from the required Resume field. Upload to the field labelled Resume.
- System fields: `_systemfield_name`, `_systemfield_email`, `_systemfield_resume`, `_systemfield_location`.
- Public API: `https://api.ashbyhq.com/posting-api/job-board/<org>?includeCompensation=true`.

## SmartRecruiters (oneclick)
- Detect: host `jobs.smartrecruiters.com` / `smartr.me`, elements `oc-oneclick-form`, `spl-input` (web components; the inputs live in shadow DOM, and Playwright's CSS pierces open shadow roots).
- Ids: `first-name-input`, `last-name-input`, `email-input`, `confirm-email-input`, `linkedin-input`, `website-input`, `hiring-manager-message-input`, `location-autocomplete-search-input`. Title pattern: `Easy apply - <title> - <company>`.

## Workable
- Detect: host `apply.workable.com`, `[data-ui="application-form"]`. Fields have `data-ui` = `firstname`, `lastname`, `email`, `phone`, `address`, `city`, `postcode`, `country`, `resume`, `cover_letter`. Submit `[data-ui="apply-button"]`. Cloudflare Turnstile is common.

## iCIMS
- The form is often inside `#icims_content_iframe`. Use `page.frame_locator('#icims_content_iframe')`. Field names: `PersonProfileFields.FirstName`, `.MiddleName`, `.LastName`, `.Email`, `.PhoneNumber`, `.AddressStreet1`, `.AddressStreet2`, `.AddressCity`, `.AddressState`, `.AddressZip`, `.AddressCountry`, `.LinkedIn`. Job title: `.iCIMS_Header h1`, `.iCIMS_JobHeaderTitle`.

## JazzHR
- Names `resumator-<field>-value`, where field is one of firstname, lastname, email, phone, address, city, state, postal, resume, coverletter, linkedin, website, salary, eeo_gender, eeo_race, eeo_veteran, eeo_disability.

## Personio / Recruitee / softgarden / BambooHR / Jobvite / Breezy
- Personio: host `jobs.personio.de|com` (`<company>.jobs.personio.de/job/<id>`), `form[action*="personio"]`. The title pattern is `<title> | Jobs at <company>`. No repo had field maps. Personio fields are standard named inputs (`first_name`, `last_name`, `email`, `documents`), so label matching works. Unverified.
- Recruitee: `*.recruitee.com`, `[class*=recruitee]`. BambooHR: `[class*="fab-Form"]`. Jobvite: `jobs.jobvite.com`, `.jv-logo`. Breezy: `*.breezy.hr`.
- softgarden: none of the repos had code for it.
