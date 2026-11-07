#!/usr/bin/env python3
"""
High-Resolution Vehicle Background Removal & Thumbnail Pipeline using BiRefNet.
Accelerated via Apple Silicon Mac GPU (MPS) or CUDA when available.

Usage:
  # Single image from local file or web URL
  uv run --with transformers --with torch --with torchvision --with pillow --with timm --with einops --with kornia \
    scripts/tooling/birefnet_segment.py --input "path/or/url.jpg" --output "output.png" --facing-left

  # Or process batch:
  uv run --with transformers --with torch --with torchvision --with pillow --with timm --with einops --with kornia \
    scripts/tooling/birefnet_segment.py --batch batch.json
"""

import argparse
import os
import sys
import time
import urllib.request
import numpy as np
from PIL import Image

try:
    import torch
    from torchvision import transforms
    from transformers import AutoModelForImageSegmentation
except ImportError:
    print("Error: PyTorch and Transformers required. Run with:")
    print("  uv run --with transformers --with torch --with torchvision --with pillow --with timm --with einops --with kornia python ...")
    sys.exit(1)

CANVAS_WIDTH = 1400
CANVAS_HEIGHT = 475
TARGET_VEHICLE_WIDTH = 1380
BASELINE_MARGIN_BOTTOM = 10


def get_device():
    if torch.backends.mps.is_available():
        return torch.device("mps")
    if torch.cuda.is_available():
        return torch.device("cuda")
    return torch.device("cpu")


def load_model(device):
    print(f"Loading BiRefNet on {device}...")
    model = AutoModelForImageSegmentation.from_pretrained("ZhengPeng7/BiRefNet", trust_remote_code=True)
    model.to(device).float()
    model.eval()
    return model


def segment_image(image: Image.Image, model, device) -> Image.Image:
    w, h = image.size
    transform = transforms.Compose([
        transforms.Resize((1024, 1024)),
        transforms.ToTensor(),
        transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
    ])
    tensor = transform(image.convert("RGB")).unsqueeze(0).to(device).float()
    with torch.no_grad():
        preds = model(tensor)[-1].sigmoid().cpu()
    pred = preds[0].squeeze()
    mask = transforms.ToPILImage()(pred).resize((w, h), Image.Resampling.BILINEAR)

    out = image.convert("RGBA").copy()
    out.putalpha(mask)
    return out


def standardize_canvas(cutout: Image.Image, facing_left: bool = True) -> Image.Image:
    arr = np.array(cutout)
    alpha = arr[:, :, 3]
    y_idxs, x_idxs = np.where(alpha > 15)
    if len(y_idxs) == 0:
        return cutout

    crop = cutout.crop((x_idxs.min(), y_idxs.min(), x_idxs.max() + 1, y_idxs.max() + 1))
    if facing_left:
        crop = crop.transpose(Image.FLIP_LEFT_RIGHT)

    scale = TARGET_VEHICLE_WIDTH / crop.width
    new_w = TARGET_VEHICLE_WIDTH
    new_h = int(crop.height * scale)
    resized = crop.resize((new_w, new_h), Image.Resampling.LANCZOS)

    canvas = Image.new("RGBA", (CANVAS_WIDTH, CANVAS_HEIGHT), (0, 0, 0, 0))
    pos_x = (CANVAS_WIDTH - new_w) // 2
    pos_y = CANVAS_HEIGHT - new_h - BASELINE_MARGIN_BOTTOM
    canvas.paste(resized, (pos_x, max(0, pos_y)), resized)
    return canvas


def main():
    parser = argparse.ArgumentParser(description="BiRefNet GPU Vehicle Cutout Pipeline")
    parser.add_argument("--input", help="Image URL or local file path")
    parser.add_argument("--output", help="Output PNG path")
    parser.add_argument("--facing-left", action="store_true", help="Ensure vehicle faces left")
    args = parser.parse_args()

    if not args.input or not args.output:
        parser.print_help()
        sys.exit(1)

    device = get_device()
    model = load_model(device)

    t0 = time.time()
    if args.input.startswith("http://") or args.input.startswith("https://"):
        req = urllib.request.Request(args.input, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req) as resp:
            raw_img = Image.open(resp)
    else:
        raw_img = Image.open(args.input)

    cutout = segment_image(raw_img, model, device)
    canvas = standardize_canvas(cutout, facing_left=args.facing_left)

    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    canvas.save(args.output, optimize=True)
    print(f"✓ Saved {args.output} in {time.time()-t0:.2f}s on {device}")


if __name__ == "__main__":
    main()
