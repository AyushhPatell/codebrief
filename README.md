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

Cloners of your repo get no key from you — they copy `.env.example` → `.env` and add their own key.

## Quick start

cd codebrief
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env

# Edit `.env`: set OPENAI_API_KEY to your key (this file stays on your machine only)

Run it:

python codebrief.py /path/to/some/project
python codebrief.py https://github.com/owner/repo


- **`--detail`** — longer answer with more module-level / architecture detail.

## How it works (short)

1. **Local path** — uses that folder. 
2. **GitHub URL** — shallow clone into a temp directory, then deletes it when finished.

## Project layout

1. codebrief.py - All logic.
2. requirements.txt - Dependencies.
3. .env.example - Safe template (commit this).
4. .env - Your real key (gitignored — do not commit).
5. .gitignore - Excludes .env, venv, caches.
