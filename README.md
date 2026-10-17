# Kranti Job Hunter

Twice a day (emails around 11:00 and 17:00 India time) this repo searches for every new
SAP Commerce Cloud / Hybris / e-commerce opening in Germany and remote in the EU,
scores each one against `cv.md`, and emails a ranked digest.

## What it searches

| Source | How |
|---|---|
| Bundesagentur für Arbeit (Arbeitsagentur) | Job-search API (unofficial, used by the official app) |
| LinkedIn | JobSpy library, Germany + remote-EU pass |
| Indeed.de | JobSpy library |
| Company career sites (direct) | Public job feeds (Personio, Greenhouse, Lever, SmartRecruiters) of the employers in `config.yaml` → `companies` |
| Company career sites (Google) | Google search inside job pages hosted on Personio, Workday, SuccessFactors, SmartRecruiters, JOIN, … (`career_site_queries`, first run of each day, needs `SERPER_API_KEY`) |
| LinkedIn recruiter posts ("#hiring SAP Commerce…") | Google search via Serper.dev (optional, `SERPER_API_KEY`) |

Every keyword in `config.yaml` → `queries` runs on every source. Tiers:
SAP Commerce/Hybris → other commerce platforms (Salesforce Commerce Cloud,
commercetools, Spryker, Shopware…) → e-commerce analyst/consultant/PO roles →
adjacent (Java for e-commerce, SAP CPQ, PIM).

A job is kept if its title/description mentions one of `relevance_terms`, and
dropped if its title has one of `exclude_title_terms` (internships, warehouse,
sales). The same job on several boards is shown once, and a job is never sent twice.

## The digest

- Header: counts of 🎯 strong (80+), 👍 good (60–79) and lower matches, plus links to the full record.
- Only strong and good jobs are shown, as cards, split into 🇬🇧 English-speaking and 🇩🇪 German-speaking.
  Each card: score, title, company, location, remote, salary, age (🆕 ≤1 day …), language, source, the reason, and an **Open job** button.
- Lower matches are not in the email; they are in the full record.
- Sources line at the bottom; ⚠️ if a source returned nothing or failed.

## Ranking

The AI scores each job against `cv.md` on a fixed scale (SAP Commerce/Hybris 90+, other commerce platforms 70s,
technical e-commerce consulting 60s, non-technical e-commerce 20–39). Then hard rules in `hunter/rules.py` cap:
on-site jobs outside Germany (max 35), jobs outside Europe (max 25), LinkedIn posts that don't name a concrete role (max 45)
or don't mention Germany/remote (max 65).

## Applied tracking

Edit [`APPLIED.md`](APPLIED.md) on GitHub (pencil icon, works on the phone): one line per application — a job link
or a company name, optionally starting with the date (`2026-10-14 https://...`). Emails and JOBS.md then mark
**✅ Applied** or **↺ Applied at this company before**, and the weekly summary leaves applied jobs out.

## Weekly summary

Every Monday (first run of the day) a second email: counts for the week, the 10 best jobs you haven't applied to,
and companies that posted 2+ openings in the last 30 days. Send it any time with **Run workflow → Also send the weekly summary now**.

## Hard-to-fill roles

Jobs posted 30+ days ago show a red **⏳ open N days** badge. The weekly summary adds a fresh list of SAP Commerce
roles that are *still open* after 30+ days (job agency + company feeds): companies struggling to hire — apply and
message the recruiter directly.

## Application kits (CV + cover letter per strong job)

For every job scoring 80+ (and every hard-to-fill role in the Monday summary) the run creates:

- **Tailored CV (PDF)** in Kranti's own design, built from [`profile/master.yaml`](profile/master.yaml) (her CV word
  for word). The AI may only *select and reorder* her real bullets and skills — the code rejects anything not in the
  master CV. Headline and summary mirror the job's keywords she truly has.
- **Cover letter PDF in English**, plus **German** for German postings (her letter structure: hook, 4 matching
  points, honest gap paragraph, notice period until 15.12.2026).
- **Kit note** in [`applications/`](applications/): ATS keyword match (covered / missing), copy-paste answers for
  application forms, "why us" and motivation texts, LinkedIn message, email draft.

**ATS-friendly:** one column, real selectable text, standard headings, no text in images, normalised hyphens
(checked by extracting the PDF text). **Accuracy checks:** her own verbs, notice period, German B1, surname-only
salutations, and any technology claimed but missing from her CV is flagged "check before sending".

**Privacy:** this repository is public, so the PDFs (phone, email, photo) are **attached to the email only** and
never committed. Secrets: `CANDIDATE_PHONE`, `CANDIDATE_EMAIL`, `CANDIDATE_PHOTO_B64` (base64 of the photo).
Nothing is ever sent or submitted automatically.

## Full record

[`JOBS.md`](JOBS.md) lists every job ever sent, grouped like the email, newest first. Raw data: `data/jobs_log.csv`.

## Setup (GitHub → Settings → Secrets and variables → Actions)

| Secret | Needed | Notes |
|---|---|---|
| `TO_EMAIL`, `TO_EMAIL_2` | yes | One address each (or comma-separated) |
| `GMAIL_USER` + `GMAIL_APP_PASSWORD` | one email method | Gmail App Password (Google account → Security → App passwords). Used first |
| `RESEND_API_KEY` + `FROM_EMAIL` | optional backup | Without a verified domain, Resend only delivers to the Resend account's own address |
| `GEMINI_API_KEY` | recommended | AI scoring (free tier is enough) |
| `SERPER_API_KEY` | optional | Free key from serper.dev (2,500 searches, no card). Enables LinkedIn recruiter posts |
| `GROQ_API_KEY` | optional | Backup AI scorer. Without any AI key, keyword scoring is used |

Test it: **Actions → Job hunt → Run workflow** (tick *Dry run* to only preview;
the digest is attached to the run as an artifact). Tick *Only send a test email*
to check email delivery in under a minute.

## Files

- `config.yaml` – keywords, filters, locations
- `cv.md` – candidate profile used for scoring (update when the CV changes)
- `hunter/` – code (`sources.py`, `score.py`, `digest.py`, `main.py`)
- `data/seen.json` – jobs already sent (kept 90 days)
- `data/jobs_log.csv` – every job ever sent, opens in Excel

## Limits

LinkedIn and Indeed sometimes block automated searches; the health section shows
when that happens. StepStone and XING aren't scraped (they block bots). For full
coverage also keep email alerts on StepStone, XING and LinkedIn for "SAP Commerce" / "Hybris".
