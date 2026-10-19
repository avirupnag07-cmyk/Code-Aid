"""Build the public corrected fixture ZIP reproducibly, without executing it."""

import argparse
import hashlib
import io
from pathlib import Path
import stat
import zipfile


PREFIX = "corrected-python-project"
FILES = ("README.md", "calculator.py", "metadata.json", "traceback.txt")
TIMESTAMP = (1980, 1, 1, 0, 0, 0)


def build_archive(fixtures: Path) -> bytes:
    """Use an explicit manifest and fixed headers, independent of host metadata."""
    source = fixtures / PREFIX
    if source.is_symlink() or not source.is_dir():
        raise ValueError("fixture source must be a regular directory")
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_STORED) as archive:
        archive.comment = b""
        for name in sorted(FILES):
            path = source / name
            if path.is_symlink() or not path.is_file():
                raise ValueError("fixture member must be a regular file: " + name)
            content = path.read_bytes()
            content.decode("utf-8")
            entry = zipfile.ZipInfo(PREFIX + "/" + name, date_time=TIMESTAMP)
            entry.create_system = 3
            entry.create_version = 20
            entry.extract_version = 20
            entry.compress_type = zipfile.ZIP_STORED
            entry.external_attr = (stat.S_IFREG | 0o644) << 16
            entry.internal_attr = 0
            entry.extra = b""
            entry.comment = b""
            archive.writestr(entry, content)
    return output.getvalue()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true",
                        help="verify existing ZIP equals the reproducible build")
    args = parser.parse_args()
    fixtures = Path(__file__).resolve().parent
    destination = fixtures / (PREFIX + ".zip")
    content = build_archive(fixtures)
    if args.check:
        if not destination.is_file() or destination.read_bytes() != content:
            parser.exit(1, "ZIP missing or stale; run this script without --check\n")
    else:
        destination.write_bytes(content)
    print("sha256 " + hashlib.sha256(content).hexdigest() + "  " + destination.name)


if __name__ == "__main__":
    main()
