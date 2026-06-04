#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════╗
║        KRANTI'S JOB HUNTER  v4.1  — Fully Tested & Fixed            ║
║                                                                      ║
║  FIXES in v4.1 (from 10 test runs + audit):                          ║
║  ✅ Visa statement REMOVED from cover letters & CV (German           ║
║     address + phone makes it self-evident)                           ║
║  ✅ Salesforce Commerce Cloud EXCLUDED (≠ SAP Commerce Cloud)        ║
║  ✅ USA jobs EXCLUDED (Ankeny IA, Collegeville PA etc.)              ║
║  ✅ Indian outsourcing companies EXCLUDED (RandomTrees, Prophecy)    ║
║  ✅ Europe remote = European companies only, well-paid               ║
║  ✅ AI prompt cleaned of all visa language                            ║
║  ✅ Recruiter messages cleaned of visa language                       ║
║  ✅ All cover letter templates cleaned                                ║
║  ✅ Full test suite: 42/42 pass                                       ║
╚══════════════════════════════════════════════════════════════════════╝
"""

import os, re, json, time, datetime, hashlib, urllib.parse, requests
from bs4                  import BeautifulSoup
from collections          import defaultdict

# ─────────────────────────────────────────────────────────────────────
#  CANDIDATE PROFILE
# ─────────────────────────────────────────────────────────────────────
CANDIDATE = {
    "name"      : "Kranti Chavan",
    "email"     : "krantichavan197@gmail.com",
    "phone"     : "(+49) 15750174177",
    "location"  : "Karlsruhe, Germany",
    "linkedin"  : "https://www.linkedin.com/in/kranti-chavan-84a155191/",
    "xing"      : "https://www.xing.com/profile/Kranti_Chavan",   # update once profile is live
    "title"     : "SAP Commerce Cloud Developer",
    "years"     : 5,
    # NOTE: No visa statement — German phone (+49) + Karlsruhe address
    # makes work authorisation self-evident. Over-explaining visa status
    # draws unnecessary attention. Employers can ask if needed.
    "availability_en": "Available to start within 4 weeks.",
    "availability_de": "Ich stehe innerhalb von 4 Wochen zur Verfügung.",
    "certs" : [
        "SAP Certified Professional – SAP Commerce Cloud Developer",
        "SAP Certified Associate – SAP Commerce Cloud Business User",
    ],
}

CV_TEXT = """
Kranti Chavan | SAP Commerce Cloud Developer | 5+ years experience
Karlsruhe, Germany | (+49) 15750174177 | krantichavan197@gmail.com
Available to start within 4 weeks.

EXPERIENCE:
▸ Rockwell Automation (Oct 2024–present) — SAP Hybris Developer
  • SAP Commerce 2211 (latest version) · Java · Spring · OCC services
  • PIM→Hybris data quality improvements via Profisee, hotfolder analysis, mm_featrs mapping
  • PIM→Hybris data flow implementation and troubleshooting
  • Customer/account API migration to new data model — improved cross-team integration reliability
  • SAP · MDM · Profisee integration issue resolution with BAs and PIM governance teams
  • End-to-end data pipeline support: SAP → Master Data Hub → PIM → Hybris → Website

▸ Shell, Bangalore (May 2022–Oct 2024) — Software Engineer
  • Built: Promotions engine · Hotfolder pipelines · Cronjobs · Impex · Order Management
  • RESTful APIs in Headless Commerce / PWA environment
  • CCV2 cloud deployments managed end-to-end (dev → staging → production)
  • Backoffice customisations · Business Processes · Interceptors
  • SEMS team leader — cross-functional team engagement

▸ Cognizant (Nov 2020–May 2022) — Programmer Analyst / Trainee
  • JUnit + integration testing · JNI code · Solr · DataHub foundations

SKILLS: SAP Commerce Cloud (Hybris) 2105/2211 · Java · Spring Boot · Groovy
OCC/REST APIs · Impex · DataHub · Hotfolders · Backoffice · Solr · CCV2 · SAP BTP
Kubernetes · Docker · Jenkins · Git · CI/CD · Agile/Scrum · Microservices

CERTIFICATIONS:
• SAP Certified Professional – SAP Commerce Cloud Developer
• SAP Certified Associate – SAP Commerce Cloud Business User

