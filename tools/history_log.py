# Required Notice: Copyright Matthew Armstrong (https://github.com/The-Dorkknight)
# Licensed under the PolyForm Noncommercial License 1.0.0. No warranty.
"""Write docs/HISTORY.md: one entry per build (commit): version/tag, date, files, +/- lines and the ten
code files changed most. Entries already in the file are kept, so builds trimmed from git stay on record.
Run it on the full history BEFORE trimming old builds, and again on every new build."""
import os, re, subprocess, sys

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
OUT = os.path.join(ROOT, "docs", "HISTORY.md")
HEAD = "# Build history\n\nOne entry per build, written by `tools/history_log.py` (older builds are trimmed from git but stay listed here).\n"
CODE = (".py", ".js", ".qml", ".html", ".css", ".sh", ".bat", ".command", ".yml", ".json", ".toml")


def git(*a):
    return subprocess.run(["git", "-C", ROOT, *a], capture_output=True, text=True).stdout


def entries_in_file():
    if not os.path.exists(OUT):
        return {}
    text = open(OUT, encoding="utf-8").read()
    out = {}
    for block in re.split(r"(?m)^## ", text)[1:]:
        key = block.split("\n", 1)[0].split(" · ")[0].strip()
        out[key] = "## " + block.rstrip() + "\n"
    return out


def main():
    old = entries_in_file()
    new = {}
    revs = git("rev-list", "--reverse", "HEAD").split()
    for h in revs:
        tags = git("tag", "--points-at", h).split()
        key = tags[0] if tags else h[:7]
        date = git("show", "-s", "--format=%ad", "--date=short", h).strip()
        stat = git("show", "--numstat", "--format=", h).strip().splitlines()
        rows = []
        for line in stat:
            a, d, f = (line.split("\t") + ["", "", ""])[:3]
            if a.isdigit() and d.isdigit():
                rows.append((int(a) + int(d), int(a), int(d), f))
        ins, dele = sum(r[1] for r in rows), sum(r[2] for r in rows)
        top = sorted((r for r in rows if r[3].endswith(CODE)), reverse=True)[:10]
        body = "## %s · %s · %d files, +%d / -%d lines\n\n" % (key, date, len(rows), ins, dele)
        body += "Top code files changed:\n\n" + "".join("- `%s` +%d / -%d\n" % (f, a, d) for _, a, d, f in top)
        new[key] = body
    merged = dict(old); merged.update(new)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    open(OUT, "w", encoding="utf-8").write(HEAD + "\n" + "\n".join(merged.values()))
    print("wrote %s (%d entries, %d from git)" % (os.path.relpath(OUT, ROOT), len(merged), len(new)))


if __name__ == "__main__":
    sys.exit(main())
