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

```bash
cd codebrief
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# Edit `.env`: set OPENAI_API_KEY to your key (this file stays on your machine only)
```

Run it:

```bash
python codebrief.py /path/to/some/project
python codebrief.py https://github.com/owner/repo
```

- **`--detail`** — longer answer with more module-level / architecture detail.
- **`--save`** or **`--save my-brief.md`** — write the result to a markdown file (default filename: `codebrief.md`).
- **`--model gpt-4o`** — override the model (or set `OPENAI_MODEL` in `.env`; default is `gpt-4o-mini`).

Progress lines (clone, scan, API) go to **stderr**; the brief itself prints to **stdout** so you can pipe it (`python codebrief.py ./app > brief.md`).

## How it works (short)

1. **Local path** — uses that folder. **GitHub URL** — shallow clone into a temp directory, then deletes it when finished.
2. Builds a **directory tree** (skips heavy folders like `node_modules`, respects a simple reading of `.gitignore`).
3. Pulls in **README**, common manifests (`package.json`, `pyproject.toml`, …), likely **entry-point** filenames, and a few files under `src/` / `lib/` / `app/` when present. Large files are truncated.
4. Sends that context to the **OpenAI API** and prints the markdown-style brief.

If the repo is private, cloning will fail unless your machine already has credentials configured for Git; this tool does not ask for a GitHub token.

## Project layout

| File | Role |
|------|------|
| `codebrief.py` | CLI and all logic |
| `requirements.txt` | Dependencies |
| `.env.example` | Safe template (commit this) |
| `.env` | Your real key (gitignored — do not commit) |
| `.gitignore` | Excludes `.env`, venv, caches |

## License

Use and modify freely for your own projects.
