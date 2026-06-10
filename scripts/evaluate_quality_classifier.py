from __future__ import annotations

import argparse
from pathlib import Path


QUALITY_CLASSES = ("sharp", "acceptable", "marginal")


def _load_model(weights: str):
    try:
        from ultralytics import YOLO
    except Exception as exc:
        raise SystemExit(
            "Ultralytics is not installed in this environment. Install requirements.txt first."
        ) from exc

    return YOLO(weights)


def _resolve_weights_path(weights: Path) -> Path:
    if weights.exists():
        return weights

    # Fallback to the newest training artifact when path assumptions differ.
    candidates = sorted(Path("runs").glob("**/weights/best.pt"), key=lambda p: p.stat().st_mtime, reverse=True)
    if candidates:
        print(f"weights_not_found: {weights}")
        print(f"using_latest_weights: {candidates[0]}")
        return candidates[0]

    raise SystemExit(
        "Could not find weights file. Expected path does not exist and no runs/**/weights/best.pt was found."
    )


def _evaluate_split(model, data_root: Path, split: str) -> None:
    results = model.val(data=str(data_root), split=split, task="classify", verbose=False)
    print(f"[{split}] top1={getattr(results, 'top1', 'n/a')} top5={getattr(results, 'top5', 'n/a')}")


def _predict_demo_images(model, demo_images: list[Path]) -> None:
    if not demo_images:
        return

    print("demo_predictions:")
    predictions = model.predict(source=[str(path) for path in demo_images], task="classify", verbose=False)
    for image_path, prediction in zip(demo_images, predictions):
        probs = getattr(prediction, "probs", None)
        if probs is None:
            print(f"- {image_path.name}: no probabilities returned")
            continue

        top_idx = int(probs.top1)
        top_conf_raw = probs.top1conf
        top_conf = float(top_conf_raw.item() if hasattr(top_conf_raw, "item") else top_conf_raw)
        names = getattr(prediction, "names", {})
        label = names.get(top_idx, top_idx) if isinstance(names, dict) else names[top_idx]
        print(f"- {image_path.name}: {label} ({top_conf:.3f})")


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate the YOLO quality classifier on held-out data and demo images.")
    parser.add_argument("--data-root", type=Path, default=Path("data/quality_split"))
    parser.add_argument("--weights", type=Path, default=Path("runs/classify/yolo_quality_classifier/weights/best.pt"))
    parser.add_argument("--demo-image", type=Path, action="append", default=[], help="Optional fresh image to test")
    args = parser.parse_args()

    if not args.data_root.exists():
        raise SystemExit(f"Split dataset root not found: {args.data_root}")

    weights_path = _resolve_weights_path(args.weights)
    model = _load_model(str(weights_path))

    print("quality_classes:", ", ".join(QUALITY_CLASSES))
    _evaluate_split(model, args.data_root, "val")
    _evaluate_split(model, args.data_root, "test")
    _predict_demo_images(model, args.demo_image)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
