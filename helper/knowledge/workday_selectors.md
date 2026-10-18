# Workday apply flow: selectors and techniques

These are facts collected from several repos (see SOURCES.md). Where an id is marked (M), it came from an MIT repo (Amro212, andrewmillercode, arya2919, PINGx969). The other ids were seen in unlicensed repos and are recorded here as facts only. Tenants vary, so always try several candidates.

## Two id generations
- Older tenants: `[data-automation-id="legalNameSection_firstName"]`, `addressSection_city`, `phone-number`, `email`.
- Newer tenants (2024+): DOM `id="name--legalName--firstName"`, `address--city`, `phoneNumber--phoneNumber`, `source--source`, `country--country`. Repeating rows look like `id="workExperience-3--jobTitle"` and `education-4--fieldOfStudy`.
- Resolver order that works (PS12007): `[data-automation-id="formField-<k>"]` (wrapper) -> `[data-automation-id="<k>"]` -> `[id="<k>"]` -> `[id$="--<k>"]` -> `[name="<k>"]` -> label regex. The first visible match wins.
- Field wrapper: `[data-automation-id^="formField-"]`, for example `formField-source`, `formField-country`, `formField-countryPhoneCode`, `formField-previousWorker`, `formField-skills`, `formField-gender`, `formField-ethnicities`, `formField-disability(ies)`, `formField-veteran`, `formField-pronouns`, `formField-todaysDate`.
- State is `addressSection_countryRegion` / `address--countryRegion`. The automation id says "countryRegion" even though the label says "State" (tso_autofiller).

## Step detection
- `[data-automation-id="progressBar"] [data-automation-id="progressBarActiveStep"]`, also `[aria-current="step"]`, `currentPage` and `stepTitle`. In the active step, the 3rd child holds the step name text (andrewmillercode (M)).
- Page containers: `applyFlowPage`, `contactInformationPage`, `personalInformationPage`, `applicationQuestionsPage`, `applyFlowReviewPage`.
- Step name regexes: `my information|personal information|contact information`, `my experience`, `application questions|additional questions|questionnaire`, `voluntary disclosure`, `self[\s-]?identif`, `\breview\b`, `autofill with resume`.

## Sign in / create account / start
- Start buttons: `applyButton`, then `applyManually` / `autofillWithResume` / `useMyLastApplication` (adventure page).
- Sign in: `signInLink`, `utilityButtonSignIn`, `email`, `password`, `signInSubmitButton`.
- Create account: `createAccountLink`, `email`, `password`, `verifyPassword`, `createAccountCheckbox` (terms), `createAccountSubmitButton`.
- `signInSubmitButton` / `createAccountSubmitButton` often sit behind an overlay div `[data-automation-id="click_filter"]`. Click the click_filter div, not the button (kaleidoscope). In Playwright, use `page.locator('[data-automation-id="createAccountSubmitButton"]').locator('xpath=..').locator('[data-automation-id="click_filter"]')`, or `click(force=True)` on the button's bounding box.

## My Information
| field | ids to try |
|---|---|
| How did you hear | `source`, `sourcePrompt`, `source--source`, wrapper `formField-source` / `sourceSection` |
| Previous worker (radio) | `candidateIsPreviousWorker`, `previousWorker`, wrapper `formField-previousWorker`; label `/previously (worked|been employed)|former (employee|worker)|worked (here|for us) before/i` |
| Country | `countryDropdown`, `country--country`, `addressSection_country` |
| First/last name | `legalNameSection_firstName`/`_lastName`, `name--legalName--firstName`/`lastName` |
| Preferred name checkbox | `preferredNameCheckbox`, `name--preferredCheck` |
| Address | `addressSection_addressLine1`, `address--addressLine1`, `addressSection_city`, `address--city`, `addressSection_postalCode`, `address--postalCode` |
| State/region | `addressSection_countryRegion`, `address--countryRegion` |
| Email | `email`, `emailAddress--emailAddress` |
| Phone device type | `phone-device-type`, `phoneNumber--phoneType` (button listbox; pick "Mobile" with synonyms Mobile/Cell/Cellular, DE "Mobil") |
| Country phone code | `country-phone-code`, `phoneNumber--countryPhoneCode` (searchable prompt: type "Germany" or "+49", then Enter, then pick the option) |
| Phone number | `phone-number`, `phoneNumber--phoneNumber`. Enter it WITHOUT the country code when the code prompt exists. |
| Extension | `phone-extension`, `phoneNumber--extension` |

"How did you hear" is a hierarchical prompt. Option groups (`promptTitle` / `promptOptionGroup`, for example "Job Board", "Social Media") must be clicked to drill down, and the leaf is `promptLeafNode`. Amro212 (M) clicks only the group that matches `^(job boards?|social media|social networks?)$` when the target is LinkedIn.

## My Experience
- Resume upload: `input[type=file]` inside `resumeUpload`, `quickApplyUpload` or `file-upload-input-ref`, or `resumeAttachments--attachments`. Success shows `file-upload-successful` or `file-upload-item` with `file-upload-item-name` / `file-upload-file-name`. The upload is still processing while `[aria-busy=true]` or `[role=progressbar]` is visible, and it was rejected if `inputError` or `[aria-invalid=true]` appears. Wait for acceptance before you click Next (Amro212 (M)). In Playwright, use `set_input_files` on the hidden input. Never click the "Select files" button, because that opens the OS dialog.
- Sections: `workExperienceSection`, `educationSection`, `languageSection`, `websiteSection` / `websitePanelSet-*`, `skillsSection`. The add button is `add-button` / `Add` / text `^add( another)?$`. Rows are `workExperience-N`, `education-N`, `language-N`.
- Row fields: `jobTitle`, `company`/`companyName`, `location`, `currentlyWorkHere` (checkbox), `startDate`, `endDate`, `description`/`roleDescription`. Education fields: `school`/`schoolName`, `degree` (button listbox), `fieldOfStudy` (prompt), `gpa`/`gradeAverage`, `firstYearAttended`, `lastYearAttended`.
- Skills: `formField-skills` -> `multiselectInputContainer` input (`monikerSearchBox`). For each skill, type it, press Enter, wait about 1 s, then click the matching row in `.ReactVirtualized__Grid__innerScrollContainer` (match on aria-label). Some tenants accept the first result only via a second Enter.
- LinkedIn: `linkedinQuestion`, `linkedInAccount`, `socialNetworkAccounts--linkedInAccount`.

