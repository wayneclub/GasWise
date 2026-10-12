"""Query Waze over HTTP; no App, browser or ADB required."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "backend"))
from gaswise.providers.waze.protocol import main  # noqa: E402

if __name__ == "__main__":
    main()
