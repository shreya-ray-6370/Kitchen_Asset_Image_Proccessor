from __future__ import annotations

import argparse
import random
import shutil
from pathlib import Path


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
QUALITY_CLASSES = ("sharp", "acceptable", "marginal")


def _collect_images(class_dir: Path) -> list[Path]:
    return sorted(path for path in class_dir.iterdir() if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS)


def prepare_split(dataset_root: Path, split_root: Path, train_ratio: float, val_ratio: float, seed: int) -> None:
    if train_ratio <= 0 or val_ratio <= 0:
        raise ValueError("train_ratio and val_ratio must be greater than zero")
    if train_ratio + val_ratio >= 1.0:
        raise ValueError("train_ratio + val_ratio must be less than 1.0")

    random.seed(seed)

    if split_root.exists():
        shutil.rmtree(split_root)
    for split_name in ("train", "val", "test"):
        for class_name in QUALITY_CLASSES:
            (split_root / split_name / class_name).mkdir(parents=True, exist_ok=True)

    for class_name in QUALITY_CLASSES:
        class_dir = dataset_root / class_name
        images = _collect_images(class_dir)
        if not images:
            continue

        random.shuffle(images)
        total = len(images)
        train_end = max(1, int(total * train_ratio))
        val_end = max(train_end + 1, int(total * (train_ratio + val_ratio)))
        val_end = min(val_end, total - 1) if total > 2 else total

        train_images = images[:train_end]
        val_images = images[train_end:val_end]
        test_images = images[val_end:]

        if not val_images and test_images:
            val_images = test_images[:1]
            test_images = test_images[1:]
        if not test_images and val_images:
            test_images = val_images[-1:]
            val_images = val_images[:-1]

        for source_path in train_images:
            shutil.copy2(source_path, split_root / "train" / class_name / source_path.name)
        for source_path in val_images:
            shutil.copy2(source_path, split_root / "val" / class_name / source_path.name)
        for source_path in test_images:
            shutil.copy2(source_path, split_root / "test" / class_name / source_path.name)


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare and train a YOLO classification model for image quality.")
    parser.add_argument("--dataset-root", type=Path, default=Path(r"C:\projects\data_set_creation\dataset"))
    parser.add_argument("--split-root", type=Path, default=Path("data/quality_split"))
    parser.add_argument("--model", type=str, default="yolo26n-cls.pt")
    parser.add_argument("--epochs", type=int, default=30)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--batch", type=int, default=16)
    parser.add_argument("--train-ratio", type=float, default=0.7)
    parser.add_argument("--val-ratio", type=float, default=0.2)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--project", type=Path, default=None, help="Optional Ultralytics project directory")
    parser.add_argument("--name", type=str, default="yolo_quality_classifier")
    args = parser.parse_args()

    dataset_root = args.dataset_root
    if not dataset_root.exists():
        raise SystemExit(f"Dataset root not found: {dataset_root}")

    prepare_split(dataset_root, args.split_root, args.train_ratio, args.val_ratio, args.seed)

    try:
        from ultralytics import YOLO
    except Exception as exc:
        raise SystemExit(
            "Ultralytics is not installed in this environment. Install requirements.txt first."
        ) from exc

    model = YOLO(args.model)
    train_kwargs = dict(
        data=str(args.split_root),
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=args.batch,
        name=args.name,
        task="classify",
    )
    if args.project is not None:
        train_kwargs["project"] = str(args.project)

    results = model.train(**train_kwargs)
    save_dir = getattr(results, "save_dir", None)
    if save_dir:
        print(f"training_output_dir: {save_dir}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
