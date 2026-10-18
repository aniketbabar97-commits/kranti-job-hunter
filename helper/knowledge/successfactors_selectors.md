# SAP SuccessFactors (career site / RMK) and Taleo

Only one repo (rpeng220/kaleidoscope, 2022, no license) has SF-specific code, so treat these as facts only and verify them live.

## SuccessFactors
- Login: `#username`, `#password`, button with text "Sign In" (XPath `//button[contains(text(),"Sign In")]`).
- Register (RMK "Create an account"): `#fbclc_userName`, `#fbclc_emailConf`, `#fbclc_pwd`, `#fbclc_pwdConf`, `#fbclc_fName`, `#fbclc_lName`, `#fbclc_country` (native select; set it and dispatch change). Data privacy statement accept is normally shown first.
- Application form uses `name=` attributes: `cellPhone`, `address`, `zip`, `state` (select). First name, last name, email and country are pre-filled from the profile.
- Work history and education are label-anchored: `//*[contains(text(),"Company Name")]/following::input[1]`, "Title", "Responsibilities"/"Achievements". Dates are `input[role=combobox]` in MM/DD/YYYY.
- Technique: SF form ids are generated (`..._fieldNNN`), so anchor on labels. DE labels: "Vorname", "Nachname", "E-Mail", "Mobiltelefon", "Straße", "Postleitzahl", "Ort", "Land", "Lebenslauf", "Anschreiben", "Gehaltsvorstellung", "Kündigungsfrist", "frühestmöglicher Eintrittstermin".
- Search: jobs.sap.com-style `/search/?q=&locationsearch=` returns server-rendered rows (`tr.data-row`, `a.jobTitle-link`). No repo had a JSON API.

## Taleo (Oracle TBE)
- Login dialog: `dialogTemplate-dialogForm-login-name1`, `-login-password`, `-login-defaultCmd`. The error marker is `-login-errorMessageTitle`, and register goes through `-login-register`.
- Register: `dialogTemplate-dialogForm-userName`, `-password`, `-passwordConfirm`, `-email`, `-defaultCmd`. Security Q/A: `...-question`/`-answer`.
- Personal info ids follow the pattern `et-ef-content-ftf-gp-j_id_id16pc9-page_<N>-cpi-cfrmsub-frm-dv_cs_candidate_personal_info_<Field>`, where Field is one of FirstName, LastName, Address, City, ZipCode, MobilePhone, HomePhone, PreferredPhone, ResidenceLocation-0 (country), ResidenceLocation-1 (state). Page N varies, so use the suffix match `[id$="dv_cs_candidate_personal_info_FirstName"]`.
- Experience: `[id$="-we-wei-0-frm-dv_cs_experience_Employer"]`. Education: `[id$="-csef-efi-0-frm-dv_cs_education_Program"]`.

## Oracle Recruiting Cloud (successor to Taleo), iCIMS, SmartRecruiters, Workable, JazzHR: see greenhouse_lever_selectors.md
