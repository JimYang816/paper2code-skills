"""Read-only verification of the distribution lock and optional upstream Git objects."""

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys


def digest(data):
    return hashlib.sha256(data).hexdigest()


def content_hash(files):
    return digest(json.dumps(files, sort_keys=True, separators=(",", ":")).encode())


def require(condition, message):
    if not condition:
        raise ValueError(message)


def safe_path(root, relative):
    require(isinstance(relative, str) and relative and "\\" not in relative,
            f"Invalid relative path: {relative!r}")
    path = root / relative
    require(not Path(relative).is_absolute() and ".." not in Path(relative).parts,
            f"Unsafe path: {relative}")
    require(path.resolve().is_relative_to(root.resolve()), f"Path escapes root: {relative}")
    require(not path.is_symlink(), f"Symlink not allowed: {relative}")
    return path


def inventory(directory):
    require(directory.is_dir(), f"Missing directory: {directory}")
    result = {}
    for path in sorted(directory.rglob("*")):
        require(not path.is_symlink(), f"Symlink not allowed: {path}")
        if path.is_file():
            result[path.relative_to(directory).as_posix()] = digest(path.read_bytes())
    return result


def git(checkout, *args):
    return subprocess.check_output(["git", "-C", str(checkout), *args], stderr=subprocess.PIPE)


def source_inventory(checkout, revision, directory):
    names = git(checkout, "ls-tree", "-r", "--name-only", "-z", revision, "--", directory)
    prefix = directory + "/"
    result = {}
    for raw in names.split(b"\0"):
        if raw:
            name = raw.decode("utf-8")
            require(name.startswith(prefix), f"Invalid source path: {name}")
            result[name[len(prefix):]] = digest(git(checkout, "show", f"{revision}:{name}"))
    require(result, f"Missing upstream directory: {directory}")
    return result


def verify(root, upstream=None):
    lock = json.loads((root / "skills-lock.yaml").read_text(encoding="utf-8"))
    require(lock["version"] == 1, "Unsupported lock version")
    skills = lock["skills"]
    require(skills and lock["roots"], "Empty closure")
    reached = set()
    pending = list(lock["roots"])
    while pending:
        name = pending.pop()
        require(name in skills, f"Missing dependency: {name}")
        if name not in reached:
            reached.add(name)
            pending.extend(skills[name]["dependencies"])
    require(reached == set(skills), f"Unrelated skills: {sorted(set(skills) - reached)}")
    actual_names = {p.name for p in (root / "skills").iterdir()}
    require(actual_names == set(skills), "Skill directory inventory differs from lock")
    for name, entry in skills.items():
        require(re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name), f"Invalid skill name: {name}")
        files = inventory(safe_path(root, f"skills/{name}"))
        require("SKILL.md" in files, f"Missing SKILL.md: {name}")
        require(files == entry["files"], f"File inventory or hash mismatch: {name}")
        require(content_hash(files) == entry["content_hash"], f"Content hash mismatch: {name}")
        classification = entry["classification"]
        require(classification in ("unchanged", "adapted", "new"), f"Invalid classification: {name}")
        require(entry["origin"] and entry["license"] == "MIT", f"Missing origin/license: {name}")
        if classification == "new":
            require("source_files" not in entry, f"New skill has upstream file map: {name}")
            continue
        source = entry["origin"]
        require(re.fullmatch(r"[0-9a-f]{40}", source["revision"]), f"Unpinned revision: {name}")
        require(source["repository"] == lock["upstream"]["repository"]
                and source["revision"] == lock["upstream"]["revision"], f"Inconsistent source: {name}")
        require(content_hash(entry["source_files"]) == entry["source_hash"], f"Source hash mismatch: {name}")
        if classification == "unchanged":
            require(files == entry["source_files"], f"Unchanged skill differs from source: {name}")
        else:
            require(entry.get("modifications"), f"Missing adaptation note: {name}")
        if upstream:
            require(source_inventory(upstream, source["revision"], source["path"])
                    == entry["source_files"], f"Upstream source mismatch: {name}")
    for path, expected in lock["distribution_files"].items():
        require(digest(safe_path(root, path).read_bytes()) == expected, f"Distribution file mismatch: {path}")
    required = {"LICENSE", "THIRD_PARTY_NOTICES.md", "licenses/mattpocock-skills-LICENSE", ".gitattributes"}
    require(required <= set(lock["distribution_files"]), "Missing licensing records")
    if upstream:
        source = lock["upstream"]
        require(digest(git(upstream, "show", f"{source['revision']}:LICENSE"))
                == lock["distribution_files"]["licenses/mattpocock-skills-LICENSE"],
                "Upstream license mismatch")
    return len(skills)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--upstream", type=Path)
    args = parser.parse_args()
    try:
        count = verify(args.root, args.upstream)
    except (ValueError, KeyError, TypeError, OSError, subprocess.CalledProcessError) as error:
        print(f"INVALID: {error}", file=sys.stderr)
        return 1
    print(f"OK: {count} skills; closure, byte hashes and licenses verified"
          + (" against upstream Git objects" if args.upstream else " offline"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
