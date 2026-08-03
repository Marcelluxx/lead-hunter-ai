"""Validate runtime dependency licenses against an explicit commercial policy."""

from __future__ import annotations

import argparse
import json
import re
from datetime import date
from pathlib import Path
from typing import Any


def canonicalize_name(value: str) -> str:
    return re.sub(r"[-_.]+", "-", value).lower()


def license_atoms(value: str) -> list[str]:
    normalized = value.strip()
    if normalized.startswith("MIT License") and "Permission is hereby granted" in normalized:
        return ["MIT"]
    return [
        atom.strip()
        for atom in re.split(r"\s+(?:AND|OR)\s+|;\s*", normalized)
        if atom.strip()
    ]


def validate_licenses(
    inventory: list[dict[str, Any]],
    sbom: dict[str, Any],
    policy: dict[str, Any],
    *,
    today: date | None = None,
) -> dict[str, Any]:
    runtime_names = {
        canonicalize_name(component["name"])
        for component in sbom.get("components", [])
        if component.get("type") == "library" and component.get("name")
    }
    allowed = set(policy.get("allowed_license_atoms", []))
    review_atoms = set(policy.get("review_required_atoms", []))
    overrides = {
        canonicalize_name(name): value
        for name, value in policy.get("package_overrides", {}).items()
    }
    current_date = today or date.today()

    checked: list[dict[str, Any]] = []
    failures: list[str] = []
    reviews: list[str] = []

    for item in sorted(inventory, key=lambda row: canonicalize_name(row["Name"])):
        name = canonicalize_name(item["Name"])
        if name not in runtime_names:
            continue

        version = str(item["Version"])
        raw_license = str(item.get("License") or "UNKNOWN").strip()
        effective_license = raw_license
        override = overrides.get(name)
        override_failure: str | None = None

        if raw_license.upper() == "UNKNOWN" and override:
            permitted_versions = set(override.get("versions", []))
            expires = date.fromisoformat(override["expires"])
            reviewed = date.fromisoformat(override["reviewed"])
            source = str(override.get("sources", {}).get(version, ""))
            reason = str(override.get("reason", "")).strip()
            if version not in permitted_versions:
                override_failure = f"{name}=={version}: override does not cover this version"
            elif reviewed > current_date:
                override_failure = f"{name}=={version}: override review date is in the future"
            elif expires <= reviewed or (expires - reviewed).days > 366:
                override_failure = f"{name}=={version}: override review window is invalid"
            elif expires < current_date:
                override_failure = f"{name}=={version}: license override expired on {expires}"
            elif not source.startswith("https://"):
                override_failure = f"{name}=={version}: version-specific source must use HTTPS"
            elif len(reason) < 20:
                override_failure = f"{name}=={version}: override reason is incomplete"
            else:
                effective_license = str(override["license"])

        if override_failure:
            failures.append(override_failure)
        else:
            atoms = license_atoms(effective_license)
            unsupported = sorted(set(atoms) - allowed)
            if unsupported:
                failures.append(
                    f"{name}=={version}: unsupported license atoms {unsupported} "
                    f"(reported: {raw_license!r})"
                )
            package_reviews = sorted(set(atoms) & review_atoms)
            if package_reviews:
                reviews.append(f"{name}=={version}: {', '.join(package_reviews)}")

        checked.append(
            {
                "name": name,
                "version": version,
                "reported_license": raw_license,
                "effective_license": effective_license,
                "override_applied": effective_license != raw_license,
            }
        )

    if not checked:
        failures.append("license inventory contains no runtime SBOM components")

    return {
        "status": "pass" if not failures else "fail",
        "checked_packages": len(checked),
        "review_required": reviews,
        "failures": failures,
        "packages": checked,
    }


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--sbom", type=Path, required=True)
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()

    result = validate_licenses(
        _load_json(args.inventory),
        _load_json(args.sbom),
        _load_json(args.policy),
    )
    args.report.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print(f"Checked runtime licenses: {result['checked_packages']}")
    for review in result["review_required"]:
        print(f"REVIEW REQUIRED: {review}")
    for failure in result["failures"]:
        print(f"POLICY FAILURE: {failure}")
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
