import urllib.request
import os
import numpy as np
from PIL import Image
from rembg import remove, new_session

OUTPUT_DIR = "frontend/public/vehicles"
os.makedirs(OUTPUT_DIR, exist_ok=True)

session = new_session("u2net")

# Tesla configurations
# Model 3
m3_colors = {
    "pearl_white": "$PPSW",
    "solid_black": "$PBSB",
    "stealth_grey": "$PN01",
    "deep_blue": "$PPSB",
    "ultra_red": "$PR01",
}

# Model Y
my_colors = {
    "pearl_white": "$PPSW",
    "solid_black": "$PBSB",
    "stealth_grey": "$PN01",
    "deep_blue": "$PPSB",
    "ultra_red": "$PR01",
    "quicksilver": "$PMNG",
}

def process_car(model_type, color_name, option_code, filename):
    out_path = os.path.join(OUTPUT_DIR, filename)
    if os.path.exists(out_path):
        print(f"Skipping {filename}, already exists.")
        return

    print(f"Fetching & processing {model_type} {color_name}...")
    if model_type == "m3":
        url = f"https://static-assets.tesla.com/configurator/compositor?context=design_studio_2&options=$MT351,{option_code},$W38A,$IPB1&view=SIDE&model=m3&size=1440"
    else:
        url = f"https://static-assets.tesla.com/configurator/compositor?context=design_studio_2&options=$MTY22,{option_code},$WY20P,$INPB0&view=SIDE&model=my&size=1440"

    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    tmp_jpg = f"/tmp/{model_type}_{color_name}.jpg"
    with urllib.request.urlopen(req) as resp, open(tmp_jpg, "wb") as f:
        f.write(resp.read())

    # Background removal
    raw_img = Image.open(tmp_jpg)
    nobg = remove(raw_img, session=session)

    # Find bounding box
    arr = np.array(nobg)
    alpha = arr[:, :, 3]
    y_idxs, x_idxs = np.where(alpha > 15)
    if len(y_idxs) == 0:
        print(f"Error: Empty alpha for {filename}")
        return

    ymin, ymax = y_idxs.min(), y_idxs.max()
    xmin, xmax = x_idxs.min(), x_idxs.max()

    crop = nobg.crop((xmin, ymin, xmax + 1, ymax + 1))

    # Standardize to 1400 x 500
    target_width = 1100
    scale = target_width / crop.width
    new_w = target_width
    new_h = int(crop.height * scale)
    resized = crop.resize((new_w, new_h), Image.Resampling.LANCZOS)

    canvas = Image.new("RGBA", (1400, 500), (0, 0, 0, 0))
    pos_x = (1400 - new_w) // 2
    # Baseline ground wheels around y = 435
    pos_y = 435 - new_h
    canvas.paste(resized, (pos_x, pos_y), resized)

    canvas.save(out_path, optimize=True)
    print(f"Saved: {out_path} ({os.path.getsize(out_path) // 1024} KB)")

# Process Model 3
for color_name, opt in m3_colors.items():
    process_car("m3", color_name, opt, f"tesla_model_3_{color_name}.png")

# Process Model Y
for color_name, opt in my_colors.items():
    process_car("my", color_name, opt, f"tesla_model_y_{color_name}.png")

print("All Tesla models completed successfully!")