## Date fields
- `dateSectionMonth-input`, `dateSectionDay-input`, `dateSectionYear-input` inside `dateInputWrapper` / `dateSectionGroup`. The ids are prefixed per field, for example `startDate-dateSectionMonth-input`. Many tenants show only MM/YYYY.
- These are spinbutton-style inputs that build their value from keystrokes. Click the month section and type the digits (`keyboard.type("032021")` across sections works, because the cursor auto-advances). Do NOT set `.value` directly or send synthetic keys mixed with setNativeValue (tso_autofiller notes that one extra key is read as a digit).
- Self-identify "Today's date" (`formField-todaysDate` / `selfIdentifiedDisabilityData--dateSignedOn`) is often filled by the calendar icon `dateIcon`, or by typing MMDDYYYY.

## Dropdown technique (the core trick)
1. Button listbox (Gender, Degree, Phone device type, Country on some tenants): `button[aria-haspopup="listbox"]` inside the wrapper. Click it, then the popup renders at the END of `<body>` as `ul[role="listbox"]` (`[tabindex="-1"]`) with `[role="option"]` / `li div`. Click the option that matches the text. Exclude `selectedItemList` / `selectedItem`, which are also role=listbox. Afterwards, verify the button text no longer matches the placeholder `^(select one|--)`.
2. Searchable prompt (Source, Country phone code, Field of study, Skills, sometimes Country/State): `input[data-uxi-widget-type="selectinput"]`, `searchBox`, `multiselectInputContainer input`, `input[role=combobox]`. Type, press Enter, then choose from `[data-automation-id="promptOption"]` / `promptLeafNode` within `activeListContainer`. "No items" shows as `/no items|no results/`. Chosen pills are `selectedItem` (title attr) with delete `DELETE_charm`. Long lists are virtualised (`.ReactVirtualized__Grid`), so scroll the grid to load more.
3. NEVER press Escape to close a Workday prompt, because it ROLLS BACK the selection (Amro212 (M) findings). Close it by clicking the toggle `promptIcon`, or click on neutral page whitespace instead.
4. After filling, Workday validates on change AND blur. Use real `fill()`/`type()` followed by Tab or blur, then check `[data-automation-id="inputError"]`, `errorMessage`, `inputAlert` and `errorBanner`.

## Questions / Voluntary disclosures / Self-identify
- Application questions: ids like `primaryQuestionnaire--<uuid>`. Treat them generically by wrapper plus label. Radios are `[role=radio]` or `input[type=radio]` inside the formField, and checked state is `aria-checked="true"`.
- Disclosures: `personalInfoUS--gender` / `personalInfoPerson--gender`, `hispanicOrLatino`, `ethnicityDropdown` / `personalInfoPerson--ethnicities` (can be a checkbox group or a multiselect), `veteranStatus`, `disability`, `personalInfoPerson--pronouns`. Terms checkbox: `agreementCheckbox`. Decline-option regex: `/not\s+(wish|want)\s+to|decline|prefer\s+not|choose\s+not|rather\s+not|don'?t\s+wish/i`.
- Self-identify (US CC-305): `selfIdentifiedDisabilityData--name`, `--dateSignedOn`, `--disabilityStatus` (checkbox group).
- In checkbox groups inside prompts, click the row, not `checkbox.click()`, then re-read `checked`.

## Navigation / review / submit
- Next: `bottom-navigation-next-button` (new), `pageFooterNextButton` (old), `wd-CommandButton_next`, `saveAndContinueButton`/`save-and-continue-button`. The footer zone is `pageFooter` / `bottom-navigation`.
- After Save, Continue can stay disabled for up to about 15 s, so wait for it to be enabled (Amro212 quirk `continueReadyTimeoutMs: 15000`).
- On the review page (`applyFlowReviewPage`), the Submit button has the same id as Next (`bottom-navigation-next-button`) with text "Submit". Gate on the text.
- Confirmation: the dialog or page shows "Application Submitted" / "Thank you for applying" / "Congratulations". Candidate home lists "Submitted". DE: "Bewerbung eingereicht".

## Pitfalls
- `click_filter` overlay divs intercept clicks on buttons.
- Popups are portal-rendered at the end of body, so do not scope the option search to the field.
- Multi-language tenants: labels and step names are localised (DE "Meine Informationen", "Meine Erfahrung", "Bewerbungsfragen", "Freiwillige Angaben", "Selbstidentifizierung", "Überprüfen", "Weiter", "Absenden"/"Senden", "Wie haben Sie von uns erfahren", "Haben Sie bereits für ... gearbeitet"). Prefer automation ids over text.
- Ids are not stable across tenants. Every repo keeps a list of candidates.
- Bot detection is mild, but account creation per tenant (email verification on some) is the main blocker.
- Pre-check closed postings via the CXS JSON: `GET https://<host>/wday/cxs/<tenant>/<site>/job/<postingSlug>` (see scrapers.md).