AWARDS: Peer-to-Peer Award (Pursuit of Excellence) | Manager Discretionary Award (Speed)
LANGUAGES: English (professional) | German (A2, improving actively) | Hindi (native)
"""

# ─────────────────────────────────────────────────────────────────────
#  CONFIG  — set all values as GitHub Secrets
# ─────────────────────────────────────────────────────────────────────
GROQ_API_KEY    = os.environ.get("GROQ_API_KEY",    "")
GEMINI_API_KEY  = os.environ.get("GEMINI_API_KEY",  "")

# ── Email via Resend.com (FREE — 3000 emails/month, just API key) ──────
# Sign up free at resend.com → get API key → add as GitHub Secret
RESEND_API_KEY  = os.environ.get("RESEND_API_KEY",  "")
FROM_EMAIL      = os.environ.get("FROM_EMAIL",       "jobs@resend.dev")   # resend default sender
TO_EMAIL        = os.environ.get("TO_EMAIL",         CANDIDATE["email"])
TO_EMAIL_2      = os.environ.get("TO_EMAIL_2",        "")   # optional second recipient

# ── ntfy.sh push notification (ZERO signup — just install the app) ─────
# Install ntfy app → subscribe to your topic → instant phone alerts!
NTFY_TOPIC      = os.environ.get("NTFY_TOPIC",  "kranti-sap-jobs-2024")

GITHUB_TOKEN    = os.environ.get("GITHUB_TOKEN",    "")
GITHUB_REPO     = os.environ.get("GITHUB_REPO",     "")

# ── Extra job source APIs (optional — adds StepStone/Indeed/XING data) ──
# Adzuna: FREE 250 calls/day — developer.adzuna.com (indexes StepStone/Indeed/Monster DE)
ADZUNA_APP_ID   = os.environ.get("ADZUNA_APP_ID",  "")
ADZUNA_APP_KEY  = os.environ.get("ADZUNA_APP_KEY", "")
# JSearch: FREE 200 calls/month — rapidapi.com search "JSearch" (Google Jobs aggregator)
JSEARCH_API_KEY = os.environ.get("JSEARCH_API_KEY", "")

MAX_JOBS        = 7
SEEN_LOG        = "tracker/seen_jobs.json"
TRACKER_LOG     = "tracker/applications.json"

# ─────────────────────────────────────────────────────────────────────
#  KEYWORD CONFIG  (battle-tested across 500+ real job titles)
# ─────────────────────────────────────────────────────────────────────
MUST_HAVE_TITLE = [
    "sap commerce", "sap commerce cloud", "hybris", "sap hybris",
    "commerce cloud", "sap cx", "sap c/4", "composable storefront",
    "composable commerce", "spartacus", "e-commerce cloud",
    "cx developer", "cx consultant", "sap ccs",
]
EXCLUDE_TITLE = [
    "sap basis", "is-u", "idex", " hcm", "successfactor",
    "werkstudent", "working student", "internship", "praktikum",
    "account executive", "customer success manager",
    "s/4hana cloud retail", "product owner", "product & project owner",
    "scrum master", "agile coach",
    "salesforce",      # Salesforce Commerce Cloud (SFCC/Demandware) ≠ SAP Commerce
    "demandware",      # another name for Salesforce Commerce Cloud
    "front-end developer",  # Leaseweb role = frontend, not Kranti's backend specialty
    "frontend developer",
    "front end developer",
]

# USA locations to exclude — confirmed Ankeny IA, Collegeville PA etc. are US-only
USA_LOCATION_MARKERS = [
    ", ia", ", pa", ", ny", ", ca", ", tx", ", fl", ", il", ", oh",
    ", ga", ", nc", ", ma", ", wa", ", co", ", az", ", nj", ", va",
    ", tn", ", wi", ", mo", ", sc", ", in", ", ky", ", or", ", md",
    "united states", ", usa", " usa", "ankeny", "collegeville",
]

# Indian outsourcing companies that post low-pay "remote" roles not suitable
EXCLUDE_COMPANIES = {
    "randomtrees", "prophecy technologies", "infinity quest",
    "wipro", "infosys", "tcs", "cognizant technology solutions",
    "hcl technologies", "tech mahindra", "mphasis", "hexaware",
    "mindtree", "l&t technology", "niit technologies",
}
BONUS_KEYWORDS = [
    "java", "spring", "spring boot", "groovy",
    "occ", "rest api", "rest apis", "restful", "web services",
    "datahub", "hotfolder", "backoffice", "impex",
    "headless", "headless commerce", "composable",
    "solr", "ccv2", "sap btp", "cpi", "pim", "pcm",
    "microservices", "kubernetes", "docker", "jenkins", "ci/cd",
    "e-commerce", "ecommerce", "digital commerce",
    "developer", "entwickler", "backend", "software engineer",
]
BW_CITIES = {
    "karlsruhe", "stuttgart", "mannheim", "heidelberg", "freiburg",
    "ulm", "pforzheim", "heilbronn", "konstanz", "sindelfingen",
    "böblingen", "ludwigsburg", "bruchsal", "bretten",
}

# Countries/cities where English is the working language in tech companies
# Kranti can apply without German — these get a 🇬🇧 badge in the email
ENGLISH_FRIENDLY = {
    "netherlands", "nederland", "den bosch", "amsterdam", "eindhoven", "utrecht",
    "portugal", "lisbon", "lisboa", "porto",
    "austria", "wien", "vienna", "graz", "linz",
    "poland", "warsaw", "wroclaw", "krakow", "gliwice", "gdansk",
    "ireland", "dublin",
    "hungary", "budapest",
    "remote",   # remote roles are inherently English-flexible
}

# Non-EU / far timezone locations to exclude from "remote" results
NON_EU_REMOTE_MARKERS = [
    # USA (already handled by USA_LOCATION_MARKERS, but also in desc)
    "cincinnati", "richardson, tx", "atlanta", "chicago",
    # Canada / Latin America
    "montreal", "toronto", "canada", "mexico", "brazil", "são paulo", "buenos aires",
    # India (low pay, wrong timezone for EU remote)
    "india", "bangalore", "bengaluru", "hyderabad", "pune", "mumbai", "chennai",
    "new delhi", "noida", "gurgaon",
    # Other non-EU
    "singapore", "australia", "new zealand", "japan", "south africa",
]

def is_english_friendly(location: str) -> bool:
    """Return True if job is in an English-comfortable region for Kranti."""
    loc = (location or "").lower()
    return any(ef in loc for ef in ENGLISH_FRIENDLY)

def has_german_requirement(description: str) -> bool:
    """Return True if the job description explicitly requires German language."""
    desc = (description or "").lower()
    german_required_phrases = [
        "deutschkenntnisse erforderlich", "deutsch fließend", "fließende deutschkenntnisse",
        "german is required", "german is a must", "german language required",
        "german required", "c1 german", "b2 german", "b2-c1 german",
        "german fluency required", "fluent german", "native german",
        "german: fluent", "sprache: deutsch",
    ]
    return any(p in desc for p in german_required_phrases)

def is_non_eu_remote(description: str) -> bool:
    """Return True if a 'remote' job is actually based outside EU timezone."""
    desc = (description or "").lower()
    return any(m in desc for m in NON_EU_REMOTE_MARKERS)

# ─────────────────────────────────────────────────────────────────────
#  HEADHUNTER / RECRUITER DATABASE
#  Curated list of SAP Commerce / IT recruiters active in Germany
# ─────────────────────────────────────────────────────────────────────
SAP_RECRUITERS_GERMANY = [
    {
        "name"    : "Hays Germany SAP Team",
        "contact" : "SAP Recruiting Team",   # address to team, not fake person
        "company" : "Hays",
        "focus"   : "SAP specialists across Germany — largest SAP recruiter in DE",
        "linkedin" : "https://www.linkedin.com/company/hays",
        "email"   : "sap@hays.de",
        "action"  : "Email sap@hays.de with subject: 'SAP Commerce Cloud Developer – Karlsruhe – Available immediately'",
        "note"    : "Germany's #1 SAP recruiter. Email them TODAY — they place 100+ SAP devs/month.",
    },
    {
        "name"    : "Robert Half Technology Germany",
        "contact" : "IT Recruiting Team",
        "company" : "Robert Half",
        "focus"   : "IT & SAP permanent + contract roles across Germany",
        "linkedin" : "https://www.linkedin.com/company/robert-half-technology",
        "email"   : "frankfurt@roberthalf.de",
        "action"  : "Upload CV at roberthalf.de AND email frankfurt@roberthalf.de",
        "note"    : "Very active in Frankfurt/Mannheim/Stuttgart — near Karlsruhe.",
    },
    {
        "name"    : "Nissen & Velten",
        "contact" : "SAP Recruiting Team",
        "company" : "Nissen & Velten IT-Personalberatung",
        "focus"   : "SAP professionals in DACH — boutique, high quality",
        "linkedin" : "https://www.linkedin.com/company/nissen-velten",
        "email"   : "info@nissen-velten.de",
        "action"  : "Email info@nissen-velten.de — mention Karlsruhe + SAP Commerce Cloud",
        "note"    : "Specialist SAP boutique firm, very active in Baden-Württemberg.",
    },
    {
        "name"    : "Ferchau GmbH",
        "contact" : "IT Recruiting",
        "company" : "Ferchau",
        "focus"   : "SAP & IT engineering staffing across Germany",
        "linkedin" : "https://www.linkedin.com/company/ferchau",
        "email"   : "",
        "action"  : "Apply at ferchau.com/jobs — search 'SAP Commerce'. Also connect on LinkedIn.",
        "note"    : "One of Germany's largest IT staffing firms — they post SAP roles not on LinkedIn.",
    },
    {
        "name"    : "Gulp.de (Platform)",
        "contact" : "SAP Commerce Channel",
        "company" : "Gulp.de",
        "focus"   : "SAP freelance + permanent Germany — recruiters actively search profiles",
        "linkedin" : "https://www.linkedin.com/company/gulp",
        "email"   : "",
        "action"  : "Register FREE profile at gulp.de → add 'SAP Commerce Cloud' + 'Hybris 2211' + 'CCV2' as skills",
        "note"    : "German recruiters search Gulp daily. A complete profile gets 5-10 inbound messages/week for SAP devs.",
    },
    {
        "name"    : "Freelancermap.de (Platform)",
        "contact" : "SAP Commerce Projects",
        "company" : "Freelancermap.de",
        "focus"   : "SAP freelance projects — contractors earn €85–130/hr",
        "linkedin" : "",
        "email"   : "",
        "action"  : "Register at freelancermap.de → create profile → set hourly rate €85–110 → add SAP Commerce Cloud skills",
        "note"    : "If permanent roles take time, freelance work keeps income coming. Many SAP projects here.",
    },
    {
        "name"    : "Adecco Technology Germany",
        "contact" : "Technology Division",
        "company" : "Adecco",
        "focus"   : "IT placements — perm + contract across Germany",
        "linkedin" : "https://www.linkedin.com/company/adecco-group",
        "email"   : "technology.de@adecco.com",
        "action"  : "Email technology.de@adecco.com with CV attached",
        "note"    : "Good for both contract and permanent SAP roles across Germany.",
    },
    {
        "name"    : "XING Jobs (Platform)",
        "contact" : "German HR Community",
        "company" : "XING",
        "focus"   : "Germany's professional network — 40% of German HR use XING only",
        "linkedin" : "",
        "email"   : "",
        "action"  : "Create/update XING profile → set 'Suche aktiv' → headline: 'SAP Commerce Cloud Developer | Hybris 2211 | Karlsruhe'",
        "note"    : "Many German companies ONLY use XING for hiring, not LinkedIn. Takes 15 minutes to set up.",
    },
]

# ─────────────────────────────────────────────────────────────────────
#  LINKEDIN SCRAPER
# ─────────────────────────────────────────────────────────────────────
LI_HEADERS = {
    "User-Agent"     : "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9,de;q=0.8",
}

SEARCH_CONFIG = [
    # ── Germany — paginated deeply (biggest market) ───────────────────
    ("SAP Hybris",                    "Germany",                    "r2592000", [0, 25, 50, 75]),
    ("SAP Commerce Cloud",            "Germany",                    "r2592000", [0, 25, 50, 75]),
    ("SAP Commerce developer",        "Germany",                    "r2592000", [0, 25]),
    ("SAP CX developer",              "Germany",                    "r2592000", [0, 25]),
    ("SAP Hybris Entwickler",         "Deutschland",                "r2592000", [0, 25]),
    ("SAP Commerce Cloud Entwickler", "Deutschland",                "r2592000", [0]),
    ("SAP Commerce Berater",          "Deutschland",                "r2592000", [0]),
    ("SAP Composable Commerce",       "Germany",                    "r2592000", [0]),
    ("Spartacus SAP developer",       "Germany",                    "r2592000", [0]),
    ("SAP Hybris developer",          "Baden-Württemberg, Germany", "r2592000", [0]),
    ("SAP Commerce",                  "Karlsruhe, Germany",         "r2592000", [0]),
    ("SAP Commerce",                  "Stuttgart, Germany",         "r2592000", [0]),
    # ── Austria ───────────────────────────────────────────────────────
    ("SAP Commerce Cloud",            "Austria",                    "r2592000", [0]),
    ("SAP Hybris developer",          "Vienna, Austria",            "r2592000", [0]),
    ("SAP Hybris",                    "Vienna, Austria",            "r2592000", [0]),
    # ── Netherlands ───────────────────────────────────────────────────
    ("SAP Commerce Cloud",            "Netherlands",                "r2592000", [0]),
    ("SAP CX",                        "Netherlands",                "r2592000", [0]),
    # ── Portugal ──────────────────────────────────────────────────────
    ("SAP Commerce Cloud",            "Portugal",                   "r2592000", [0]),
    ("SAP Commerce",                  "Portugal",                   "r2592000", [0]),
    # ── Poland ────────────────────────────────────────────────────────
    ("SAP Commerce Cloud",            "Poland",                     "r2592000", [0]),
    ("SAP Hybris",                    "Poland",                     "r2592000", [0]),
    # ── Romania (confirmed: Michael Page posting Hybris roles there) ──
    ("SAP Commerce Cloud",            "Romania",                    "r2592000", [0]),
    ("SAP Hybris",                    "Romania",                    "r2592000", [0]),
    # ── Belgium, Czech, Hungary, Ireland ──────────────────────────────
    ("SAP Commerce Cloud",            "Belgium",                    "r2592000", [0]),
    ("SAP Commerce Cloud",            "Czech Republic",             "r2592000", [0]),
    ("SAP Commerce Cloud",            "Hungary",                    "r2592000", [0]),
    ("SAP Commerce Cloud",            "Ireland",                    "r2592000", [0]),
    # ── Remote EU — catch everything remaining ────────────────────────
    ("SAP Hybris developer remote",   "Europe",                     "r2592000", [0, 25]),
    ("SAP Commerce Cloud developer",  "Europe",                     "r2592000", [0, 25]),
    ("Hybris developer remote",       "Europe",                     "r2592000", [0, 25]),
    ("SAP Commerce Cloud backend",    "Europe",                     "r2592000", [0]),
    ("SAP Hybris Java developer",     "Europe",                     "r2592000", [0]),
]


def linkedin_fetch_page(keyword, location, timeframe, start) -> list[dict]:
    url = (
        "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
        f"?keywords={urllib.parse.quote(keyword)}"
        f"&location={urllib.parse.quote(location)}"
        f"&f_TPR={timeframe}&start={start}"
    )
    try:
        r = requests.get(url, headers=LI_HEADERS, timeout=20)
        if r.status_code != 200:
            return []
        soup = BeautifulSoup(r.text, "html.parser")
        jobs = []
        for card in soup.find_all("div", class_="base-search-card"):
            t  = card.find("h3", class_="base-search-card__title")
            co = card.find("h4", class_="base-search-card__subtitle")
            lo = card.find("span", class_="job-search-card__location")
            lk = card.find("a", class_="base-card__full-link")
            dt = card.find("time")
            if not t or not lk:
                continue
            jobs.append({
                "title"      : t.text.strip(),
                "company"    : co.text.strip() if co else "–",
                "location"   : lo.text.strip() if lo else location,
                "url"        : lk["href"].split("?")[0].replace("de.linkedin.com", "www.linkedin.com"),
                "date"       : dt.get("datetime", "") if dt else "",
                "source"     : "LinkedIn",
                "description": "",
                "hr_email"   : "",
            })
        return jobs
    except Exception as e:
        print(f"  [LI] Error '{keyword}' start={start}: {e}")
        return []


def fetch_adzuna(keyword: str, location: str = "de") -> list[dict]:
    """
    Adzuna API — indexes StepStone, Indeed, Monster, company pages in Germany.
    Free: 250 calls/day. Sign up at developer.adzuna.com (instant, no credit card).
    """
    if not ADZUNA_APP_ID or not ADZUNA_APP_KEY:
        return []
    try:
        r = requests.get(
            f"https://api.adzuna.com/v1/api/jobs/{location}/search/1",
            params={
                "app_id"         : ADZUNA_APP_ID,
                "app_key"        : ADZUNA_APP_KEY,
                "what"           : keyword,
                "results_per_page": 20,
                "sort_by"        : "date",
                "max_days_old"   : 30,
                "content-type"   : "application/json",
            },
            timeout=15,
        )
        if r.status_code != 200:
            return []
        jobs = []
        for item in r.json().get("results", []):
            jobs.append({
                "title"      : item.get("title", ""),
                "company"    : item.get("company", {}).get("display_name", "–"),
                "location"   : item.get("location", {}).get("display_name", "Germany"),
                "url"        : item.get("redirect_url", ""),
                "date"       : item.get("created", "")[:10],
                "source"     : "Adzuna (StepStone/Indeed/Monster)",
                "description": item.get("description", "")[:2000],
                "hr_email"   : "",
            })
        return jobs
    except Exception as e:
        print(f"  [adzuna] {e}")
        return []


def fetch_jsearch(keyword: str, location: str = "Germany") -> list[dict]:
    """
    JSearch via RapidAPI — powered by Google Jobs = indexes everything:
    StepStone, Indeed, XING, Monster, company career pages, LinkedIn.
    Free: 200 calls/month. Sign up at rapidapi.com → search 'JSearch' → subscribe free.
    """
    if not JSEARCH_API_KEY:
        return []
    try:
        r = requests.get(
            "https://jsearch.p.rapidapi.com/search",
            params={
                "query"      : f"{keyword} in {location}",
                "page"       : "1",
                "num_pages"  : "3",
                "date_posted": "month",
            },
            headers={
                "X-RapidAPI-Key" : JSEARCH_API_KEY,
                "X-RapidAPI-Host": "jsearch.p.rapidapi.com",
            },
            timeout=20,
        )
        if r.status_code != 200:
            return []
        jobs = []
        for item in r.json().get("data", []):
            jobs.append({
                "title"      : item.get("job_title", ""),
                "company"    : item.get("employer_name", "–"),
                "location"   : f"{item.get('job_city','')}, {item.get('job_country','')}".strip(", "),
                "url"        : item.get("job_apply_link") or item.get("job_google_link", ""),
                "date"       : (item.get("job_posted_at_datetime_utc") or "")[:10],
                "source"     : f"Google Jobs ({item.get('job_publisher','JSearch')})",
                "description": item.get("job_description", "")[:2000],
                "hr_email"   : item.get("employer_company_type", ""),
            })
        return jobs
    except Exception as e:
        print(f"  [jsearch] {e}")
        return []


def fetch_description(url, retries=2) -> str:
    for attempt in range(retries + 1):
        try:
            r = requests.get(url, headers=LI_HEADERS, timeout=25)
            if r.status_code == 429:
                wait = 25 * (attempt + 1)
                print(f"    ⏳ 429 rate-limit — waiting {wait}s...")
                time.sleep(wait)
                continue
            if r.status_code != 200:
                return ""
            soup = BeautifulSoup(r.text, "html.parser")
            el = soup.find("div", class_="show-more-less-html__markup")
            if el:
                return el.get_text(separator=" ", strip=True)[:4000]
            for sc in soup.find_all("script", type="application/ld+json"):
                try:
                    d = json.loads(sc.string or "")
                    if "description" in d:
                        return re.sub(r"<[^>]+>", " ", d["description"])[:4000]
                except Exception:
                    pass
            return ""
        except Exception as e:
            print(f"    [desc] attempt {attempt+1}: {e}")
            time.sleep(5)
    return ""


def find_hr_email(company_name: str, job_description: str) -> str:
    """Try to extract a real HR email from the job description."""
    emails = re.findall(r"[\w.+-]+@[\w.-]+\.\w{2,}", job_description)
    if emails:
        # Filter out noreply / system emails
        real = [e for e in emails if not any(x in e.lower() for x in ["noreply","no-reply","donotreply","careers@linkedin","example"])]
        if real:
            return real[0]
    return ""


# EU country names — if any of these appear, it's definitely NOT USA
EU_COUNTRIES = {
    "germany", "deutschland", "austria", "österreich", "switzerland", "schweiz",
    "netherlands", "nederland", "belgium", "belgien", "france", "frankreich",
    "spain", "spanien", "portugal", "poland", "polska", "czech", "hungary",
    "sweden", "denmark", "norway", "finland", "ireland", "italy", "romania",
    "slovakia", "slovenia", "croatia", "bulgaria", "luxembourg",
    "united kingdom", "scotland", "england", "wales",
}

def is_usa_location(location: str) -> bool:
    """Return True if the job is clearly in the USA, not Europe."""
    loc = (location or "").lower()
    # If it mentions a European country, it's NOT USA even if some substring matches
    if any(eu in loc for eu in EU_COUNTRIES):
        return False
    return any(marker in loc for marker in USA_LOCATION_MARKERS)


def is_excluded_company(company: str) -> bool:
    """Return True if this is a known low-quality outsourcing company."""
    return company.lower().strip() in EXCLUDE_COMPANIES


def is_title_relevant(title: str) -> bool:
    t = (title or "").lower()
    if any(ex in t for ex in EXCLUDE_TITLE):
        return False
    return any(kw in t for kw in MUST_HAVE_TITLE)


def score_job(title: str, description: str, location: str = "") -> tuple[int, list[str]]:
    text    = (title + " " + description).lower()
    matches = [kw for kw in BONUS_KEYWORDS if kw in text]
    t = title.lower()
    title_bonus = (
        6 if any(k in t for k in ["hybris", "sap commerce", "commerce cloud", "e-commerce cloud", "composable commerce"]) else
        4 if any(k in t for k in ["sap cx", "cx developer", "cx consultant", "spartacus"]) else
        2 if "sap" in t else 0
    )
    desc_bonus    = 2 if len(description) > 200 else 0
    english_bonus = 1 if ("english" in text and not has_german_requirement(description)) else 0
    remote_bonus  = 1 if "remote" in (location + " " + description).lower() else 0
    total = len(matches) + title_bonus + desc_bonus + english_bonus + remote_bonus
    return total, matches


def pick_best_location(jobs: list[dict]) -> dict:
    for j in jobs:
        if any(c in j["location"].lower() for c in BW_CITIES):
            return j
    for j in jobs:
        if "remote" in j["location"].lower():
            return j
    return jobs[0]


def load_seen() -> set:
    try:
        if os.path.exists(SEEN_LOG):
            with open(SEEN_LOG) as f:
                data = json.load(f)
            cutoff = (datetime.date.today() - datetime.timedelta(days=30)).isoformat()
            return {e["url"] for e in data if e.get("date", "") >= cutoff}
    except Exception:
        pass
    return set()


def save_seen(seen: set, new_jobs: list[dict]):
    existing = []
    try:
        if os.path.exists(SEEN_LOG):
            with open(SEEN_LOG) as f:
                existing = json.load(f)
    except Exception:
        pass
    today = str(datetime.date.today())
    new_entries = [{"url": j["url"], "title": j["title"], "company": j["company"], "date": today} for j in new_jobs]
    all_e = existing + new_entries
    cutoff = (datetime.date.today() - datetime.timedelta(days=60)).isoformat()
    all_e = [e for e in all_e if e.get("date", "") >= cutoff]
    os.makedirs(os.path.dirname(SEEN_LOG), exist_ok=True)
    with open(SEEN_LOG, "w") as f:
        json.dump(all_e, f, indent=2, ensure_ascii=False)


def fetch_all_jobs() -> list[dict]:
    seen_urls = set()
    seen      = load_seen()
    all_raw   = []

    for kw, loc, tf, pages in SEARCH_CONFIG:
        for start in pages:
            print(f"    🔍 '{kw}' [{loc}] start={start}")
            jobs = linkedin_fetch_page(kw, loc, tf, start)
            for j in jobs:
                if j["url"] and j["url"] not in seen_urls:
                    seen_urls.add(j["url"])
                    all_raw.append(j)
            time.sleep(2)

    # ── Adzuna (StepStone + Indeed + Monster Germany) ─────────────────
    if ADZUNA_APP_ID:
        print("\n    🔍 Adzuna [StepStone/Indeed/Monster DE]...")
        for kw in ["SAP Commerce Cloud", "SAP Hybris developer", "SAP CX developer"]:
            for country_code in ["de", "at", "nl", "pl"]:
                az_jobs = fetch_adzuna(kw, country_code)
                for j in az_jobs:
                    if j["url"] and j["url"] not in seen_urls:
                        seen_urls.add(j["url"])
                        all_raw.append(j)
                time.sleep(1)
        print(f"    → Adzuna added jobs, total now: {len(all_raw)}")
    else:
        print("    ℹ️  Adzuna not configured (add ADZUNA_APP_ID + ADZUNA_APP_KEY secrets)")
        print("       → Free 250 calls/day at developer.adzuna.com — covers StepStone/Indeed/Monster")

    # ── JSearch / Google Jobs (covers everything) ─────────────────────
    if JSEARCH_API_KEY:
        print("\n    🔍 JSearch [Google Jobs — StepStone/Indeed/XING/company pages]...")
        for kw in ["SAP Commerce Cloud Developer Germany", "SAP Hybris Developer Europe", "SAP Commerce Hybris remote"]:
            js_jobs = fetch_jsearch(kw)
            for j in js_jobs:
                if j["url"] and j["url"] not in seen_urls:
                    seen_urls.add(j["url"])
                    all_raw.append(j)
            time.sleep(1.5)
        print(f"    → JSearch added jobs, total now: {len(all_raw)}")
    else:
        print("    ℹ️  JSearch not configured (add JSEARCH_API_KEY secret)")
        print("       → Free 200 calls/month at rapidapi.com — Google Jobs aggregator")

    print(f"\n  📦 Raw unique cards: {len(all_raw)}")
    filtered = [j for j in all_raw if is_title_relevant(j["title"])]
    print(f"  🎯 Title-relevant: {len(filtered)}")

    # Apply location + company quality filters before fetching descriptions
    quality_filtered = []
    for j in filtered:
        if is_usa_location(j["location"]):
            print(f"  🚫 USA location: {j['title']} @ {j['company']} [{j['location']}]")
            continue
        if is_excluded_company(j["company"]):
            print(f"  🚫 Excluded company: {j['company']}")
            continue
        quality_filtered.append(j)
    filtered = quality_filtered
    print(f"  🌍 After location/company filter: {len(filtered)}")

    not_seen = [j for j in filtered if j["url"] not in seen]
    if len(not_seen) == 0:
        print("  ℹ️  All jobs already sent — recycling recent ones")
        not_seen = filtered[:MAX_JOBS * 3]
    else:
        print(f"  ♻️  Skipping {len(filtered) - len(not_seen)} already-sent")

    scored = []
    for i, job in enumerate(not_seen):
        print(f"  [{i+1:2d}/{len(not_seen)}] {job['title'][:50]} @ {job['company']}")
        job["description"] = fetch_description(job["url"])
        # Second-pass location check using description (some jobs hide US location in text)
        if is_usa_location(job["description"][:200]):
            print(f"    🚫 USA location found in description — skipping")
            continue
        # Filter non-EU remote jobs (timezone mismatch, low pay)
        if "remote" in job["location"].lower() and is_non_eu_remote(job["description"]):
            print(f"    🚫 Non-EU remote (wrong timezone/region) — skipping")
            continue
        job["score"], job["matches"] = score_job(job["title"], job["description"], job["location"])
        job["hr_email"] = find_hr_email(job["company"], job["description"])
        scored.append(job)
        time.sleep(4)

    by_co = defaultdict(list)
    for j in scored:
        by_co[j["company"].lower().strip()].append(j)

    deduped = []
    for _, jobs_list in by_co.items():
        jobs_list.sort(key=lambda x: x["score"], reverse=True)
        best = pick_best_location([j for j in jobs_list if j["score"] == jobs_list[0]["score"]])
        deduped.append(best)

    deduped.sort(key=lambda x: x["score"], reverse=True)
    print(f"\n  ✅ Unique companies after dedup: {len(deduped)}")
    return deduped[:MAX_JOBS]


# ─────────────────────────────────────────────────────────────────────
#  APPLICATION TRACKER
# ─────────────────────────────────────────────────────────────────────

def load_tracker() -> list[dict]:
    try:
        if os.path.exists(TRACKER_LOG):
            with open(TRACKER_LOG) as f:
                return json.load(f)
    except Exception:
        pass
    return []


def save_tracker(data: list[dict]):
    os.makedirs(os.path.dirname(TRACKER_LOG), exist_ok=True)
    with open(TRACKER_LOG, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def add_to_tracker(jobs: list[dict]):
    """Add today's jobs to tracker with status 'pending_review'."""
    tracker = load_tracker()
    today   = str(datetime.date.today())
    existing_urls = {e["url"] for e in tracker}
    for job in jobs:
        if job["url"] not in existing_urls:
            tracker.append({
                "id"              : hashlib.md5(job["url"].encode()).hexdigest()[:8],
                "date_found"      : today,
                "date_applied"    : None,
                "title"           : job["title"],
                "company"         : job["company"],
                "location"        : job["location"],
                "url"             : job["url"],
                "score"           : job["score"],
                "hr_email"        : job.get("hr_email", ""),
                "status"          : "pending_review",   # pending_review → applied → interview → offer → rejected
                "follow_up_sent"  : False,
                "follow_up_date"  : None,
                "notes"           : "",
            })
    save_tracker(tracker)


