# Application helper for Windows

The helper opens each strong job in a normal Chrome window and fills in the application form. It enters your name,
email, phone, city, salary, start date, LinkedIn and a "why this company" text, and it uploads the tailored CV
and cover letter. **It never clicks Submit.** You check the form, tick the consent boxes and submit it yourself.
That way every application really arrives, because job sites block robots but not people.

Jobs with an application email address are not shown here; those are already in your Gmail Drafts.

## One-time setup (about 10 minutes)

1. **Python:** install it from https://www.python.org/downloads/ and tick **"Add python.exe to PATH"** in the
   installer.
2. **The project:** install **GitHub Desktop** (https://desktop.github.com), sign in, and clone
   `aniketbabar97-commits/kranti-job-hunter`. The project then updates itself with one click ("Fetch origin").
3. In the project folder, open `helper` and double-click **`setup.bat`**.
4. Open `helper\me.env` in Notepad and enter your phone and email. Save your photo as `profile\photo.jpg`.
   Both stay on this laptop only.

## Every day (about 2 minutes per job)

Double-click **`helper\start.bat`**. A Chrome window opens next to a black window that lists the jobs, best match first.

For each job:
1. The job page opens. If needed, click **Apply / Bewerben** there. If the site asks you to log in, log in once;
   Chrome remembers it next time.
2. In the black window, press **f** and Enter. The form fills itself, and the window lists what it filled (✓)
   and what you still need to fill (✗).
3. Fill in anything marked ✗, tick the consent boxes, check the form, then click **Submit**.
4. Press **a** and Enter. The job is logged in `APPLIED.md`, so the daily emails stop suggesting it, and the next
   job opens.

Other keys: **s** skips a job (closed or not interesting), **q** quits. If a page changes (multi-step forms),
press **f** again.
