# Kranti job hunter — product spec (agreed 2026-10-18)

Every item is checked off only when tested. Status lives in the final report.

## Documents
- [ ] Posting language rules everything: German posting → German CV, letter, email, form answers; English → English.
- [ ] Selling documents: no weaknesses or gaps, ATS keywords mirrored, techno-functional / BA / AI framing.
- [ ] Per-job PDF names (`Kranti_Chavan_Lebenslauf_<Company>_<Role>.pdf` / `_CV_` / `_Anschreiben_` / `_Cover_Letter_`).
- [ ] Carlito font (no blurry Type 3), job titles never split across pages.
- [ ] Salary: upper part of a posted range, else 60.000 € brutto/Jahr verhandelbar.

## Facts (profile/facts.yaml) — never invent anything else
- [ ] Frau, female; Karlsruhe; valid work permit, no sponsorship; notice: last day 15.12.2026, start 16.12.2026.
- [ ] English C2, German **B1 (never higher)**, Hindi + Marathi native; B.E. Pune 2020; 5+ years SAP Commerce/Java/Spring.
- [ ] Driving licence **no**; travel yes up to 50 %; disability **no**; hybrid/remote/relocation yes.
- [ ] Unknown question → answer from facts only; not covered → park and log the question once.

## Finding jobs (no job in the field missed, especially Baden-Württemberg)
- [ ] LinkedIn, Indeed, Arbeitsagentur, LinkedIn recruiter posts (existing).
- [ ] StepStone, XING, Glassdoor, Google Jobs.
- [ ] Workday and SuccessFactors career sites searched directly.
- [ ] ~150 BW + German employers on their own career systems, read every run.
- [ ] Weekly miss-check: Google results vs. what we have.
- [ ] Same job on several portals = one job (company + title).

## Applying (target: end-to-end automatic)
- [ ] Every job gets its real form URL and system (resolver); apply through the easiest door: own form → Personio/JOIN/softgarden/… → Workday/SuccessFactors → Arbeitsagentur → Indeed/LinkedIn last.
- [ ] Site modules: Personio, JOIN, softgarden, SmartRecruiters, Recruitee, own forms, Workday, SuccessFactors; each tested on a live posting up to Submit.
- [ ] Fill every field, upload CV + cover letter, motivation box → "Why us".
- [ ] Tick **every** checkbox (privacy, terms, talent pool, keep data, newsletter); accept all cookies.
- [ ] Accounts: create automatically with her Gmail and the default password from me.env; stored encrypted on her PC only (never in the repo); login next time; reset via Gmail if needed.
- [ ] Verification codes / links read from her Gmail automatically.
- [ ] Submit automatically. One-click rule: first job per system stops at Submit for her; after one confirmed success → auto.
- [ ] **CAPTCHA is the only thing that stops a job**: parked, helper moves on immediately, never waits. No CAPTCHA solving, no stealth/anti-detection tricks.
- [ ] Parked list at the end (helper/parked.txt) for later.

## Proof and follow-up
- [ ] "Applied" only with proof: thank-you page (screenshot saved) or confirmation email within 24 h. 3 unconfirmed in a row → system back to assisted.
- [ ] APPLIED.md line written only after proof.
- [ ] HR email (job / HR / small-company generic address) goes out **only after** the website application is proven.
- [ ] Inbox tracking: interviews, rejections, receipts in the digest.
- [ ] Funnel in daily digest + weekly: found → relevant → kit → applied (auto/assisted/manual) → confirmed → replies → interviews.

## Safety
- [ ] No PII or passwords in the public repo; me.env and vault stay on her PC.
- [ ] Never apply twice to the same job; max 2 roles per company per day rule for emails.

## Delivery
- [ ] Full dry run on all direct-link jobs (placeholder data, nothing submitted from the cloud).
- [ ] Merged to main; `start.bat` with `AUTO_SUBMIT=1` runs the 50 applications on her PC.
