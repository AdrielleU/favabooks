#!/usr/bin/env python3
"""Check for Fava and Beancount releases that Favabooks hasn't taken in.

- Fava: is the newest release tag of beancount/fava merged into HEAD? A
  new major version (2.0 after 1.x) usually needs work in the qb-fork code.
- Python dependencies: is the newest release on PyPI of each dependency
  allowed by pyproject.toml? One that isn't (Beancount 4 with
  "beancount>=3.2.0,<4") needs its limit raised, and the code checked.

Writes a Markdown report; with --github-output, sets `action_needed` for
the upstream.yml workflow. Needs git, network access and `packaging`:

    uv run --no-project --with packaging python contrib/check_upstream.py

--overrides FILE instead writes uv overrides that drop our version limits,
to test with the newest releases (`uv pip install --overrides FILE`);
add --main to take Beancount, beangulp and beanquery from their main
branches.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import urllib.request
from pathlib import Path

import tomllib
from packaging.requirements import Requirement
from packaging.version import InvalidVersion
from packaging.version import Version

ROOT = Path(__file__).parent.parent
FAVA = "https://github.com/beancount/fava"
#: Where upstream refs are fetched to, out of the way of our own tags.
REFS = "refs/upstream"
PYPI = "https://pypi.org/pypi/{}/json"
#: Packages tested from their main branch with --main.
MAIN = {
    "beancount": "git+https://github.com/beancount/beancount@master",
    "beangulp": "git+https://github.com/beancount/beangulp@master",
    "beanquery": "git+https://github.com/beancount/beanquery@master",
}


def git(*args: str) -> str:
    return subprocess.run(
        ["git", *args],  # noqa: S607
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


def merged(ref: str) -> bool:
    done = subprocess.run(
        ["git", "merge-base", "--is-ancestor", ref, "HEAD"],  # noqa: S607
        cwd=ROOT,
        check=False,
    )
    return done.returncode == 0


def release_tags() -> list[tuple[Version, str]]:
    """Fava's release tags (vX.Y.Z), oldest first, fetched to REFS."""
    git(
        "fetch",
        "--quiet",
        "--no-tags",
        FAVA,
        f"+refs/heads/main:{REFS}/main",
        f"+refs/tags/v*:{REFS}/tags/v*",
    )
    tags = []
    for ref in git(
        "for-each-ref", "--format=%(refname)", f"{REFS}/tags"
    ).split():
        name = ref.rsplit("/", 1)[1]
        try:
            version = Version(name)
        except InvalidVersion:
            continue
        if not version.is_prerelease:
            tags.append((version, ref))
    return sorted(tags)


def kind(old: Version, new: Version) -> str:
    if new.major != old.major:
        return "major"
    return "minor" if new.minor != old.minor else "patch"


def check_fava() -> tuple[list[str], bool]:
    tags = release_tags()
    newest = tags[-1][0]
    ours = next((v for v, ref in reversed(tags) if merged(ref)), None)
    behind = int(git("rev-list", "--count", f"HEAD..{REFS}/main"))
    lines = ["## Fava", ""]
    if ours == newest:
        lines.append(f"Up to date: Fava {newest} is merged.")
    else:
        change = kind(ours, newest) if ours is not None else "new"
        lines += [
            (
                f"**Fava {newest} is out** ({change} release); Favabooks "
                f"has {ours or 'none'}."
            ),
            "",
            f"- Release notes: {FAVA}/blob/main/CHANGES",
            (
                "- Merge it: `git fetch upstream && git merge upstream/main`"
                " (merge, never rebase), then `make lint mypy test`"
            ),
        ]
        if change == "major":
            lines.append(
                "- A major version: check the qb-fork code against its "
                "breaking changes first."
            )
    lines += ["", f"Upstream main is {behind} commits ahead of us."]
    return lines, ours != newest


def newest_release(name: str) -> Version:
    with urllib.request.urlopen(PYPI.format(name), timeout=30) as response:  # noqa: S310
        data = json.load(response)
    versions = []
    for text, files in data["releases"].items():
        try:
            version = Version(text)
        except InvalidVersion:
            continue
        yanked = all(f.get("yanked") for f in files)
        if files and not yanked and not version.is_prerelease:
            versions.append(version)
    return max(versions)


def dependencies() -> list[Requirement]:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text())
    return [Requirement(t) for t in pyproject["project"]["dependencies"]]


def overrides(*, main: bool) -> str:
    """Each dependency without its version limits (or from main)."""
    lines = []
    for req in dependencies():
        line = req.name
        if main and req.name in MAIN:
            line += f" @ {MAIN[req.name]}"
        if req.marker is not None:
            line += f" ; {req.marker}"
        lines.append(line)
    return "\n".join(lines) + "\n"


def check_dependencies() -> tuple[list[str], bool]:
    lines = [
        "## Python dependencies",
        "",
        "| Package | We allow | Newest | |",
        "| --- | --- | --- | --- |",
    ]
    blocked = False
    for req in dependencies():
        if req.marker is not None and not req.marker.evaluate():
            continue
        newest = newest_release(req.name)
        if req.specifier.contains(newest):
            status = "ok"
        else:
            blocked = True
            lowest = min(
                (Version(s.version) for s in req.specifier), default=newest
            )
            status = f"**not allowed** ({kind(lowest, newest)})"
        lines.append(
            f"| {req.name} | `{req.specifier}` | {newest} | {status} |"
        )
    if blocked:
        lines += [
            "",
            (
                "To take a release that's not allowed: raise the limit in "
                "pyproject.toml, `uv lock`, `make test`, and fix what "
                'breaks. The "newest releases" test run shows what does.'
            ),
        ]
    return lines, blocked


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--report", type=Path, help="write the report here")
    parser.add_argument(
        "--github-output", type=Path, help="append action_needed=… here"
    )
    parser.add_argument(
        "--overrides", type=Path, help="only write uv overrides here"
    )
    parser.add_argument(
        "--main", action="store_true", help="Beancount from main (overrides)"
    )
    args = parser.parse_args()
    if args.overrides:
        args.overrides.write_text(overrides(main=args.main))
        return 0
    fava, fava_behind = check_fava()
    deps, deps_blocked = check_dependencies()
    report = "\n".join([*fava, "", *deps]) + "\n"
    sys.stdout.write(report)
    if args.report:
        args.report.write_text(report)
    needed = fava_behind or deps_blocked
    if args.github_output:
        with args.github_output.open("a") as output:
            output.write(f"action_needed={str(needed).lower()}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
