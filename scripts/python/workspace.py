#!/usr/bin/env python3
"""Resolve install profiles from config/workspace.yaml.

The manifest declares repositories, the groups they belong to, and the profiles that
select those groups. This module turns a profile name into the concrete repository list
that scripts/setup.sh clones, and validates that the selected profile can actually serve
the hardware configured in config/robot_overrides.yaml.

Usage:
    workspace.py profiles
    workspace.py repos   --profile dfki
    workspace.py specs   --profile dfki            # pipe-separated, consumed by setup.sh
    workspace.py check   --profile dfki --overrides config/robot_overrides.yaml
    workspace.py paths   --profile dfki            # submodule paths for `submodule.active`
    workspace.py verify-submodules                 # .gitmodules vs manifest drift check
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "config" / "workspace.yaml"


class ManifestError(Exception):
    """Raised when the manifest is internally inconsistent or a name is unknown."""


def load_manifest(path: Path = MANIFEST) -> dict[str, Any]:
    """Load and self-check the workspace manifest.

    Args:
        path: Location of the manifest file.

    Returns:
        The parsed manifest.

    Raises:
        ManifestError: If a group references an unknown repo, a profile references an
            unknown group, or a repo belongs to no group.
    """
    manifest = yaml.safe_load(path.read_text()) or {}
    repos = manifest.get("repos", {})
    groups = manifest.get("groups", {})
    profiles = manifest.get("profiles", {})

    grouped: set[str] = set()
    for group, members in groups.items():
        for name in members:
            if name not in repos:
                raise ManifestError(f"group '{group}' references unknown repo '{name}'")
            if name in grouped:
                raise ManifestError(f"repo '{name}' appears in more than one group")
            grouped.add(name)

    for orphan in sorted(set(repos) - grouped):
        raise ManifestError(f"repo '{orphan}' belongs to no group")

    for profile, members in profiles.items():
        for group in members:
            if group not in groups:
                raise ManifestError(f"profile '{profile}' references unknown group '{group}'")

    return manifest


def resolve(manifest: dict[str, Any], profile: str) -> list[str]:
    """List the repositories a profile installs, in manifest order.

    Args:
        manifest: The parsed manifest.
        profile: Profile name to resolve.

    Returns:
        Repository names.

    Raises:
        ManifestError: If the profile is not defined.
    """
    profiles = manifest["profiles"]
    if profile not in profiles:
        known = ", ".join(sorted(profiles))
        raise ManifestError(f"unknown profile '{profile}' (known: {known})")

    selected: list[str] = []
    for group in profiles[profile]:
        selected.extend(manifest["groups"][group])
    return selected


def _spec_line(name: str, spec: dict[str, Any], ros_distro: str) -> str:
    """Render one repository as a pipe-separated line for the shell to consume.

    Pipe rather than tab: bash treats tab as IFS whitespace and collapses runs of it,
    which silently shifts empty fields in `read`.
    """
    branch = (spec.get("branch") or "").format(ros_distro=ros_distro)
    flags = ",".join(
        flag
        for flag in ("recurse_submodules", "optional", "special")
        if spec.get(flag)
    )
    return "|".join([name, spec["url"], branch, str(spec.get("rev") or ""), flags])


def submodule_repos(manifest: dict[str, Any], profile: str | None) -> list[tuple[str, str]]:
    """List repositories that are managed as submodules, as (path, name) pairs.

    Repositories flagged `special` are excluded: they are handled by the bespoke
    franka_ros2 block in setup.sh and cannot be submodules while that surgery deletes
    tracked files from the upstream tree.

    Args:
        manifest: The parsed manifest.
        profile: Profile to restrict to, or None for the union of every profile.

    Returns:
        Pairs of (submodule path, repo name), in manifest order.
    """
    if profile is None:
        names: list[str] = []
        for candidate in manifest["profiles"]:
            for name in resolve(manifest, candidate):
                if name not in names:
                    names.append(name)
    else:
        names = resolve(manifest, profile)

    return [(f"src/{n}", n) for n in names if not manifest["repos"][n].get("special")]


def declared_submodules(gitmodules: Path) -> dict[str, str]:
    """Read submodule path -> url from a .gitmodules file.

    Args:
        gitmodules: Path to the .gitmodules file.

    Returns:
        Mapping of submodule path to url, empty if the file does not exist.
    """
    if not gitmodules.exists():
        return {}
    out = subprocess.run(
        ["git", "config", "-f", str(gitmodules), "--get-regexp", r"^submodule\..*\.(path|url)$"],
        capture_output=True, text=True, check=False,
    ).stdout
    paths: dict[str, str] = {}
    urls: dict[str, str] = {}
    for line in out.splitlines():
        key, _, value = line.partition(" ")
        name = key[len("submodule."):].rsplit(".", 1)[0]
        (paths if key.endswith(".path") else urls)[name] = value
    return {path: urls.get(name, "") for name, path in paths.items()}


def cmd_profiles(manifest: dict[str, Any], _: argparse.Namespace) -> int:
    """Print each profile with its groups and whether it needs private access."""
    for profile, groups in manifest["profiles"].items():
        repos = resolve(manifest, profile)
        private = [r for r in repos if manifest["repos"][r].get("visibility") != "public"]
        access = f"needs access to {len(private)} private repo(s)" if private else "fully public"
        print(f"{profile:10s} {len(repos):2d} repos  [{', '.join(groups)}]  - {access}")
    return 0


def cmd_repos(manifest: dict[str, Any], args: argparse.Namespace) -> int:
    """Print the repository names selected by a profile."""
    for name in resolve(manifest, args.profile):
        spec = manifest["repos"][name]
        if args.visibility and spec.get("visibility") != args.visibility:
            continue
        print(name)
    return 0


def cmd_specs(manifest: dict[str, Any], args: argparse.Namespace) -> int:
    """Print tab-separated clone specs for a profile."""
    ros_distro = args.ros_distro or os.environ.get("ROS_DISTRO", "humble")
    for name in resolve(manifest, args.profile):
        print(_spec_line(name, manifest["repos"][name], ros_distro))
    return 0


def cmd_check(manifest: dict[str, Any], args: argparse.Namespace) -> int:
    """Verify the profile provides drivers for the hardware in robot_overrides.yaml.

    Missing drivers are an error against real hardware and a warning against fake
    hardware, where the driver package may not be exercised at all.
    """
    overrides = yaml.safe_load(Path(args.overrides).read_text()) or {}
    groups = set(manifest["profiles"][args.profile]) if args.profile in manifest["profiles"] else set()
    requirements = manifest.get("gripper_requirements", {})
    fake = str(overrides.get("use_fake_hardware", False)).lower() == "true"

    problems: list[str] = []
    for side in ("left", "right"):
        arm = f"franka_{side}"
        if str(overrides.get(f"spawn_{arm}", True)).lower() != "true":
            continue
        gripper = overrides.get(arm, {}).get("gripper_type")
        needed = requirements.get(gripper)
        if needed and needed not in groups:
            problems.append(
                f"  {arm}.gripper_type: {gripper!r} needs group '{needed}', "
                f"which profile '{args.profile}' does not install"
            )

    if not problems:
        return 0

    level = "warning" if fake else "error"
    print(f"{level}: {Path(args.overrides).name} is incompatible with profile "
          f"'{args.profile}':", file=sys.stderr)
    print("\n".join(problems), file=sys.stderr)
    if fake:
        print("  (use_fake_hardware is true, continuing anyway)", file=sys.stderr)
        return 0
    return 1


def cmd_paths(manifest: dict[str, Any], args: argparse.Namespace) -> int:
    """Print submodule paths, one per line, for `git config submodule.active`."""
    for path, _ in submodule_repos(manifest, None if args.all else args.profile):
        print(path)
    return 0


def cmd_verify_submodules(manifest: dict[str, Any], args: argparse.Namespace) -> int:
    """Report drift between .gitmodules and the manifest.

    Optional repositories that are not yet published are allowed to be missing.
    """
    declared = declared_submodules(args.gitmodules)
    expected = {path: manifest["repos"][name] for path, name in submodule_repos(manifest, None)}

    problems: list[str] = []
    for path, spec in expected.items():
        if path not in declared:
            if spec.get("optional"):
                print(f"note: optional '{path}' not yet a submodule, skipping")
                continue
            problems.append(f"  missing from .gitmodules: {path}")
        elif declared[path] != spec["url"]:
            problems.append(
                f"  url drift at {path}:\n"
                f"    .gitmodules: {declared[path]}\n"
                f"    manifest:    {spec['url']}"
            )
    for path in sorted(set(declared) - set(expected)):
        problems.append(f"  in .gitmodules but not the manifest: {path}")

    if problems:
        print("error: .gitmodules and config/workspace.yaml disagree:", file=sys.stderr)
        print("\n".join(problems), file=sys.stderr)
        return 1
    print(f"ok: {len(declared)} submodule(s) match the manifest")
    return 0


def main() -> int:
    """Parse arguments and dispatch to the selected subcommand."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--manifest", type=Path, default=MANIFEST)
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("profiles", help="list available install profiles")

    p_repos = sub.add_parser("repos", help="list repositories in a profile")
    p_repos.add_argument("--profile", required=True)
    p_repos.add_argument("--visibility", choices=["public", "private"])

    p_specs = sub.add_parser("specs", help="print pipe-separated clone specs")
    p_specs.add_argument("--profile", required=True)
    p_specs.add_argument("--ros-distro", dest="ros_distro")

    p_check = sub.add_parser("check", help="validate a profile against robot_overrides.yaml")
    p_check.add_argument("--profile", required=True)
    p_check.add_argument("--overrides", required=True)

    p_paths = sub.add_parser("paths", help="print submodule paths for a profile")
    p_paths_target = p_paths.add_mutually_exclusive_group(required=True)
    p_paths_target.add_argument("--profile")
    p_paths_target.add_argument("--all", action="store_true",
                                help="union across every profile (what .gitmodules must hold)")

    p_verify = sub.add_parser("verify-submodules", help="check .gitmodules against the manifest")
    p_verify.add_argument("--gitmodules", type=Path, default=ROOT / ".gitmodules")

    args = parser.parse_args()
    handlers = {
        "profiles": cmd_profiles,
        "repos": cmd_repos,
        "specs": cmd_specs,
        "check": cmd_check,
        "paths": cmd_paths,
        "verify-submodules": cmd_verify_submodules,
    }
    try:
        return handlers[args.command](load_manifest(args.manifest), args)
    except ManifestError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
