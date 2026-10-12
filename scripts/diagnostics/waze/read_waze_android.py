"""Read the currently open Waze station detail through Android accessibility."""
import argparse
import json
import subprocess
import xml.etree.ElementTree as ET
from datetime import datetime, timezone


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--serial", default="emulator-5554")
    args = parser.parse_args()
    adb = ["adb", "-s", args.serial]
    remote = "/sdcard/gaswise-waze-read.xml"
    subprocess.run(adb + ["shell", "rm", "-f", remote], check=True)
    subprocess.run(adb + ["shell", "uiautomator", "dump", remote],
                   check=True, capture_output=True)
    xml = subprocess.check_output(adb + ["exec-out", "cat", remote])
    root = ET.fromstring(xml)
    texts = [n.get("text") for n in root.iter("node") if n.get("text")]
    fuel_types = {"Regular", "Midgrade", "Premium", "Diesel", "E85"}
    prices = []
    for i, text in enumerate(texts[:-1]):
        if text in fuel_types:
            try:
                price = float(texts[i + 1])
            except ValueError:
                continue
            prices.append({"fuel_type": text, "price": price,
                           "payment_type": "unknown", "octane": None})
    result = {"captured_at": datetime.now(timezone.utc).isoformat(),
              "source": "waze_android_accessibility", "prices": prices,
              "update_labels": [t for t in texts if t.startswith("Updated")],
              "screen_text": texts}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not prices:
        raise SystemExit("No fuel prices found. Open a station's Gas prices detail first.")


if __name__ == "__main__":
    main()
