from __future__ import annotations

from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS_DIR = ROOT / "db" / "migrations"
MIGRATION_PATTERN = re.compile(r"^(?P<number>\d{3})_.+\.sql$")


def main() -> int:
    files = sorted(path for path in MIGRATIONS_DIR.glob("*.sql"))
    if not files:
        print("No migration files found.", file=sys.stderr)
        return 1

    numbers: list[int] = []
    for path in files:
        match = MIGRATION_PATTERN.match(path.name)
        if not match:
            print(f"Invalid migration filename: {path.name}", file=sys.stderr)
            return 1
        numbers.append(int(match.group("number")))

    expected = list(range(numbers[0], numbers[-1] + 1))
    if numbers != expected:
        print(
            f"Migration numbering is not sequential. Found {numbers}, expected {expected}.",
            file=sys.stderr,
        )
        return 1

    print(f"Validated {len(files)} sequential migration files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
