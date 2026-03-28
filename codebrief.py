#!/usr/bin/env python3
"""
codebrief — explain a codebase in plain English (local folder or GitHub URL).
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import tempfile
from pathlib import Path

from dotenv import load_dotenv
from git import Repo
from openai import OpenAI

MAX_TREE_DEPTH = 5
MAX_TREE_ENTRIES_PER_DIR = 40
MAX_FILE_BYTES = 48_000
MAX_TOTAL_CONTEXT_CHARS = 120_000
SKIP_DIR_NAMES = frozenset(
    {
        ".git",
        ".svn",
        ".hg",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        ".tox",
        ".venv",
        "venv",
        "env",
        ".env",
        "node_modules",
        "dist",
        "build",
        ".next",
        ".nuxt",
        "target",
        ".idea",
        ".vscode",
        "coverage",
        ".turbo",
        ".parcel-cache",
    }
)

KEY_FILE_NAMES = [
    "readme.md",
    "readme.rst",
    "readme.txt",
    "readme",
    "pyproject.toml",
    "setup.py",
    "setup.cfg",
    "requirements.txt",
    "requirements-dev.txt",
    "poetry.lock",
    "package.json",
    "package-lock.json",
    "pnpm-lock.yaml",
    "yarn.lock",
    "tsconfig.json",
    "vite.config.ts",
    "vite.config.js",
    "next.config.js",
    "next.config.mjs",
    "cargo.toml",
    "go.mod",
    "go.sum",
    "composer.json",
    "gemfile",
    "dockerfile",
    "docker-compose.yml",
    "docker-compose.yaml",
    "makefile",
    "justfile",
    "license",
    "license.md",
    "contributing.md",
]

ENTRY_HINTS = [
    "main.py",
    "app.py",
    "manage.py",
    "wsgi.py",
    "asgi.py",
    "index.js",
    "index.ts",
    "main.js",
    "main.ts",
    "cli.py",
    "__main__.py",
]


def eprint(*args: object, **kwargs: object) -> None:
    print(*args, file=sys.stderr, **kwargs)


def is_github_url(s: str) -> bool:
    s = s.strip().rstrip("/")
    return bool(
        re.match(
            r"^https?://github\.com/[\w.-]+/[\w.-]+(?:\.git)?(?:/.*)?$",
            s,
            re.I,
        )
    )


def normalize_github_clone_url(url: str) -> str:
    url = url.strip().rstrip("/")
    m = re.match(r"^(https?://github\.com/[\w.-]+/[\w.-]+)", url, re.I)
    base = m.group(1) if m else url
    if not base.lower().endswith(".git"):
        base += ".git"
    return base


def load_simple_gitignore_rules(root: Path) -> list[str]:
    gi = root / ".gitignore"
    if not gi.is_file():
        return []
    rules: list[str] = []
    for line in gi.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        rules.append(line)
    return rules


def path_matches_gitignore(rel_posix: str, rules: list[str]) -> bool:
    for rule in rules:
        if rule.startswith("!"):
            continue
        r = rule.rstrip("/")
        if not r:
            continue
        if "*" in r or "?" in r or "[" in r:
            if r.endswith("/**"):
                prefix = r[:-3]
                if rel_posix == prefix or rel_posix.startswith(prefix + "/"):
                    return True
            elif r.endswith("*"):
                stem = r[:-1]
                if rel_posix.startswith(stem):
                    return True
            continue
        if rel_posix == r or rel_posix.startswith(r + "/"):
            return True
    return False


def should_skip_dir(name: str) -> bool:
    return name.lower() in SKIP_DIR_NAMES or name.startswith(".")


def project_tree(project_root: Path) -> str:
    rules = load_simple_gitignore_rules(project_root)

    def rel_gitignore_path(path: Path) -> str:
        try:
            return str(path.resolve().relative_to(project_root.resolve())).replace("\\", "/")
        except ValueError:
            return path.name

    def tree_with_rules(
        root: Path,
        *,
        max_depth: int = MAX_TREE_DEPTH,
        _depth: int = 0,
        _prefix: str = "",
    ) -> list[str]:
        lines: list[str] = []
        if _depth >= max_depth:
            return [f"{_prefix}… (max depth {max_depth})"]
        try:
            entries = sorted(
                [p for p in root.iterdir() if not should_skip_dir(p.name)],
                key=lambda p: (not p.is_dir(), p.name.lower()),
            )
        except OSError:
            return [f"{_prefix}[inaccessible: {root.name}]"]

        shown = 0
        for p in entries:
            rel_posix = rel_gitignore_path(p)
            if rules and path_matches_gitignore(rel_posix, rules):
                continue
            if shown >= MAX_TREE_ENTRIES_PER_DIR:
                lines.append(f"{_prefix}… and more (>{MAX_TREE_ENTRIES_PER_DIR} entries)")
                break
            marker = "/" if p.is_dir() else ""
            lines.append(f"{_prefix}{p.name}{marker}")
            shown += 1
            if p.is_dir():
                sub = tree_with_rules(
                    p, max_depth=max_depth, _depth=_depth + 1, _prefix=_prefix + "  "
                )
                lines.extend(sub)
        return lines

    body = "\n".join(tree_with_rules(project_root))
    return f"Project root: {project_root.resolve()}\n\n{body}"


def read_file_snippet(path: Path, max_bytes: int = MAX_FILE_BYTES) -> str | None:
    try:
        raw = path.read_bytes()
    except OSError:
        return None
    if len(raw) > max_bytes:
        text = raw[:max_bytes].decode("utf-8", errors="replace")
        return text + f"\n\n… [truncated: file is {len(raw)} bytes, showing first {max_bytes}]\n"
    return raw.decode("utf-8", errors="replace")


def collect_key_files(project_root: Path) -> list[tuple[str, str]]:
    collected: list[tuple[str, str]] = []
    seen: set[str] = set()

    def add(rel: str, content: str) -> None:
        if rel in seen:
            return
        seen.add(rel)
        collected.append((rel, content))

    root_files = {p.name.lower(): p for p in project_root.iterdir() if p.is_file()}
    for name in KEY_FILE_NAMES:
        p = root_files.get(name.lower())
        if p:
            text = read_file_snippet(p)
            if text is not None:
                add(str(p.relative_to(project_root)).replace("\\", "/"), text)

    for hint in ENTRY_HINTS:
        for path in project_root.rglob(hint):
            if any(should_skip_dir(part) for part in path.relative_to(project_root).parts):
                continue
            try:
                depth = len(path.relative_to(project_root).parts)
            except ValueError:
                continue
            if depth > 4:
                continue
            rel = str(path.relative_to(project_root)).replace("\\", "/")
            if rel in seen:
                continue
            text = read_file_snippet(path)
            if text is not None:
                add(rel, text)
            if len(seen) >= 24:
                break
        if len(seen) >= 24:
            break

    source_suffixes = {".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".rs", ".java"}
    for dirname in ("src", "lib", "app", "pkg", "internal", "packages"):
        d = project_root / dirname
        if not d.is_dir():
            continue
        files = sorted(
            [
                p
                for p in d.rglob("*")
                if p.is_file()
                and p.suffix.lower() in source_suffixes
                and not any(should_skip_dir(part) for part in p.relative_to(project_root).parts)
            ],
            key=lambda p: str(p),
        )[:6]
        for p in files:
            rel = str(p.relative_to(project_root)).replace("\\", "/")
            if rel in seen:
                continue
            text = read_file_snippet(p, max_bytes=min(MAX_FILE_BYTES, 24_000))
            if text is not None:
                add(rel, text)

    return collected


def build_context(project_root: Path) -> str:
    tree = project_tree(project_root)
    files = collect_key_files(project_root)
    parts = [
        "## Directory structure\n",
        tree,
        "\n\n## Selected file contents\n",
    ]
    for rel, content in files:
        parts.append(f"\n### File: {rel}\n```\n{content}\n```\n")

    text = "".join(parts)
    if len(text) > MAX_TOTAL_CONTEXT_CHARS:
        text = (
            text[: MAX_TOTAL_CONTEXT_CHARS - 200]
            + "\n\n… [context truncated for size; tree + early files kept first]\n"
        )
    return text


def build_system_prompt(detail: bool) -> str:
    base = (
        "You are a senior software engineer explaining a repository to a new teammate. "
        "Use clear headings, short paragraphs, and bullet lists. Avoid jargon unless you define it. "
        "If something is uncertain from the files, say what is unclear instead of guessing."
    )
    if detail:
        base += (
            " Provide a deeper breakdown: major modules or packages, what each is responsible for, "
            "and how data or control flows between them when inferable."
        )
    else:
        base += (
            " Keep the overview concise: purpose, who it is for, how to run or build if obvious, "
            "and the main parts of the layout."
        )
    return base


def build_user_prompt(context: str, detail: bool) -> str:
    level = "detailed" if detail else "high-level"
    return (
        f"Below is a folder tree (with some noisy paths omitted) and excerpts from key files "
        f"from a software project. Write a {level} plain-English brief.\n\n"
        "Include, when possible:\n"
        "- What the project does and its audience\n"
        "- Tech stack and runtime (languages, frameworks, tools)\n"
        "- How the repo is organized (important top-level folders)\n"
        "- Main entry points or apps and how they relate\n"
        "- Notable config or deployment hints\n\n"
        f"--- PROJECT CONTEXT ---\n{context}"
    )


def explain_project(
    project_root: Path,
    *,
    detail: bool,
    client: OpenAI,
    model: str,
) -> str:
    eprint("→ Scanning folder structure and key files…", flush=True)
    context = build_context(project_root.resolve())
    eprint("→ Asking the model for a summary…", flush=True)
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": build_system_prompt(detail)},
            {"role": "user", "content": build_user_prompt(context, detail)},
        ],
        temperature=0.3,
    )
    choice = resp.choices[0].message.content
    if not choice:
        raise RuntimeError("The model returned an empty response.")
    return choice.strip()


def resolve_target(path_or_url: str) -> tuple[Path, tempfile.TemporaryDirectory[str] | None]:
    raw = path_or_url.strip()
    if is_github_url(raw):
        clone_url = normalize_github_clone_url(raw)
        tmp = tempfile.TemporaryDirectory(prefix="codebrief-")
        eprint(f"→ Cloning {clone_url} (shallow)…", flush=True)
        try:
            Repo.clone_from(clone_url, tmp.name, depth=1, single_branch=True)
        except Exception:
            tmp.cleanup()
            raise
        return Path(tmp.name), tmp
    p = Path(raw).expanduser().resolve()
    if not p.exists():
        raise FileNotFoundError(f"Path does not exist: {p}")
    if not p.is_dir():
        raise NotADirectoryError(f"Not a directory: {p}")
    return p, None


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="codebrief",
        description=(
            "Summarize a codebase in plain English. "
            "Pass a local project folder or a public github.com repository URL."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python codebrief.py ./my-app
  python codebrief.py https://github.com/psf/requests
  python codebrief.py ../backend --detail --save

Setup:
  1. Copy .env.example to .env and set OPENAI_API_KEY.
  2. pip install -r requirements.txt

The tool reads README, common config files, likely entry points, and a few
source files, then asks OpenAI to write the brief. Temporary clones are
removed automatically.
""".strip(),
    )
    p.add_argument(
        "target",
        help="Local directory path or https://github.com/owner/repo URL",
    )
    p.add_argument(
        "--detail",
        action="store_true",
        help="Ask for a deeper per-module / architecture-style breakdown",
    )
    p.add_argument(
        "--save",
        nargs="?",
        const="codebrief.md",
        default=None,
        metavar="FILE",
        help="Write markdown to FILE (default: codebrief.md in the current directory)",
    )
    p.add_argument(
        "--model",
        default=None,
        help="OpenAI model id (overrides OPENAI_MODEL in .env; default gpt-4o-mini)",
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    args = parse_args(argv)

    api_key = (os.environ.get("OPENAI_API_KEY") or "").strip()
    if not api_key:
        eprint(
            "Missing OPENAI_API_KEY. Copy .env.example to .env and add your key, "
            "or export OPENAI_API_KEY in your shell.",
        )
        return 1

    model = (args.model or os.environ.get("OPENAI_MODEL") or "gpt-4o-mini").strip()
    client = OpenAI(api_key=api_key)

    tmp: tempfile.TemporaryDirectory[str] | None = None
    try:
        project_root, tmp = resolve_target(args.target)
        text = explain_project(project_root, detail=args.detail, client=client, model=model)
    except FileNotFoundError as e:
        eprint(str(e))
        return 1
    except NotADirectoryError as e:
        eprint(str(e))
        return 1
    except Exception as e:
        eprint(f"Error: {e}")
        return 1
    finally:
        if tmp is not None:
            tmp.cleanup()
            eprint("→ Removed temporary clone.", flush=True)

    print(text)
    if args.save is not None:
        out = Path(args.save).expanduser().resolve()
        out.write_text(text + "\n", encoding="utf-8")
        eprint(f"→ Saved to {out}", flush=True)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
