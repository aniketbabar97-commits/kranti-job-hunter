"""Read verification codes / links that job portals mail to her Gmail (Workday, SuccessFactors, ...).

Uses the same Gmail IMAP credentials as hunter/outreach.py (CANDIDATE_EMAIL + KRANTI_GMAIL_APP_PASSWORD).

    from helper import mailcodes
    t0 = time.time()
    code = mailcodes.wait_for_code("workday", since_ts=t0)                   # '483920' or None
    url = mailcodes.wait_for_link("successfactors", r"verify|activate|reset", since_ts=t0)
"""
import email
import html as htmlmod
import imaplib
import quopri
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from email.header import decode_header, make_header
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

CODE_WORDS = re.compile(r"(verification|verify|security|confirmation|one.?time|access|login|sign.?in|auth\w*|"
                        r"bestätigungs|verifizierungs|sicherheits|einmal|otp|pin|passcode)\w*\s*(code|key|pin|number)?",
                        re.I)
CODE_RE = re.compile(r"(?<![\d\w-])(\d{4,8})(?![\d\w-])")
CODE_NEAR = re.compile(r"(?:code|pin|passcode|otp|key|schlüssel)\W{0,40}?(?:is|ist|lautet|:)?\W{0,10}?(\d{4,8})\b|"
                       r"\b(\d{4,8})\W{0,10}?(?:is your|ist (?:ihr|dein)|as your)", re.I)
URL_RE = re.compile(r"https?://[^\s<>\"'\]\)]+")
NOT_CODE = re.compile(r"(19|20)\d\d")  # years are not codes


def _credentials():
    from hunter.outreach import credentials
    user, pw = credentials()
    if not user:
        from helper.vault import _load_env
        _load_env()
        user, pw = credentials()
    return user, pw


def _text_of(msg):
    """Plain text + raw HTML (for links) of a parsed email message."""
    plain, html_parts = [], []
    for part in msg.walk():
        ct = part.get_content_type()
        if ct not in ("text/plain", "text/html"):
            continue
        try:
            body = part.get_payload(decode=True) or b""
            body = body.decode(part.get_content_charset() or "utf-8", errors="replace")
        except Exception:
            body = quopri.decodestring(part.get_payload() or "").decode("utf-8", errors="replace")
        (plain if ct == "text/plain" else html_parts).append(body)
    html = "\n".join(html_parts)
    text = "\n".join(plain)
    if not text and html:
        text = html_to_text(html)
    return text, html


def html_to_text(html):
    t = re.sub(r"(?is)<(script|style).*?</\1>", " ", html)
    t = re.sub(r"(?i)<br\s*/?>|</(p|div|tr|li|h\d|td)>", "\n", t)
    t = re.sub(r"<[^>]+>", " ", t)
    return htmlmod.unescape(t)


def extract_code(text):
    """4-8 digit verification code from an email body, or None."""
    t = htmlmod.unescape(text)
    for m in CODE_NEAR.finditer(t):
        c = m.group(1) or m.group(2)
        if c and not NOT_CODE.fullmatch(c):
            return c
    # 'Your verification code' ... (anywhere within the next ~120 chars)
    for m in CODE_WORDS.finditer(t):
        window = t[m.end():m.end() + 160]
        for c in CODE_RE.findall(window):
            if not NOT_CODE.fullmatch(c):
                return c
    # fallback: a line that is only a code
    for line in t.splitlines():
        s = line.strip().strip("*").strip()
        if re.fullmatch(r"\d{4,8}", s) and not NOT_CODE.fullmatch(s):
            return s
    return None


def extract_links(text, html=""):
    """All URLs (href= first, then bare URLs), de-duplicated, HTML entities decoded, trailing punctuation removed."""
    urls = []
    for m in re.finditer(r"""href\s*=\s*["']([^"']+)["']""", html or "", re.I):
        urls.append(m.group(1))
    urls += URL_RE.findall(html or "") + URL_RE.findall(text or "")
    out = []
    for u in urls:
        u = htmlmod.unescape(u).rstrip(".,;:!?)>]")
        if u.startswith("http") and u not in out:
            out.append(u)
    return out


