# Moodle Coruse Loader

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

For Google Sheets support, install the optional extra:

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

## Google Sheets setup

Authentication uses a **Google Service Account** — a robot user that accesses the sheet without any interactive login.

### 1. Create a Google Cloud project and enable the API

1. Go to [console.cloud.google.com](https://console.cloud.google.com)
2. Create a new project (or reuse an existing one)
3. Navigate to **APIs & Services → Library**
4. Search for **Google Sheets API** and click **Enable**

### 2. Create a Service Account and download credentials

1. Go to **APIs & Services → Credentials**
2. Click **Create credentials → Service Account**
3. Give it a name (e.g. `moodle-loader`) and click **Done**
4. Click on the new service account → **Keys** tab → **Add key → Create new key → JSON**
5. Download the file and save it as `credentials.json` in the project root

> `credentials.json` is in `.gitignore` — never commit it.

### 3. Share your Google Sheet with the Service Account

1. Open the `credentials.json` file and copy the `client_email` value
   (looks like `moodle-loader@your-project.iam.gserviceaccount.com`)
2. Open your Google Sheet → **Share**
3. Paste the email and grant **Viewer** access (read-only is enough)

### 4. Configure the sheet columns

The sheet must have a header row with at least these columns:

| Column | Maps to | Required |
|---|---|---|
| `Course name (Spanish)` | `fullname` | yes |
| `CODE` | `shortname` | yes |
| `Course Name (English)` | `summary` | no |
| `Path` | `category_id` (resolved via Moodle API) | no |
| `template_id` | `template_id` | no (default: `DEFAULT_TEMPLATE_ID`) |

Category names in `Path` are matched against Moodle category names automatically.
If a name is not found, it falls back to `DEFAULT_CATEGORY_NAME` (configurable in `.env`).

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