from __future__ import annotations

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from astrobot.swisseph_engine import SwissEphEngine


def main() -> None:
    engine = SwissEphEngine()
    payload = {
        "name": "Demo",
        "date": "1988-04-16",
        "time": "20:09",
        "timezone": "Europe/Berlin",
        "latitude": 50.9230079,
        "longitude": 6.8088915,
    }
    print(engine.calc_birth_chart_from_payload(payload)["planet_signs"]["sun"])


if __name__ == "__main__":
    main()
