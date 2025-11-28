"""Swiss Ephemeris helper functions for astrological calculations."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Tuple
from zoneinfo import ZoneInfo

import swisseph as swe


class SwissEphEngine:
    """Wrapper around the Swiss Ephemeris library.

    The class centralises common configuration and helper methods to
    calculate astronomical values from user supplied payloads.
    """

    def __init__(self, ephemeris_path: str | None = None) -> None:
        """Initialise the ephemeris path.

        Args:
            ephemeris_path: Optional path to the ephemeris files. Defaults to
                the bundled ``ephe`` directory.
        """

        swe.set_ephe_path(ephemeris_path or "ephe")

    def calc_planet_longitudes(self, jd_ut: float) -> Dict[str, float]:
        """Calculate ecliptic longitudes for the classical planets.

        Args:
            jd_ut: Julian day in Universal Time.

        Returns:
            Dictionary with lowercase planet names mapped to their longitude in
            degrees.
        """

        planet_constants = {
            "sun": swe.SUN,
            "moon": swe.MOON,
            "mercury": swe.MERCURY,
            "venus": swe.VENUS,
            "mars": swe.MARS,
            "jupiter": swe.JUPITER,
            "saturn": swe.SATURN,
            "uranus": swe.URANUS,
            "neptune": swe.NEPTUNE,
            "pluto": swe.PLUTO,
        }

        planet_positions: Dict[str, float] = {}
        for name, body in planet_constants.items():
            position, _ = swe.calc_ut(jd_ut, body, swe.FLG_SWIEPH)
            planet_positions[name] = position[0] % 360.0

        return planet_positions

    @staticmethod
    def _zodiac_for_longitude(longitude: float) -> Tuple[str, float]:
        """Return the zodiac sign and the position within that sign.

        Args:
            longitude: Ecliptic longitude in degrees (0-360).

        Returns:
            A tuple of the sign name (German) and the longitude inside the sign.
        """

        signs = (
            "Widder",
            "Stier",
            "Zwillinge",
            "Krebs",
            "Löwe",
            "Jungfrau",
            "Waage",
            "Skorpion",
            "Schütze",
            "Steinbock",
            "Wassermann",
            "Fische",
        )

        normalized = longitude % 360.0
        index = int(normalized // 30) % 12
        position_in_sign = normalized % 30.0

        return signs[index], position_in_sign

    def calc_birth_chart_from_payload(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate a birth chart from a payload containing birth data.

        The payload expects the keys ``date`` (``YYYY-MM-DD``), ``time``
        (``HH:MM`` or ``HH:MM:SS``), ``timezone`` (IANA name), ``latitude`` and
        ``longitude``.
        """

        date_str = payload["date"]
        time_str = payload.get("time", "00:00")
        timezone_name = payload.get("timezone", "UTC")

        local_zone = ZoneInfo(timezone_name)
        dt_local = datetime.fromisoformat(f"{date_str}T{time_str}")
        if dt_local.tzinfo is None:
            dt_local = dt_local.replace(tzinfo=local_zone)
        else:
            dt_local = dt_local.astimezone(local_zone)

        dt_utc = dt_local.astimezone(timezone.utc)
        hour_utc = (
            dt_utc.hour
            + dt_utc.minute / 60
            + dt_utc.second / 3600
            + dt_utc.microsecond / 3_600_000_000
        )

        jd_ut = swe.julday(dt_utc.year, dt_utc.month, dt_utc.day, hour_utc, swe.GREG_CAL)
        planets = self.calc_planet_longitudes(jd_ut)
        planet_signs = {
            name: self._zodiac_for_longitude(longitude) for name, longitude in planets.items()
        }

        return {
            "jd_ut": jd_ut,
            "date": date_str,
            "time": time_str,
            "timezone": timezone_name,
            "latitude": payload.get("latitude"),
            "longitude": payload.get("longitude"),
            "name": payload.get("name", "Unbekannte Person"),
            "planets": planets,
            "planet_signs": planet_signs,
        }


if __name__ == "__main__":
    engine = SwissEphEngine()

    berlin_payload = {
        "name": "Dein Name",  # Trage hier deinen Namen ein.
        "date": "1990-01-01",
        "time": "12:00",
        "timezone": "Europe/Berlin",
        "latitude": 52.52,
        "longitude": 13.405,
    }

    chart = engine.calc_birth_chart_from_payload(berlin_payload)

    print("Berechnetes Geburtshoroskop (Berlin)")
    print(f"Name: {chart['name']}")
    print(f"Julianischer Tag (UT): {chart['jd_ut']:.6f}")

    sun_long = chart["planets"]["sun"]
    sun_sign, sun_pos = chart["planet_signs"]["sun"]
    moon_long = chart["planets"]["moon"]
    moon_sign, moon_pos = chart["planet_signs"]["moon"]

    print(f"Sonnenlänge: {sun_long:.6f}° ({sun_pos:.2f}° {sun_sign})")
    print(f"Mondlänge: {moon_long:.6f}° ({moon_pos:.2f}° {moon_sign})")

    print("Planetenpositionen:")
    for planet, longitude in chart["planets"].items():
        sign, pos_in_sign = chart["planet_signs"][planet]
        print(
            f"  {planet.capitalize():<8}: {longitude:.6f}° – {pos_in_sign:.2f}° {sign}"
        )
