"""Extract one accepted run's actual final frame without generating media."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from lfo.canvas.accepted_tail import extract_accepted_tail
from lfo.canvas.client import CanvasClient
from lfo.canvas.settings import CanvasSettings

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_id")
    parser.add_argument("--url")
    args = parser.parse_args()
    client = CanvasClient(CanvasSettings.resolve(Path(__file__).resolve().parents[1]), args.url)
    print(json.dumps(extract_accepted_tail(client, args.run_id), ensure_ascii=False, indent=2))