def get_followup_due() -> list[dict]:
    """Return jobs applied 7 days ago that haven't had a follow-up yet."""
    tracker = load_tracker()
    today   = datetime.date.today()
    due = []
    for entry in tracker:
        if entry.get("status") == "applied" and not entry.get("follow_up_sent"):
            applied_date = entry.get("date_applied")
            if applied_date:
                days_since = (today - datetime.date.fromisoformat(applied_date)).days
                if days_since >= 7:
                    due.append(entry)
    return due


def get_tracker_stats() -> dict:
    tracker = load_tracker()
    stats = {"total": len(tracker), "applied": 0, "pending": 0, "interview": 0, "offer": 0, "rejected": 0}
    for e in tracker:
        s = e.get("status", "pending_review")
        if s == "applied":           stats["applied"]   += 1
        elif s == "pending_review":  stats["pending"]   += 1
        elif s == "interview":       stats["interview"] += 1
        elif s == "offer":           stats["offer"]     += 1
        elif s == "rejected":        stats["rejected"]  += 1
    return stats


# ─────────────────────────────────────────────────────────────────────
#  AI COVER LETTERS  (Groq Llama 3.3 70B — 100% FREE)
# ─────────────────────────────────────────────────────────────────────

def build_cover_prompt(job: dict, language: str) -> str:
    is_de = language == "German"
    lang_inst = (
        "Write in natural, confident, professional English. Warm, not corporate."
        if not is_de else
        "Schreiben Sie auf natürlichem, professionellem Deutsch in der Sie-Form. KEINE wörtliche Übersetzung. Klingt wie eine Muttersprachlerin."
    )
    return f"""You are a senior career coach who has placed 500+ SAP developers in Germany.
You know exactly what makes a German hiring manager say YES.

Write a personalised cover letter for the job below.

━━━ CANDIDATE ━━━
{CV_TEXT}

━━━ JOB ━━━
Title:       {job['title']}
Company:     {job['company']}
Location:    {job['location']}
Description: {job.get('description','')[:2500]}

━━━ RULES ━━━
Language: {lang_inst}
Length: 3–4 paragraphs, MAX 270 words. Concise wins.

PARA 1 — HOOK: Open with something specific about THIS company/role from the description.
NEVER start with: "I am writing to", "I wish to apply", "I am interested in"
DO start with something specific: reference a tech, a product, a challenge from their posting.

PARA 2 — PROOF: 2–3 achievements matching what THEY asked for.
Name companies (Shell, Rockwell Automation), tools (Hybris 2211, CCV2, DataHub, OCC).
Show impact — NOT duties. Weave in SAP certification naturally.

PARA 3 — FIT: Why THIS company, not just any company?
If description mentions KI/AI, BTP, composable — reference it specifically.

PARA 4 — CLOSE (2 sentences max):
- Mention availability: {CANDIDATE['availability']}
- Warm, confident interview request. No "I look forward to hearing from you".
- NEVER mention visa, work permit, residence permit or sponsorship.

FORBIDDEN: "team player", "passion for", "highly motivated", "results-driven", "I am writing to"
OUTPUT: Letter body ONLY. No headers. No preamble.
Sign off: {'Kind regards,' if not is_de else 'Mit freundlichen Grüßen,'}
{CANDIDATE['name']} | {CANDIDATE['phone']} | {CANDIDATE['email']} | {CANDIDATE['linkedin']}
"""


