# Moodle Course Loader

CLI to automate course loading into Moodle via the Web Services API.

Current phase: **1 — duplicate from template** (MOOC, SEMINAR, etc.).
Upcoming phases: section/module structure from scratch, file uploads, bulk enrolment.

## Install

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env   # fill in MOODLE_URL and MOODLE_TOKEN
```

For Google Sheets support, install the optional extra packages:

```bash
pip install -e ".[dev,sheets]"
```

## Usage

```bash
# Verify connection and token
moodle-loader info

# Load courses defined in a YAML file
moodle-loader load examples/courses.yaml

# Dry run without touching Moodle
moodle-loader load examples/courses.yaml --dry-run

# Load courses from a Google Sheet
moodle-loader load-sheets <spreadsheet_id>
moodle-loader load-sheets <spreadsheet_id> --worksheet "Hoja 1" --dry-run
```

## Plan ₿ videos

When importing a Plan ₿ course, two video syntaxes in the markdown are turned
into embedded players (a responsive 16:9 `<iframe>`):

- `:::video id=<UUID>:::` — resolved via the `videos:` block of `course.yml`,
  which maps each UUID to a YouTube and/or PeerTube id per language.
- `![desc](https://youtu.be/<id>)` or `![desc](https://www.youtube.com/watch?v=<id>)`
  — the YouTube id is taken straight from the URL.

YouTube is preferred over PeerTube when both exist. The importer is
English-only, so the `en` track is used; if a video has no `en` track the first
available track is embedded and a warning is logged. A video that can't be
resolved (unknown UUID, no tracks) is dropped with a warning — never left as
raw `:::video ...:::` text or a broken image.

> **Moodle requirement — allow the iframe sources.** Moodle's HTML purifier
> strips `<iframe>` unless the source domain is allow-listed. In the target
> Moodle, add `www.youtube.com` and `peertube.planb.network` under
> *Site administration → Security → HTTP security → Allowed iframe sources*.
> Without this the players are removed silently and the pages render empty
> where the videos should be.

## Google Sheets setup

Two authentication options are supported. Use whichever works in your environment.

---

### Option A — Application Default Credentials (recommended)

No key file needed. Uses your own Google account via `gcloud`.

**1. Enable the Sheets API**

1. Go to [console.cloud.google.com](https://console.cloud.google.com)
2. Create or select a project
3. **APIs & Services → Library → Google Sheets API → Enable**

**2. Install the Google Cloud SDK (`gcloud`)**

If you don't have `gcloud` installed yet:

- **Linux/Mac:**
  ```bash
  curl https://sdk.cloud.google.com | bash
  exec -l $SHELL
  gcloud init
  ```
- **Mac (Homebrew):**
  ```bash
  brew install --cask google-cloud-sdk
  ```

**3. Authenticate once from the terminal**

```bash
gcloud auth application-default login
```

A browser window opens — log in with your Google account. Done.

**3. Share the Sheet with your Google account**

Make sure the account you logged in with has at least **Viewer** access to the Sheet.

---

### Option B — Service Account key file

> Use this only if your organisation allows service account key creation.
> If you see `iam.disableServiceAccountKeyCreation`, use Option A instead.

**1. Enable the Sheets API** (same steps as above)

**2. Create a Service Account and download credentials**

1. **APIs & Services → Credentials → Create credentials → Service Account**
2. Give it a name (e.g. `moodle-loader`) and click **Done**
3. Click the service account → **Keys → Add key → Create new key → JSON**
4. Save the downloaded file as `credentials.json` in the project root

> `credentials.json` is in `.gitignore` — never commit it.

**3. Share the Sheet with the Service Account**

1. Copy the `client_email` from `credentials.json`
   (e.g. `moodle-loader@your-project.iam.gserviceaccount.com`)
2. Open your Google Sheet → **Share**, paste the email, grant **Viewer** access

---

### Configure the sheet columns

The sheet must have a header row with at least these columns:

| Column | Maps to | Required |
|---|---|---|
| `Course name (Spanish)` | `fullname` | yes |
| `CODE` | `shortname` | yes |
| `Course Name (English)` | `summary` | no |
| `Path` | `category_id` (resolved via Moodle API) | no |
| `template_id` | `template_id` | no (default: `DEFAULT_TEMPLATE_ID`) |
| `Moodle Link` | written back after creation | no |

Category names in `Path` are matched against Moodle category names automatically.
If a name is not found, it falls back to `DEFAULT_CATEGORY_NAME` (configurable in `.env`).

After a course is created, the Moodle course URL is automatically written to the `Moodle Link` column.
Use `--no-writeback` to skip this step.

> **Re-authentication after a scope change**: if you have an existing `authorized_user.json`
> that was created with a read-only scope, delete it and run `moodle-loader load-sheets` again
> to trigger a fresh OAuth flow with write access.

## YAML format

```yaml
defaults:
  category_id: 2
  visible: false

courses:
  - template_id: 10              # 10 = MOOC, 18 = SEMINAR
    fullname: "Bitcoin Basics — May 2026 Cohort"
    shortname: "bitcoin-basics-2026-05"
    summary: "Introductory Bitcoin course."
```

## Tests

```bash
pytest
```

## Layout

```
src/moodle_loader/
├── cli.py          # Typer entry point
├── config.py       # settings loaded from .env
├── client.py       # Moodle Web Services wrapper
├── loader.py       # orchestrator
├── models.py       # CourseSpec, LoadResult
└── sources/        # YAML, Google Sheets
```