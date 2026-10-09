"""Run inside the actual customer image, before mounting runtime JWT secrets."""
from pathlib import Path


def check_customer_image(root: Path):
    forbidden = ["tools/license_issuer", ".secrets", ".leadhunter-state", ".superpowers", "src/prompts.py"]
    for relative in forbidden:
        if (root / relative).exists():
            raise SystemExit("Customer image includes private development material.")
    for extension in ("*.pem", "*.key", "*.p12", "*.pfx", "*.lh"):
        for path in root.rglob(extension):
            # These pinned dependencies ship public TLS/authentication material.
            # They are unrelated to the owner's licensing keys.
            relative = path.relative_to(root).as_posix()
            public_dependency = (relative.startswith(".venv/") and "/site-packages/" in relative and
                (relative.endswith("/certifi/cacert.pem") or
                 relative.endswith("/litellm/proxy/auth/public_key.pem")))
            if public_dependency and b"PRIVATE KEY" not in path.read_bytes():
                continue
            raise SystemExit("Customer image includes key or license files.")


def main():
    check_customer_image(Path("/app"))
    print("Customer image: issuer, private keys, license files and local state absent.")


if __name__ == "__main__":
    main()