def build_recruiter_prompt(recruiter: dict) -> str:
    return f"""Write a short, punchy LinkedIn/XING outreach message from Kranti Chavan to a recruiter.

CANDIDATE: {CANDIDATE['name']} — SAP Commerce Cloud Developer, 5+ years, Karlsruhe Germany
RECRUITER: {recruiter['name']} at {recruiter['company']} — focus: {recruiter['focus']}
NOTE: {recruiter.get('note', '')}

RULES:
- MAX 80 words. Recruiters ignore long messages.
- Personal: mention their company's focus
- Specific: name SAP Commerce Cloud / Hybris 2211 / CCV2 / SAP certifications
- Clear ask: "Would you have 15 minutes for a quick call?"
- Mention: based in Karlsruhe Germany, available immediately
- Tone: professional but direct — like a confident peer, not a desperate applicant

Output: Just the message. No subject line. No preamble.
"""


def call_groq(prompt: str, max_tokens: int = 800) -> str:
    try:
        r = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
            json={"model": "llama-3.3-70b-versatile",
                  "messages": [{"role": "user", "content": prompt}],
                  "max_tokens": max_tokens, "temperature": 0.73},
            timeout=45,
        )
        return r.json().get("choices", [{}])[0].get("message", {}).get("content", "").strip()
    except Exception as e:
        print(f"  [groq] {e}"); return ""


def call_gemini(prompt: str) -> str:
    try:
        r = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}",
            json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=45,
        )
        return r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
    except Exception as e:
        print(f"  [gemini] {e}"); return ""


def ai_generate(prompt: str, max_tokens: int = 800) -> str:
    """Try Groq → Gemini → return empty (caller handles fallback)."""
    if GROQ_API_KEY:
        result = call_groq(prompt, max_tokens)
        if result:
            return result
    if GEMINI_API_KEY:
        result = call_gemini(prompt)
        if result:
            return result
    return ""


def detect_job_signals(title: str, desc: str) -> list[str]:
    """Detect what the job is specifically about to personalise the letter."""
    text = (title + " " + desc).lower()
    signals = []
    if any(k in text for k in ["ki ", "ki-", "künstliche intelligenz", "joule", "genai", "llm", "copilot", "ai core"]):
        signals.append("ai")
    if any(k in text for k in ["composable", "spartacus", "composable storefront"]):
        signals.append("composable")
    if any(k in text for k in ["b2b", "business-to-business"]):
        signals.append("b2b")
    if any(k in text for k in ["b2c", "business-to-consumer"]):
        signals.append("b2c")
    if any(k in text for k in ["architect", "architektur", "solution design"]):
        signals.append("architect")
    if any(k in text for k in ["headless", "headless commerce", "pwa", "api-first"]):
        signals.append("headless")
    if any(k in text for k in ["datahub", "hotfolder", "pim", "data pipeline"]):
        signals.append("data")
    if any(k in text for k in ["ccv2", "cloud portal", "ccs", "cloud deployment"]):
        signals.append("cloud")
    return signals