def extract_link(text, html="", pattern=r"verify|verif|activat|confirm|reset|password|bestätig|aktivier"):
    rx = re.compile(pattern, re.I)
    for u in extract_links(text, html):
        if rx.search(u) and not re.search(r"unsubscribe|abmelden|privacy|datenschutz|facebook|twitter|linkedin\.com|"
                                          r"instagram|youtube|apple\.com|play\.google", u, re.I):
            return u
    return None


def _subject(msg):
    try:
        return str(make_header(decode_header(msg.get("Subject", ""))))
    except Exception:
        return msg.get("Subject", "")


def _matches(msg, sender_hint):
    if not sender_hint:
        return True
    hint = sender_hint.lower()
    hay = " ".join([msg.get("From", ""), msg.get("Reply-To", ""), msg.get("Return-Path", ""),
                    _subject(msg), msg.get("List-Unsubscribe", "")]).lower()
    return hint in hay


def _received_ts(msg):
    try:
        d = email.utils.parsedate_to_datetime(msg.get("Date"))
        if d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        return d.timestamp()
    except Exception:
        return time.time()


def _candidates(imap, since_ts, folder):
    imap.select(folder, readonly=True)
    day = (datetime.fromtimestamp(since_ts, timezone.utc) - timedelta(days=1)).strftime("%d-%b-%Y")
    typ, data = imap.search(None, f'(SINCE "{day}")')
    ids = (data[0].split() if typ == "OK" and data and data[0] else [])[-40:]
    for uid in reversed(ids):  # newest first
        typ, parts = imap.fetch(uid, "(RFC822)")
        if typ != "OK" or not parts or not isinstance(parts[0], tuple):
            continue
        msg = email.message_from_bytes(parts[0][1])
        if _received_ts(msg) >= since_ts - 120:  # 2 min clock slack
            yield msg


def _poll(sender_hint, since_ts, timeout, pick, folders=("INBOX", "[Gmail]/Spam")):
    user, pw = _credentials()
    if not user:  # no crash: the adapter parks the job instead
        print("   mailcodes: Gmail IMAP not configured (CANDIDATE_EMAIL + KRANTI_GMAIL_APP_PASSWORD in helper/me.env)")
        return None
    deadline = time.time() + timeout
    while True:
        imap = None
        try:
            imap = imaplib.IMAP4_SSL("imap.gmail.com")
            imap.login(user, pw)
            for folder in folders:
                try:
                    for msg in _candidates(imap, since_ts, folder):
                        if _matches(msg, sender_hint):
                            text, html = _text_of(msg)
                            found = pick(text, html, msg)
                            if found:
                                return found
                except imaplib.IMAP4.error:
                    continue
        finally:
            if imap is not None:
                try:
                    imap.logout()
                except Exception:
                    pass
        if time.time() >= deadline:
            return None
        time.sleep(min(8, max(1, deadline - time.time())))


def wait_for_code(sender_hint, since_ts, timeout=120):
    """Poll Gmail for a mail from `sender_hint` (substring of From/Subject, e.g. 'workday') received after
    `since_ts` (time.time() before the click) and return its 4-8 digit code, or None after `timeout` s."""
    return _poll(sender_hint, since_ts, timeout, lambda t, h, m: extract_code(t) or extract_code(_subject(m)))


def wait_for_link(sender_hint, pattern=r"verify|verif|activat|confirm|reset|password|bestätig|aktivier",
                  since_ts=None, timeout=120):
    """Like wait_for_code, but returns the first URL in the mail whose address matches `pattern`."""
    since_ts = since_ts if since_ts is not None else time.time() - 600
    return _poll(sender_hint, since_ts, timeout, lambda t, h, m: extract_link(t, h, pattern))


def wait_for_mail(sender_hint, since_ts, timeout=120):
    """The whole (text, html) of the first matching mail, for anything the two helpers above cannot parse."""
    return _poll(sender_hint, since_ts, timeout, lambda t, h, m: (t, h))
