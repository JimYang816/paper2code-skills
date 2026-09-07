"""Standard-library capability checks shared by setup and the report CLI."""

import json
import os
from pathlib import Path
import shutil
import subprocess


def git_executable():
    return shutil.which("git")


def gh_executable():
    override = os.environ.get("PAPER2CODE_GH")
    if override:
        if os.path.isabs(override):
            return override if Path(override).exists() else None
        return shutil.which(override)
    return shutil.which("gh")


def run_gh(target, *arguments):
    executable = gh_executable()
    if not executable:
        raise FileNotFoundError("GitHub CLI")
    command = [executable, *arguments]
    if os.name == "nt" and executable.lower().endswith((".cmd", ".bat")):
        command = ["cmd", "/c", executable, *arguments]
    return subprocess.run(command, cwd=target, text=True, capture_output=True)


def github_ready(target):
    if not git_executable() or not gh_executable():
        return False
    remote = subprocess.run(
        ["git", "remote", "get-url", "origin"],
        cwd=target,
        text=True,
        capture_output=True,
    )
    if remote.returncode != 0 or "github.com" not in remote.stdout.lower():
        return False
    try:
        return run_gh(target, "auth", "status").returncode == 0
    except (OSError, FileNotFoundError):
        return False


def build_report(root=None):
    available = []
    missing = []
    recovery_commands = []

    if git_executable():
        available.append({"name": "Git"})
    else:
        missing.append({"name": "Git"})
        recovery_commands.append("Install Git and put git on PATH.")

    if gh_executable():
        available.append({"name": "GitHub CLI"})
    else:
        missing.append({"name": "GitHub CLI"})
        recovery_commands.append("Install GitHub CLI and run gh auth login.")

    if root is not None and not github_ready(root):
        missing.append({"name": "GitHub repository access"})
        recovery_commands.append("Add an existing GitHub origin and authenticate gh.")

    return {
        "schema_version": "1.0",
        "stage": "setup-paper2code",
        "available": available,
        "missing": missing,
        "recovery_commands": recovery_commands,
    }


def render_report(report=None):
    return json.dumps(report or build_report(), indent=2, sort_keys=True) + "\n"