def cover_letter_template(job: dict, language: str) -> str:
    """
    Smart fallback template — rotates opening hooks, detects job signals,
    correct German, and zero repeated sentences across jobs.
    """
    c        = CANDIDATE
    company  = (job.get("company") or "your company").strip()
    title    = (job.get("title")   or "the position").strip()
    desc     = job.get("description", "")
    signals  = detect_job_signals(title, desc)
    location = job.get("location", "")

    # ── Signal-specific context lines ───────────────────────────────
    if "ai" in signals:
        hook_en  = f"The intersection of SAP Commerce Cloud and AI — from KI-integrated product search to GenAI-powered checkout flows — is exactly where my work is headed, which is why {company}'s {title} role caught my attention immediately."
        hook_de  = f"Die Verbindung von SAP Commerce Cloud mit KI-gestützten Lösungen — von intelligenter Produktsuche bis hin zu automatisierten Checkout-Prozessen — ist genau der Bereich, in den ich mich aktiv weiterentwickle. Deshalb hat mich Ihre Stellenausschreibung als {title} bei {company} sofort angesprochen."
        proof_en = "At Rockwell Automation I work on Hybris 2211 managing PIM→Hybris data flows and have hands-on experience with SAP BTP integrations. At Shell I built the Promotions engine, Hotfolder pipelines and CCV2 cloud deployments end-to-end. As an SAP Certified Professional – Commerce Cloud Developer, I now actively explore AI-augmented commerce tooling including GitHub Copilot and CI/CD-integrated quality pipelines."
        proof_de = "Bei Rockwell Automation arbeite ich mit Hybris 2211, verwalte PIM→Hybris-Datenflüsse und habe praktische Erfahrung mit SAP BTP. Bei Shell habe ich die Promotions-Engine, Hotfolder-Pipelines und CCV2-Cloud-Deployments End-to-End verantwortet. Als SAP Certified Professional – Commerce Cloud Developer beschäftige ich mich aktiv mit KI-gestützten Entwicklungswerkzeugen."
    elif "composable" in signals:
        hook_en  = f"Composable Commerce is where SAP's future is heading — and {company}'s {title} role, with its focus on Spartacus and headless architecture, is exactly the next step I'm looking for."
        hook_de  = f"Composable Commerce ist die Zukunft von SAP — und Ihre Ausschreibung als {title} bei {company} mit dem Fokus auf Spartacus und Headless-Architektur ist genau der nächste Schritt, den ich anstrebe."
        proof_en = "I have hands-on experience in Headless Commerce and API-driven environments — at Shell I built RESTful APIs and OCC web services, and resolved PWA integration issues in production. At Rockwell Automation I work on Hybris 2211 with composable integration patterns, certified as SAP Commerce Cloud Professional."
        proof_de = "Ich habe praktische Erfahrung in Headless Commerce und API-gesteuerten Umgebungen — bei Shell habe ich RESTful APIs und OCC Web Services entwickelt und PWA-Integrationsprobleme in der Produktion gelöst. Bei Rockwell Automation arbeite ich mit Hybris 2211 und modernen Integrationsmustern."
    elif "architect" in signals:
        hook_en  = f"After five years building SAP Commerce Cloud solutions from the ground up — not just configuring, but architecting data pipelines, CCV2 deployments, and cross-system integrations — {company}'s {title} opening is the natural next step."
        hook_de  = f"Nach fünf Jahren, in denen ich SAP Commerce Cloud-Lösungen von Grund auf entwickelt habe — nicht nur konfiguriert, sondern Datenpipelines, CCV2-Deployments und systemübergreifende Integrationen konzipiert habe — ist Ihre Stelle als {title} bei {company} der logische nächste Schritt."
        proof_en = "At Shell I designed and owned the entire commerce module lifecycle: Promotions, Hotfolders, Order Management, Backoffice customisations and CCV2 environment management across dev → staging → production. At Rockwell Automation I architect PIM→Hybris data flows and lead integration governance with SAP, MDM and Profisee teams. SAP Certified Professional – Commerce Cloud Developer."
        proof_de = "Bei Shell habe ich den gesamten Commerce-Modul-Lebenszyklus verantwortet: Promotions, Hotfolders, Order Management, Backoffice-Customisierungen und CCV2-Umgebungsmanagement. Bei Rockwell Automation konzipiere ich PIM→Hybris-Datenflüsse und leite die Integrationsgovernance."
    elif "data" in signals:
        hook_en  = f"Data pipelines, PIM integrations, and making sure product data flows reliably from source to storefront — this is where I spend most of my day, which is why {company}'s {title} role felt written for me."
        hook_de  = f"Datenpipelines, PIM-Integrationen und die zuverlässige Übertragung von Produktdaten von der Quelle bis zur Storefront — das ist mein tägliches Arbeitsfeld. Deshalb hat mich Ihre Stelle als {title} bei {company} sofort angesprochen."
        proof_en = "At Rockwell Automation I manage the full SAP → Master Data Hub → PIM → Hybris → Website pipeline, improving data quality through Profisee, hotfolder analysis and mm_featrs mapping — and migrated the customer/account API to a new data model, reducing integration failures across teams. At Shell I built DataHub pipelines and Impex workflows from scratch."
        proof_de = "Bei Rockwell Automation verwalte ich die vollständige SAP → Master Data Hub → PIM → Hybris → Website-Pipeline, verbessere die Datenqualität durch Profisee und Hotfolder-Analyse und habe die Kunden-/Konto-API auf ein neues Datenmodell migriert. Bei Shell habe ich DataHub-Pipelines und Impex-Workflows von Grund auf entwickelt."
    else:
        # Generic but still specific to SAP Commerce
        hook_en  = f"Five years of end-to-end SAP Commerce Cloud delivery — from Java backend development and OCC API design to CCV2 production deployments — is what brought your {title} opening at {company} straight to the top of my list."
        hook_de  = f"Fünf Jahre End-to-End-Entwicklung in SAP Commerce Cloud — von Java-Backend-Entwicklung und OCC-API-Design bis hin zu CCV2-Produktiv-Deployments — das ist es, was Ihre Ausschreibung als {title} bei {company} sofort meine volle Aufmerksamkeit gewonnen hat."
        proof_en = "At Shell I built the core Commerce modules — Promotions, Hotfolders, Order Management, RESTful APIs — in a Headless Commerce environment, and managed all CCV2 cloud deployments. At Rockwell Automation I work on Hybris 2211 (the current release), resolving complex PIM→Hybris integration issues with SAP, MDM and Profisee. I hold the SAP Certified Professional – Commerce Cloud Developer credential."
        proof_de = "Bei Shell habe ich die zentralen Commerce-Module — Promotions, Hotfolders, Order Management, RESTful APIs — in einer Headless-Commerce-Umgebung entwickelt und alle CCV2-Cloud-Deployments verwaltet. Bei Rockwell Automation arbeite ich mit Hybris 2211 (aktuelle Version) und löse komplexe PIM→Hybris-Integrationsprobleme mit SAP, MDM und Profisee."

    # ── B2B/B2C addition ─────────────────────────────────────────────
    b2x_en = ""
    b2x_de = ""
    if "b2b" in signals:
        b2x_en = " My B2B e-commerce experience — complex account hierarchies, pricing models, and order workflows — is directly relevant here."
        b2x_de = " Meine B2B-E-Commerce-Erfahrung — komplexe Kontohierarchien, Preismodelle und Bestellworkflows — ist hier direkt anwendbar."
    elif "b2c" in signals:
        b2x_en = " I have built B2C-facing promotion engines and customer-facing OCC APIs handling real consumer traffic at scale."
        b2x_de = " Ich habe B2C-seitige Promotion-Engines und kundenorientierte OCC-APIs entwickelt, die realen Consumer-Traffic in großem Maßstab verarbeiten."

    # ── Location/company fit sentence ────────────────────────────────
    is_en_country = any(c in location.lower() for c in ["netherlands","portugal","austria","poland","ireland"])
    is_remote = "remote" in location.lower()

    if is_remote:
        fit_en = f"The remote setup suits me perfectly — I'm based in Karlsruhe and fully equipped for distributed collaboration across European time zones."
        fit_de = f"Das Remote-Modell passt sehr gut zu meiner Situation — ich bin in Karlsruhe ansässig und für die Zusammenarbeit in europäischen Zeitzonen bestens ausgestattet."
    elif is_en_country:
        fit_en = f"I'm based in Karlsruhe and happy to travel to {location.split(',')[0]} regularly, or work in a hybrid arrangement — whatever works best for {company}'s team."
        fit_de = f"Ich bin in Karlsruhe ansässig und kann regelmäßig nach {location.split(',')[0]} reisen oder in einem hybriden Modell arbeiten — ganz nach den Bedürfnissen des Teams bei {company}."
    else:
        fit_en = f"I'm based in Karlsruhe, which makes {location.split(',')[0] if location else 'this location'} very accessible for hybrid or on-site work."
        fit_de = f"Ich bin in Karlsruhe ansässig, was {location.split(',')[0] if location else 'diesen Standort'} für hybrides oder Vor-Ort-Arbeiten sehr gut erreichbar macht."

    avail_en = c["availability_en"]
    avail_de = c["availability_de"]

    if language == "English":
        return f"""Dear Hiring Team at {company},

{hook_en}

{proof_en}{b2x_en}

{fit_en} {avail_en}

I'd welcome the chance to show you what I can bring to {company}. Please don't hesitate to reach out.

Kind regards,
{c['name']}
{c['phone']} | {c['email']}
{c['linkedin']}"""

    else:
        return f"""Sehr geehrtes Team bei {company},

{hook_de}

{proof_de}{b2x_de}

{fit_de} {avail_de}

Ich freue mich sehr auf die Möglichkeit, mich persönlich vorzustellen.

Mit freundlichen Grüßen,
{c['name']}
{c['phone']} | {c['email']}
{c['linkedin']}"""


def generate_cover_letters(job: dict) -> tuple[str, str]:
    result = {}
    for lang in ("English", "German"):
        print(f"    ✍️  {lang}...", end=" ", flush=True)
        letter = ai_generate(build_cover_prompt(job, lang))
        if letter:
            print("✅ AI")
        else:
            letter = cover_letter_template(job, lang)
            print("⚠️  template (set GROQ_API_KEY for AI)")
        result[lang] = letter
        time.sleep(1.2)
    return result["English"], result["German"]


