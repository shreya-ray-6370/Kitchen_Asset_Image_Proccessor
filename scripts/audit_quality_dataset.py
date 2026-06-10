from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
QUALITY_CLASSES = ("sharp", "acceptable", "marginal")


def count_images(folder: Path) -> int:
    return sum(1 for path in folder.rglob("*") if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS)


def audit_dataset(dataset_root: Path) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for class_name in QUALITY_CLASSES:
        class_dir = dataset_root / class_name
        if class_dir.exists():
            counts[class_name] = count_images(class_dir)
        else:
            counts[class_name] = 0
    return dict(counts)


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit the quality-classification dataset layout.")
    parser.add_argument("dataset_root", type=Path, help="Root folder that contains sharp/acceptable/marginal")
    args = parser.parse_args()

    dataset_root = args.dataset_root
    if not dataset_root.exists():
        raise SystemExit(f"Dataset root not found: {dataset_root}")

    counts = audit_dataset(dataset_root)
    total = sum(counts.values())

    print(f"Dataset root: {dataset_root}")
    for class_name in QUALITY_CLASSES:
        print(f"{class_name}: {counts[class_name]}")
    print(f"total: {total}")

    missing = [name for name, value in counts.items() if value == 0]
    if missing:
        print(f"warning: missing or empty classes: {', '.join(missing)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
