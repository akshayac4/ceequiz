# ceequiz

Pre-test / post-test quiz system for CEE (Centre for Environment Education) workshops with
school teachers in Gujarat. Django 5 + PostgreSQL + Docker. Gujarati-first public pages,
English-only admin and reports.

Production: `https://ceequiz.thecadlabs.com`. Built and maintained by CAD Labs Technology LLP
for CEE. Admins: Akshay Chauhan and Uday Desai.

## Run it locally

Requires Docker Desktop.

```bash
cp .env.example .env
docker compose up -d
```

`docker-compose.override.yml` is picked up automatically in dev: it runs `manage.py runserver`
with `DEBUG=1`, mounts the source tree for live reload, and binds Postgres to
`127.0.0.1:5432` so you can connect a GUI client. The app is at http://localhost:8000.

> **Note:** On macOS, Docker Desktop's file-sharing layer occasionally misses a change to a
> template or static file (the dev server's autoreloader watches `.py` files reliably but can
> miss `.html`/`.css` edits). If an edit doesn't show up, run `docker compose restart web`.

Create the two admin accounts (never commit the passwords):

```bash
make createsuperuser
# run twice, once for akshay, once for uday
```

Seed Gujarat's districts and the first quiz (10 questions, correct answers intentionally left
blank — see below):

```bash
make seed
```

Then open http://localhost:8000/admin/, open the seeded quiz, tick the correct option for each
question (the pre-test can't be opened until every question has one), and use the **Open
pre-test** / **Close pre-test** / **Open post-test** / **Close quiz** buttons on the quiz page
to drive it through its lifecycle. The public link is `/q/<code>/`, shown on the quiz's admin
page.

Run tests:

```bash
make test
```

Other shortcuts: `make migrate`, `make makemigrations`, `make shell`, `make logs`,
`make collectstatic`. See `Makefile` for the full list.

## How it's built

- Django 5 (server-rendered templates + a small amount of vanilla JS for the countdown timer,
  autosave, and the post-test reveal/lock), PostgreSQL 16, gunicorn, WhiteNoise for static
  files, openpyxl for Excel import/export.
- Two apps: `quiz` (models, public flow, admin) and `reports` (staff-only dashboard).
- Fonts (Noto Sans Gujarati + Inter) and Chart.js are vendored under `static/` — no external
  CDNs are hit at runtime.
- `quiz/management/commands/`:
  - `seed_data` — Gujarat districts + the first workshop quiz with its 10 bilingual questions.
  - `autosubmit_expired` — auto-submits attempts past their deadline and auto-closes a quiz
    phase once `phase_closes_at` is reached. **Run this every minute via cron/systemd timer**
    on the VPS (see below); the app also does a lazy check on every page read, so a stray
    minute of lag never loses an in-progress attempt's answers.
  - `import_schools` — stub, not wired into the UI yet. Run by hand once CEE sends the School
    master list (`python manage.py import_schools path/to/file.xlsx`).

### Known gap: CEE logo

No CEE logo file was supplied with the "LOGO JPGS & PNGS" folder (it only contained CAD Labs
Technology LLP's own logo set, which is already in `static/brand/`). The header references
`static/brand/cee-logo.png`, which doesn't exist yet — it fails silently (the `<img>` has
`onerror` hiding it) so the page still looks fine, just without the CEE mark. Drop the real
file at that path and it will appear automatically; no code changes needed.

## Deployment (local → GitHub → VPS)

```bash
git remote add origin git@github.com:akshayac4/ceequiz.git
git push -u origin main
```

A push to `main` runs `.github/workflows/ci.yml`: install deps, `manage.py check`,
`manage.py test` (against a Postgres service container), build the Docker image, and — only if
all of that passes — SSH into the VPS and run `/opt/ceequiz/deploy.sh`.

**GitHub secrets required** (Settings → Secrets → Actions): `VPS_HOST`, `VPS_USER`,
`VPS_SSH_KEY` (a dedicated deploy key, not your personal one).

**One-time VPS setup** (do this by hand once, with Akshay):

1. Make sure Caddy is running on the shared `proxy` Docker network (see the "My VPS" project
   overview) — add the block in `deploy/Caddyfile.example` to it. DNS A record
   `ceequiz.thecadlabs.com → 187.127.140.198` is already set.
2. `git clone git@github.com:akshayac4/ceequiz.git /opt/ceequiz` using a **read-only** deploy
   key for this repo.
3. `cd /opt/ceequiz && cp .env.example .env` and fill in real values (`SECRET_KEY`,
   `POSTGRES_PASSWORD`, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`).
4. `docker compose up -d`, then `docker compose exec web python manage.py createsuperuser`
   (twice) and `docker compose exec web python manage.py seed_data`.
5. Add a cron entry to run the auto-submit/auto-close sweep every minute:
   ```
   * * * * * cd /opt/ceequiz && docker compose exec -T web python manage.py autosubmit_expired >> /var/log/ceequiz-cron.log 2>&1
   ```
6. Nightly backup cron (compressed `pg_dump`, keep 14 days):
   ```
   0 2 * * * cd /opt/ceequiz && docker compose exec -T db pg_dump -U "$(grep ^POSTGRES_USER .env|cut -d= -f2)" "$(grep ^POSTGRES_DB .env|cut -d= -f2)" | gzip > backups/nightly-$(date +\%Y\%m\%d).sql.gz && find backups -name 'nightly-*.sql.gz' -mtime +14 -delete
   ```
7. On the VPS's `~deploy/.ssh/authorized_keys`, restrict the GitHub Actions deploy key:
   ```
   command="/opt/ceequiz/deploy.sh",no-port-forwarding,no-agent-forwarding,no-pty ssh-ed25519 AAAA...
   ```

Every later change just needs `git push` to `main`.

### Rollback

```bash
# on the VPS
cd /opt/ceequiz
./deploy.sh <known-good-commit-sha>
```

or revert the bad commit on GitHub and push — that re-triggers the normal deploy. The
pre-deploy `pg_dump` backup (step in `deploy.sh`) is the safety net if a migration needs to be
undone by hand.

## Load test

```bash
pip install requests
python scripts/load_test.py --base-url https://ceequiz.thecadlabs.com --code <quiz_code> --concurrency 50
```

Open the quiz's pre-test first. Reports p95 latency and error count across 50 concurrent
simulated teachers (start → autosave each answer → submit).

## Security notes

- The correct option is never sent to the browser ahead of time: never during the pre-test,
  and during the post-test only in the response to that specific question's answer, after the
  server has locked it.
- `DEBUG=0`, secure cookies, HTTPS-only, and CSRF are all on by default outside local dev (see
  `config/settings.py`). `/admin/login/` is rate-limited via django-axes.
- Participant data (names, mobile numbers) is personal data — no public listing, no analytics
  trackers, and it's excluded from the repo via `.gitignore` (`backups/`, `*.sql*`, `media/`).