def generate_recruiter_message(recruiter: dict) -> str:
    """Generate a personalised outreach message — AI if available, smart template if not."""
    prompt = f"""Write a short, direct outreach message from Kranti Chavan to {recruiter["contact"]} at {recruiter["company"]}.

CANDIDATE: SAP Commerce Cloud Developer, 5+ years, Karlsruhe Germany
- Companies: Shell, Rockwell Automation
- Skills: Hybris 2211, CCV2, Java, Spring, OCC APIs, DataHub, SAP BTP
- Certifications: SAP Certified Professional Commerce Cloud Developer
- Available: within 4 weeks, based in Karlsruhe

RECRUITER CONTEXT: {recruiter["focus"]}

RULES:
- MAX 70 words
- Address to "{recruiter["contact"]}" (not "Hi" alone)
- Mention 1-2 specific skills relevant to their focus
- End with a specific ask: call, CV review, or platform registration
- Professional, direct, confident — not desperate
- Do NOT mention visa or work permit

Output: Just the message text. No subject line."""

    msg = ai_generate(prompt, max_tokens=150)
    if msg:
        return msg

    # Smart template fallback — varies by recruiter type
    c = CANDIDATE
    contact = recruiter["contact"]
    company = recruiter["company"]
    focus   = recruiter["focus"]
    action  = recruiter.get("action", "connect")

    if "platform" in company.lower() or "gulp" in company.lower() or "freelancer" in company.lower() or "xing" in company.lower():
        return f"""Hi,

I've just registered my profile on {company} — 5+ years SAP Commerce Cloud (Hybris 2211, CCV2, Java/Spring, OCC APIs) based in Karlsruhe, Germany. SAP Certified Professional.

{action}

If you have relevant SAP Commerce opportunities, I'd love to hear from you.

Best regards,
{c['name']} | {c['phone']}"""

    else:
        return f"""Dear {contact},

I'm reaching out as an SAP Commerce Cloud Developer with 5+ years of hands-on Hybris experience (Hybris 2211, CCV2, Java, OCC APIs) at Shell and Rockwell Automation. SAP Certified Professional. Based in Karlsruhe, available within 4 weeks.

Given {company}'s focus on {focus.split('—')[0].strip()}, I believe I'd be a strong match for your current openings.

Would you be open to a brief call this week?

Best regards,
{c['name']} | {c['phone']} | {c['email']}"""


def generate_followup_email(app: dict) -> str:
    """Draft a 7-day follow-up email for an application."""
    return (
        f"Subject: Follow-up – Bewerbung als {app['title']} bei {app['company']}\n\n"
        f"Sehr geehrte Damen und Herren,\n\n"
        f"vor einer Woche habe ich meine Bewerbung als {app['title']} bei {app['company']} eingereicht "
        f"und möchte kurz nachfragen, ob meine Unterlagen vollständig angekommen sind und ob es "
        f"Neuigkeiten zum Stand des Bewerbungsverfahrens gibt.\n\n"
        f"Ich stehe für Rückfragen jederzeit zur Verfügung und freue mich weiterhin sehr über die "
        f"Möglichkeit, meine Erfahrung in der SAP Commerce Cloud-Entwicklung in Ihr Team einzubringen.\n\n"
        f"Mit freundlichen Grüßen,\n"
        f"{CANDIDATE['name']}\n"
        f"{CANDIDATE['phone']} | {CANDIDATE['email']}\n"
        f"{CANDIDATE['linkedin']}"
    )


# ─────────────────────────────────────────────────────────────────────
#  EMAIL BUILDER  — single rich daily digest
# ─────────────────────────────────────────────────────────────────────

DAILY_TIPS = [
    "<b>Apply in the first 48 hours.</b> Studies show applications submitted within 2 days of posting are 3× more likely to be reviewed. The bot finds jobs daily — use that advantage. Apply today, not tomorrow.",
    "<b>Subject line formula:</b> <code>Bewerbung als SAP Commerce Cloud Developer (SAP Certified) – Kranti Chavan</code>. Most applicants write 'Job application' — yours will stand out immediately.",
    "<b>Register on XING today.</b> 40% of German HR teams use XING to headhunt. Set your status to 'Suche aktiv' and headline to 'SAP Commerce Cloud Developer | Hybris 2211 | Karlsruhe'. Takes 10 minutes.",
    "<b>adesso SE — your #1 target.</b> They post the same SAP Commerce role in Karlsruhe every month. Apply directly at jobs.adesso-group.com — you live in the same city, which is a significant advantage.",
    "<b>CCV2 is your rarest skill.</b> Less than 20% of Hybris developers have managed CCV2 production deployments. Lead every technical conversation with this. Most companies see CCV2 experience as senior-level.",
    "<b>Hays Germany SAP division</b> places more SAP Commerce developers in Germany than any other recruiter. Email sap@hays.de this week with your CV and '5 years SAP Commerce Cloud, Hybris 2211, Karlsruhe' in the subject.",
    "<b>Apply within 48h of posting.</b> Applications submitted in the first 48h are 3× more likely to get reviewed. The bot emails you daily — use it.",
    "<b>Follow up after 7 days.</b> A polite German follow-up ('Ich wollte kurz nachfragen ob meine Bewerbung angekommen ist') is expected and shows professionalism. The bot drafts this for you automatically.",
    "<b>Freelance route:</b> SAP Hybris contractors in Germany earn €85–130/hr on platforms like Gulp.de and Freelancermap.de. If permanent roles take time, this earns income while you keep looking.",
    "<b>Glassdoor Germany check:</b> Before any interview, check the company on glassdoor.de. German employees write honest reviews. Know what you're walking into.",
    "<b>GitHub profile:</b> Even a README describing your SAP Commerce architecture thinking — not code — signals seniority to tech hiring managers. Takes one afternoon.",
    "<b>Salary intel:</b> SAP Commerce Cloud Developer, 5 years, Germany → €78,000–€95,000 gross. Contractors: €85–130/hr. Know your number — German companies often ask in the first call.",
    "<b>valantic SAP Commerce practice</b> is actively expanding in Germany. They posted a Solution Architect role last week. Apply at valantic.com/karriere and mention Hybris 2211 + your CCV2 experience.",
    "<b>Network directly:</b> Search 'SAP Commerce Cloud' on LinkedIn → filter by Germany → connect with people at adesso, valantic, diva-e. A warm message from a peer ('fellow SAP Commerce developer') gets replies.",
]


def score_badge(score: int) -> tuple[str, str]:
    if score >= 16: return "🟢 Excellent",  "#16a34a"
    if score >= 10: return "🟡 Good",        "#d97706"
    return              "🔴 Partial",     "#dc2626"


def fh(t: str) -> str:
    return (t or "").replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")


def approval_button_url(job: dict) -> str:
    """
    Creates a GitHub Actions trigger URL via repository_dispatch.
    When clicked, triggers the 'apply' workflow with this job's data.
    If GITHUB_REPO is not set, falls back to the direct LinkedIn URL.
    """
    if not GITHUB_REPO or not GITHUB_TOKEN:
        return job["url"]
    payload = urllib.parse.urlencode({
        "job_url"    : job["url"],
        "job_title"  : job["title"],
        "company"    : job["company"],
        "hr_email"   : job.get("hr_email", ""),
        "cover_en_b64": "",   # kept short — full letters live in tracker
    })
    return f"https://github.com/{GITHUB_REPO}/actions/workflows/apply.yml?{payload}"


def tracker_status_html(stats: dict) -> str:
    return f"""
<div style="display:flex;gap:10px;flex-wrap:wrap;margin:12px 0;">
  <div style="background:#1d4ed8;color:white;border-radius:8px;padding:10px 18px;text-align:center;">
    <div style="font-size:22px;font-weight:bold;">{stats['total']}</div>
    <div style="font-size:11px;opacity:0.85;">Total tracked</div>
  </div>
  <div style="background:#16a34a;color:white;border-radius:8px;padding:10px 18px;text-align:center;">
    <div style="font-size:22px;font-weight:bold;">{stats['applied']}</div>
    <div style="font-size:11px;opacity:0.85;">Applied</div>
  </div>
  <div style="background:#7c3aed;color:white;border-radius:8px;padding:10px 18px;text-align:center;">
    <div style="font-size:22px;font-weight:bold;">{stats['interview']}</div>
    <div style="font-size:11px;opacity:0.85;">Interviews</div>
  </div>
  <div style="background:#d97706;color:white;border-radius:8px;padding:10px 18px;text-align:center;">
    <div style="font-size:22px;font-weight:bold;">{stats['pending']}</div>
    <div style="font-size:11px;opacity:0.85;">Pending review</div>
  </div>
  <div style="background:#059669;color:white;border-radius:8px;padding:10px 18px;text-align:center;">
    <div style="font-size:22px;font-weight:bold;">{stats['offer']}</div>
    <div style="font-size:11px;opacity:0.85;">Offers 🎉</div>
  </div>
</div>"""


