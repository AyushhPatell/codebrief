# codebrief

**codebrief** is a small Python CLI that reads a local project folder (or clones a public GitHub repo), gathers structure and important files, and asks OpenAI to write a plain-English summary of what the project is and how it fits together.

## What you need

- Python 3.10+
- An [OpenAI API key](https://platform.openai.com/api-keys) (you add it locally; see below)

## Keeping your API key safe

Your key is **only** read from a local `.env` file (or from the `OPENAI_API_KEY` environment variable). That is the right pattern for a repo you publish on GitHub.

- **Committed to the repo:** `.env.example` — placeholder text only, no real secret.
- **Not committed:** `.env` — where you paste your real key. It is listed in `.gitignore`, so normal `git add` / `git push` will not upload it.
- Before you push, run `git status` and make sure `.env` is **not** listed as a new or modified file to be committed.
- To double-check that Git ignores it: `git check-ignore -v .env` (should print a rule from `.gitignore`).
- Do not put keys in README, issues, or screenshots. If a key ever leaks, revoke it in the [OpenAI API keys](https://platform.openai.com/api-keys) page and create a new one.

Copy `.env.example` → `.env` and add your own key.

## Quick start

- Go to the project folder: `cd codebrief` (or `cd` to wherever you cloned it).
- Create a virtual environment: `python3 -m venv .venv`
- Activate it: `source .venv/bin/activate` — on Windows: `.venv\Scripts\activate`
- Install dependencies: `pip install -r requirements.txt`
- Copy the env template: `cp .env.example .env`
- Edit `.env` and set `OPENAI_API_KEY` to your key (that file stays on your machine only; do not commit it).

**Run it** (with the venv still activated, so `python3` uses `.venv`):

- Summarize a local folder: `python3 codebrief.py /path/to/some/project`
- Summarize a public GitHub repo: `python3 codebrief.py https://github.com/owner/repo`

If you prefer not to activate the venv, run the same command with the full interpreter path, for example: `.venv/bin/python3 codebrief.py /path/to/some/project`.

## How it works (short)

- **Local path** — uses that folder.
- **GitHub URL** — shallow clone into a temp directory, then deletes it when finished.

## Project layout

- **`codebrief.py`** — CLI and logic.
- **`requirements.txt`** — Dependencies.
- **`.env.example`** — Safe template (commit this).
- **`.env`** — Your real key (gitignored — do not commit).
- **`.gitignore`** — Excludes `.env`, venv, caches.
