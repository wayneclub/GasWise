#!/usr/bin/env python3
"""
Automated Vehicle Thumbnail Generator Pipeline for GasWise.

Usage:
  # Process a single image from URL or file
  python scripts/tooling/generate_vehicle_thumbnails.py \
    --input "https://example.com/car.jpg" \
    --model "tesla_model_y" \
    --color "ultra_red"

  # Or process a batch configuration file:
  python scripts/tooling/generate_vehicle_thumbnails.py --batch batch_vehicles.json
"""

import argparse
import json
import os
import sys
import urllib.request
import numpy as np
from PIL import Image

try:
    from rembg import remove, new_session
except ImportError:
    print("Error: rembg is required. Run with the rembg virtual environment.")
    sys.exit(1)

CANVAS_WIDTH = 1400
CANVAS_HEIGHT = 500
TARGET_VEHICLE_WIDTH = 1100
GROUND_BASELINE_Y = 435
DEFAULT_OUTPUT_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "../../frontend/public/vehicles")
)


def process_image(
    input_source: str,
    output_path: str,
    session=None,
    force: bool = False,
) -> bool:
    if os.path.exists(output_path) and not force:
        print(f"Skipping {os.path.basename(output_path)}, already exists.")
        return True

    print(f"Processing {input_source} -> {output_path}...")

    # 1. Acquire raw image
    if input_source.startswith("http://") or input_source.startswith("https://"):
        req = urllib.request.Request(
            input_source,
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            },
        )
        try:
            with urllib.request.urlopen(req) as resp:
                raw_img = Image.open(resp).convert("RGB")
        except Exception as e:
            print(f"Failed to fetch {input_source}: {e}")
            return False
    else:
        if not os.path.exists(input_source):
            print(f"File not found: {input_source}")
            return False
        raw_img = Image.open(input_source).convert("RGB")

    # 2. AI Background Removal
    if session is None:
        session = new_session("u2net")
    nobg = remove(raw_img, session=session)

    # 3. Find bounding box of vehicle
    arr = np.array(nobg)
    alpha = arr[:, :, 3]
    y_idxs, x_idxs = np.where(alpha > 15)
    if len(y_idxs) == 0:
        print(f"Error: Empty alpha channel for {input_source}")
        return False

    ymin, ymax = y_idxs.min(), y_idxs.max()
    xmin, xmax = x_idxs.min(), x_idxs.max()

    crop = nobg.crop((xmin, ymin, xmax + 1, ymax + 1))

    # 4. Standardize onto 1400 x 500 canvas with baseline alignment
    scale = TARGET_VEHICLE_WIDTH / crop.width
    new_w = TARGET_VEHICLE_WIDTH
    new_h = int(crop.height * scale)
    resized = crop.resize((new_w, new_h), Image.Resampling.LANCZOS)

    canvas = Image.new("RGBA", (CANVAS_WIDTH, CANVAS_HEIGHT), (0, 0, 0, 0))
    pos_x = (CANVAS_WIDTH - new_w) // 2
    pos_y = GROUND_BASELINE_Y - new_h
    canvas.paste(resized, (pos_x, pos_y), resized)

    # 5. Save optimized output
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    canvas.save(output_path, format="PNG", optimize=True)
    size_kb = os.path.getsize(output_path) // 1024
    print(f"✓ Saved {output_path} ({size_kb} KB)")
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Automated AI Background Removal and Vehicle Thumbnail Generator"
    )
    parser.add_argument("--input", help="Image URL or local file path")
    parser.add_argument("--model", help="Model key, e.g. tesla_model_y")
    parser.add_argument("--color", help="Color key, e.g. ultra_red")
    parser.add_argument("--output", help="Explicit output path")
    parser.add_argument("--batch", help="Path to JSON file with batch definitions")
    parser.add_argument("--force", action="store_true", help="Overwrite existing files")

    args = parser.parse_args()

    session = new_session("u2net")

    if args.batch:
        with open(args.batch, "r", encoding="utf-8") as f:
            items = json.load(f)
        for item in items:
            model = item["model"]
            color = item["color"]
            url = item["url"]
            out_file = os.path.join(
                DEFAULT_OUTPUT_DIR, f"{model}_{color}.png"
            )
            process_image(url, out_file, session=session, force=args.force)
        return

    if not args.input or not (args.output or (args.model and args.color)):
        parser.print_help()
        sys.exit(1)

    out_file = args.output
    if not out_file:
        out_file = os.path.join(
            DEFAULT_OUTPUT_DIR, f"{args.model}_{args.color}.png"
        )

    success = process_image(args.input, out_file, session=session, force=args.force)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