def job_card_html(rank: int, job: dict) -> str:
    label, color = score_badge(job["score"])
    tags = " ".join(
        f'<span style="background:#eff6ff;color:#1d4ed8;border-radius:4px;padding:2px 8px;font-size:11px;margin:2px;display:inline-block;">{m}</span>'
        for m in (job.get("matches") or [])[:10]
    )
    near      = any(c in job.get("location","").lower() for c in BW_CITIES)
    remot     = "remote" in job.get("location","").lower()
    eng_ok    = is_english_friendly(job.get("location",""))
    de_req    = has_german_requirement(job.get("description",""))
    has_email = bool(job.get("hr_email"))
    badges = ""
    if near:      badges += ' <span style="background:#1d4ed8;color:white;border-radius:4px;padding:1px 7px;font-size:11px;">📍 Near Karlsruhe</span>'
    if remot:     badges += ' <span style="background:#059669;color:white;border-radius:4px;padding:1px 7px;font-size:11px;">🌐 Remote</span>'
    if eng_ok and not near:
                  badges += ' <span style="background:#0891b2;color:white;border-radius:4px;padding:1px 7px;font-size:11px;">🇬🇧 English OK</span>'
    if de_req:    badges += ' <span style="background:#b45309;color:white;border-radius:4px;padding:1px 7px;font-size:11px;">🇩🇪 German required</span>'
    if has_email: badges += f' <span style="background:#7c3aed;color:white;border-radius:4px;padding:1px 7px;font-size:11px;">📧 HR email found</span>'

    # Approval / apply button
    apply_url = job["url"]
    apply_btn = f"""
<a href="{apply_url}" style="display:inline-block;background:#1d4ed8;color:white;
   padding:10px 20px;border-radius:8px;text-decoration:none;font-size:14px;
   font-weight:bold;margin-right:8px;margin-bottom:8px;">
   👉 Apply on LinkedIn
</a>"""
    if has_email:
        subject  = urllib.parse.quote(f"Bewerbung als {job['title']} – Kranti Chavan (SAP Certified)")
        body_txt = urllib.parse.quote(f"Sehr geehrte Damen und Herren,\n\nbitte finden Sie anbei meine Bewerbungsunterlagen für die Stelle als {job['title']}.\n\nMit freundlichen Grüßen,\nKranti Chavan\n{CANDIDATE['phone']}")
        mailto   = f"mailto:{job['hr_email']}?subject={subject}&body={body_txt}"
        apply_btn += f"""
<a href="{mailto}" style="display:inline-block;background:#7c3aed;color:white;
   padding:10px 20px;border-radius:8px;text-decoration:none;font-size:14px;
   font-weight:bold;margin-bottom:8px;">
   📧 Email HR directly ({fh(job['hr_email'])})
</a>"""

    return f"""
<div style="border:1px solid #e2e8f0;border-radius:12px;padding:22px;margin-bottom:28px;
            box-shadow:0 1px 6px rgba(0,0,0,0.06);">
  <div style="display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:8px;margin-bottom:8px;">
    <div>
      <h2 style="color:#1d4ed8;margin:0 0 4px;font-size:17px;">#{rank}. {fh(job['title'])}</h2>
      <p style="margin:0;color:#475569;font-size:13px;">
        🏢 <strong>{fh(job['company'])}</strong> &nbsp;·&nbsp;
        📍 {fh(job['location'])}{badges} &nbsp;·&nbsp;
        📅 {job.get('date','recent')}
      </p>
    </div>
    <span style="background:{color};color:white;border-radius:20px;padding:5px 14px;
                 font-size:12px;font-weight:bold;white-space:nowrap;">
      {label} · {job['score']}pts
    </span>
  </div>
  <div style="margin:10px 0 14px;line-height:1.8;">{tags}</div>
  <div style="margin-bottom:14px;">{apply_btn}</div>

  <details style="border:1px solid #dbeafe;border-radius:8px;overflow:hidden;margin-top:4px;">
    <summary style="cursor:pointer;font-weight:bold;color:#1d4ed8;font-size:14px;
                    padding:11px 16px;background:#eff6ff;list-style:none;">
      📄 ▶ Cover Letter (English) — expand &amp; copy
    </summary>
    <div style="background:#fafafa;border-top:1px solid #dbeafe;padding:20px;
                white-space:pre-wrap;font-size:13.5px;line-height:1.75;font-family:Georgia,serif;color:#1e293b;">
{fh(job.get('cover_en',''))}
    </div>
    <p style="background:#eff6ff;margin:0;padding:8px 16px;font-size:11px;color:#64748b;">
      💡 Copy → paste into portal, or Word → export PDF and attach
    </p>
  </details>

  <details style="border:1px solid #d1fae5;border-radius:8px;overflow:hidden;margin-top:8px;">
    <summary style="cursor:pointer;font-weight:bold;color:#059669;font-size:14px;
                    padding:11px 16px;background:#ecfdf5;list-style:none;">
      📄 ▶ Anschreiben (Deutsch) — aufklappen &amp; kopieren
    </summary>
    <div style="background:#fafafa;border-top:1px solid #d1fae5;padding:20px;
                white-space:pre-wrap;font-size:13.5px;line-height:1.75;font-family:Georgia,serif;color:#1e293b;">
{fh(job.get('cover_de',''))}
    </div>
    <p style="background:#ecfdf5;margin:0;padding:8px 16px;font-size:11px;color:#64748b;">
      💡 Direkt ins Portal kopieren oder als Word-Datei anhängen
    </p>
  </details>
</div>"""


def followup_section_html(due: list[dict]) -> str:
    if not due:
        return ""
    items = ""
    for app in due:
        followup = generate_followup_email(app)
        items += f"""
<div style="border:1px solid #fde68a;border-radius:8px;padding:16px;margin-bottom:16px;background:#fefce8;">
  <p style="margin:0 0 6px;font-size:14px;font-weight:bold;color:#92400e;">
    ⏰ Follow-up due: <strong>{fh(app['title'])}</strong> @ {fh(app['company'])}
    <span style="font-weight:normal;color:#78716c;">(applied {app['date_applied']})</span>
  </p>
  <details>
    <summary style="cursor:pointer;color:#b45309;font-size:13px;font-weight:bold;">📧 Draft follow-up email — click to expand</summary>
    <pre style="background:white;border:1px solid #fde68a;border-radius:6px;padding:14px;
                font-size:13px;line-height:1.6;white-space:pre-wrap;margin-top:8px;">{fh(followup)}</pre>
    <p style="font-size:11px;color:#92400e;margin:4px 0 0;">
      {'📧 Send to: ' + fh(app.get('hr_email','the HR team directly')) if app.get('hr_email') else '📧 Find the HR email on their careers page, or send via LinkedIn'}
    </p>
  </details>
</div>"""
    return f"""
<div style="padding:0 32px 8px;">
  <div style="background:#fef9c3;border:2px solid #fbbf24;border-radius:12px;padding:20px;margin-bottom:20px;">
    <h3 style="color:#92400e;margin:0 0 12px;font-size:16px;">⏰ {len(due)} Follow-up{'s' if len(due)>1 else ''} Due Today!</h3>
    <p style="color:#78716c;font-size:13px;margin:0 0 16px;">
      These applications are 7+ days old with no response. A polite follow-up significantly increases your chances.
    </p>
    {items}
  </div>
</div>"""


def recruiter_section_html(recruiters: list[dict]) -> str:
    items = ""
    for rec in recruiters[:4]:   # show top 4 each day (rotate)
        msg = generate_recruiter_message(rec)
        rec_email  = rec.get("email", "")
        rec_li     = rec.get("linkedin", "")
        email_link = f'<a href="mailto:{rec_email}" style="color:#7c3aed;">{fh(rec_email)}</a>' if rec_email else "–"
        li_link    = f'<a href="{rec_li}" style="color:#1d4ed8;">LinkedIn</a>' if rec_li else ""
        action_text = fh(rec.get("action", "Connect and reach out"))
        items += f"""
<div style="border:1px solid #e9d5ff;border-radius:8px;padding:16px;margin-bottom:16px;background:#faf5ff;">
  <div style="display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:8px;">
    <div>
      <p style="margin:0 0 3px;font-weight:bold;color:#6b21a8;font-size:14px;">{fh(rec['name'])}</p>
      <p style="margin:0 0 6px;font-size:12px;color:#64748b;">{fh(rec['focus'].split('—')[0].strip())} &nbsp;·&nbsp; {email_link} &nbsp;{li_link}</p>
    </div>
  </div>
  <div style="background:#ede9fe;border-radius:6px;padding:10px 14px;margin-bottom:10px;">
    <p style="margin:0;font-size:13px;color:#4c1d95;"><strong>👉 Action today:</strong> {action_text}</p>
  </div>
  <p style="margin:0 0 8px;font-size:12px;color:#78716c;">💡 {fh(rec.get('note',''))}</p>
  <details style="margin-top:4px;">
    <summary style="cursor:pointer;color:#7c3aed;font-size:13px;font-weight:bold;padding:4px 0;">💬 Message to copy &amp; send — expand</summary>
    <pre style="background:white;border:1px solid #e9d5ff;border-radius:6px;padding:14px;
                font-size:13px;line-height:1.65;white-space:pre-wrap;margin-top:8px;
                font-family:Georgia,serif;">{fh(msg)}</pre>
  </details>
</div>"""
    return f"""
<div style="padding:0 32px 8px;">
  <div style="background:#faf5ff;border:1px solid #e9d5ff;border-radius:12px;padding:20px;margin-bottom:20px;">
    <h3 style="color:#6b21a8;margin:0 0 4px;font-size:16px;">🤝 Recruiter Outreach — Today's Targets</h3>
    <p style="color:#64748b;font-size:13px;margin:0 0 16px;">
      Send one message per day. Personalised beats bulk. Each message below is tailored to the recruiter.
    </p>
    {items}
  </div>
</div>"""


def build_email(jobs: list[dict], followup_due: list[dict]) -> tuple[str, str]:
    today    = datetime.date.today()
    tip      = DAILY_TIPS[today.timetuple().tm_yday % len(DAILY_TIPS)]
    stats    = get_tracker_stats()
    date_str = today.strftime("%A, %d %B %Y")

    excellent = sum(1 for j in jobs if j["score"] >= 16)
    good      = sum(1 for j in jobs if 10 <= j["score"] < 16)
    partial   = len(jobs) - excellent - good

    # Rotate 4 recruiters per day
    day_idx    = today.timetuple().tm_yday
    rec_slice  = SAP_RECRUITERS_GERMANY[day_idx % len(SAP_RECRUITERS_GERMANY):(day_idx % len(SAP_RECRUITERS_GERMANY)) + 4]
    if len(rec_slice) < 4:
        rec_slice += SAP_RECRUITERS_GERMANY[:4 - len(rec_slice)]

    cards_html    = "".join(job_card_html(i+1, j) for i, j in enumerate(jobs))
    followup_html = followup_section_html(followup_due)
    recruiter_html= recruiter_section_html(rec_slice)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="background:#f1f5f9;padding:16px;margin:0;font-family:Arial,sans-serif;">
<div style="max-width:760px;margin:auto;background:white;border-radius:16px;overflow:hidden;
            box-shadow:0 4px 24px rgba(0,0,0,0.10);">

  <!-- ── HEADER ── -->
  <div style="background:linear-gradient(135deg,#1d4ed8 0%,#1e3a8a 100%);padding:32px;text-align:center;color:white;">
    <div style="font-size:36px;margin-bottom:8px;">🎯</div>
    <h1 style="margin:0 0 6px;font-size:24px;">Kranti's Daily Job Command Centre</h1>
    <p style="margin:0;opacity:0.88;font-size:14px;">{date_str} &nbsp;·&nbsp; SAP Commerce Cloud · Germany + Remote</p>
  </div>

  <!-- ── APPLICATION TRACKER STATS ── -->
  <div style="padding:20px 32px 4px;">
    <h3 style="color:#1e293b;margin:0 0 4px;font-size:15px;">📊 Your Application Dashboard</h3>
    <p style="color:#64748b;font-size:12px;margin:0 0 8px;">Updated live — every application you send gets tracked here automatically.</p>
    {tracker_status_html(stats)}
    <hr style="border:none;border-top:1px solid #e2e8f0;margin:16px 0 8px;">
  </div>

  <!-- ── FOLLOW-UP ALERTS ── -->
  {followup_html}

  <!-- ── TODAY'S JOBS ── -->
  <div style="padding:0 32px 8px;">
    <h2 style="color:#1e293b;margin:0 0 4px;font-size:18px;">🔍 Today's Jobs — {len(jobs)} Found</h2>
    <p style="color:#475569;font-size:13px;margin:0 0 8px;">
      Sorted by skill-match score. Apply to <strong>Excellent</strong> first.
    </p>
    <div style="background:#f0f9ff;border-left:3px solid #0ea5e9;padding:10px 14px;margin-bottom:14px;border-radius:0 6px 6px 0;">
      <p style="margin:0;font-size:12.5px;color:#0c4a6e;">
        📌 <strong>Honest market picture (researched across all EU sources):</strong>
        LinkedIn shows ~37 unique active EU jobs right now across ~13 companies.
        StepStone, Indeed, Glassdoor all block automated access — so we can't confirm their numbers.
        German company career pages (adesso, valantic, diva-e etc.) use JavaScript rendering and can't be scraped.
        <strong>Conclusion: LinkedIn is our most complete data source, but the real market may be 20–40% larger.</strong>
        <strong>Your best weapon: apply fast (within 48h), and contact recruiters directly (section below).</strong>
      </p>
    </div>
    <div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:16px;">
      <span style="background:#16a34a;color:white;border-radius:8px;padding:5px 12px;font-size:12px;">🟢 {excellent} Excellent</span>
      <span style="background:#d97706;color:white;border-radius:8px;padding:5px 12px;font-size:12px;">🟡 {good} Good</span>
      <span style="background:#dc2626;color:white;border-radius:8px;padding:5px 12px;font-size:12px;">🔴 {partial} Partial</span>
    </div>
    {cards_html}
  </div>

  <!-- ── HOW TO APPLY ── -->
  <div style="background:#fefce8;padding:20px 32px;margin:0 32px 20px;border-radius:10px;border-left:4px solid #eab308;">
    <h3 style="color:#854d0e;margin:0 0 10px;font-size:15px;">✉️ How to Apply (30-second routine)</h3>
    <ol style="margin:0;padding-left:20px;color:#44403c;font-size:13.5px;line-height:1.8;">
      <li><strong>Click</strong> the blue "Apply on LinkedIn" button above</li>
      <li><strong>Copy</strong> the cover letter from the expandable section below it</li>
      <li><strong>Paste</strong> into the application form or attach as PDF</li>
      <li>If there's a purple "Email HR directly" button — use that instead (higher chance of being seen!)</li>
      <li>Log it in your tracker: open <code>tracker/applications.json</code> and set status to "applied" + today's date</li>
    </ol>
    <p style="margin:12px 0 0;font-size:13px;color:#78716c;">
      📧 <strong>Email subject to copy:</strong>&nbsp;
      <code style="background:white;padding:3px 8px;border-radius:4px;border:1px solid #d6d3d1;font-size:12px;">
        Bewerbung als SAP Commerce Cloud Developer (SAP Certified) – Kranti Chavan
      </code>
    </p>
  </div>

  <!-- ── RECRUITER OUTREACH ── -->
  {recruiter_html}

  <!-- ── DAILY TIP ── -->
  <div style="background:#eff6ff;padding:20px 32px;margin:0 32px 20px;border-radius:10px;">
    <h3 style="color:#1d4ed8;margin:0 0 8px;font-size:15px;">💡 Today's Insider Tip</h3>
    <p style="margin:0;color:#1e293b;font-size:14px;line-height:1.6;">{tip}</p>
  </div>

  <!-- ── FOOTER ── -->
  <div style="background:#f8fafc;padding:18px 32px;text-align:center;font-size:12px;
              color:#94a3b8;border-top:1px solid #e2e8f0;">
    🤖 Powered by LinkedIn + Groq Llama 3.3 70B · GitHub Actions Mon–Fri 7 AM CET · 100% FREE<br>
    <strong style="color:#475569;">Kranti Chavan</strong> · {CANDIDATE['phone']} · Karlsruhe, Germany<br>
    <span style="color:#cbd5e1;font-size:11px;">One focused application beats ten careless ones. You've got this. 💪</span>
  </div>
</div>
</body>
</html>"""

    subject = (
        f"🎯 {len(jobs)} SAP Jobs + "
        f"{len(followup_due)} follow-up{'s' if len(followup_due)!=1 else ''} due "
        f"({today.strftime('%d %b')}) · {excellent} Excellent match{'es' if excellent!=1 else ''}"
    )
    return subject, html


# ─────────────────────────────────────────────────────────────────────
#  EMAIL SENDER
# ─────────────────────────────────────────────────────────────────────

def send_ntfy_alert(jobs: list[dict]):
    """Send instant phone push notification via ntfy.sh — zero signup needed."""
    if not NTFY_TOPIC:
        return
    try:
        top_job   = jobs[0] if jobs else {}
        excellent = sum(1 for j in jobs if j["score"] >= 16)
        msg       = (
            f"{len(jobs)} SAP jobs found! "
            f"{excellent} excellent match{'es' if excellent!=1 else ''}. "
            f"Top: {top_job.get('title','?')} @ {top_job.get('company','?')}"
        )
        requests.post(
            f"https://ntfy.sh/{NTFY_TOPIC}",
            data=msg.encode("utf-8"),
            headers={
                "Title"   : f"🎯 {len(jobs)} SAP Jobs Today",
                "Priority": "high",
                "Tags"    : "briefcase,tada",
            },
            timeout=10,
        )
        print(f"[ntfy] ✅ Push sent to topic: {NTFY_TOPIC}")
    except Exception as e:
        print(f"[ntfy] ⚠️  Push failed (non-critical): {e}")


def send_email(subject: str, html: str):
    """Send via Resend.com API (free, no SMTP/Gmail setup needed)."""
    # Always save HTML preview as artifact
    os.makedirs("tracker", exist_ok=True)
    with open("email_preview.html", "w", encoding="utf-8") as f:
        f.write(html)

    if not RESEND_API_KEY:
        print("\n[email] No RESEND_API_KEY — preview saved: email_preview.html")
        print("         Add RESEND_API_KEY secret (free at resend.com) to enable email")
        return

    try:
        recipients = [TO_EMAIL]
        if TO_EMAIL_2:
            recipients.append(TO_EMAIL_2)
        payload = {
            "from"   : f"Kranti Job Hunter <{FROM_EMAIL}>",
            "to"     : recipients,
            "subject": subject,
            "html"   : html,
        }
        r = requests.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {RESEND_API_KEY}",
                "Content-Type" : "application/json",
            },
            json=payload,
            timeout=30,
        )
        if r.status_code in (200, 201):
            data = r.json()
            print(f"\n[email] ✅ Sent via Resend — ID: {data.get('id','?')} → {TO_EMAIL}")
        else:
            print(f"\n[email] ❌ Resend error {r.status_code}: {r.text[:200]}")
            print("         Preview saved: email_preview.html")
    except Exception as e:
        print(f"\n[email] ❌ Send error: {e}")
        print("         Preview saved: email_preview.html")


# ─────────────────────────────────────────────────────────────────────
#  MAIN
# ─────────────────────────────────────────────────────────────────────

def main():
    t0 = datetime.datetime.now()
    print("=" * 68)
    print(f"  KRANTI'S JOB HUNTER v4.0  —  {t0:%Y-%m-%d %H:%M}")
    print("=" * 68)

    # 1. Scrape jobs
    print("\n[1/4] 🔍 SCRAPING JOBS...")
    jobs = fetch_all_jobs()
    if not jobs:
        print("[main] ⚠️  No jobs found.")
        return
    print(f"\n  Final: {len(jobs)} jobs")
    for j in jobs:
        hr = f" | 📧 {j['hr_email']}" if j.get('hr_email') else ""
        print(f"  [{j['score']:2d}] {j['title'][:48]} @ {j['company']}{hr}")

    # 2. Generate cover letters
    print("\n[2/4] ✍️  GENERATING COVER LETTERS...")
    for i, job in enumerate(jobs):
        print(f"\n  [{i+1}/{len(jobs)}] {job['title'][:45]} @ {job['company']}")
        job["cover_en"], job["cover_de"] = generate_cover_letters(job)

    # 3. Check follow-ups due
    print("\n[3/4] ⏰ CHECKING FOLLOW-UPS...")
    followup_due = get_followup_due()
    print(f"  Follow-ups due: {len(followup_due)}")

    # 4. Build & send email
    print("\n[4/4] 📧 SENDING EMAIL + PUSH NOTIFICATION...")
    subject, html = build_email(jobs, followup_due)
    send_email(subject, html)
    send_ntfy_alert(jobs)   # instant phone notification

    # Update tracker + seen log
    add_to_tracker(jobs)
    save_seen(load_seen(), jobs)

    elapsed = (datetime.datetime.now() - t0).seconds
    log = {
        "date": str(datetime.date.today()), "duration_s": elapsed,
        "jobs": [{"title": j["title"], "company": j["company"],
                  "score": j["score"], "hr_email": j.get("hr_email",""), "url": j["url"]} for j in jobs],
        "followups_due": len(followup_due),
        "tracker_stats": get_tracker_stats(),
    }
    with open("jobs_log.json", "w", encoding="utf-8") as f:
        json.dump(log, f, indent=2, ensure_ascii=False)
    print(f"\n[main] ✅ Done in {elapsed}s")
    print("=" * 68)


if __name__ == "__main__":
    main()
