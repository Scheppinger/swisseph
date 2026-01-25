"""Swiss Ephemeris helper functions for astrological calculations."""

from __future__ import annotations

from datetime import datetime, timezone
from itertools import combinations
from typing import Any, Dict, List, Tuple
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

    def calc_planet_longitudes(
        self, jd_ut: float, latitude: float | None = None, longitude: float | None = None
    ) -> Dict[str, float]:
        """Calculate ecliptic longitudes for planets and key points.

        Args:
            jd_ut: Julian day in Universal Time.
            latitude: Geographic latitude in degrees (required for AC/MC).
            longitude: Geographic longitude in degrees (required for AC/MC).

        Returns:
            Dictionary with lowercase planet names mapped to their longitude in
            degrees. Includes Chiron, Lilith (mean lunar apogee), the lunar
            node (true) and, if a location is supplied, Ascendant (``ac``)
            and Midheaven (``mc``).
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
            "chiron": swe.CHIRON,
            "lilith": swe.MEAN_APOG,
            "knoten": swe.TRUE_NODE,
        }

        planet_positions: Dict[str, float] = {}
        for name, body in planet_constants.items():
            position, _ = swe.calc_ut(jd_ut, body, swe.FLG_SWIEPH)
            planet_positions[name] = position[0] % 360.0

        if latitude is not None and longitude is not None:
            _cusps, ascmc = swe.houses_ex(jd_ut, latitude, longitude, b"P", swe.FLG_SWIEPH)
            planet_positions["ac"] = ascmc[0] % 360.0
            planet_positions["mc"] = ascmc[1] % 360.0

        return planet_positions

    @staticmethod
    def calc_aspects(planet_positions: Dict[str, float]) -> List[Dict[str, Any]]:
        """Calculate major aspects between planetary positions.

        The function considers conjunction, sextile, square, trine and
        opposition with commonly used orb allowances. The orb describes the
        deviation from the exact aspect angle.

        Args:
            planet_positions: Mapping of point names to longitudes.

        Returns:
            A list of aspects with involved bodies, aspect name, target angle
            and the current orb (absolute deviation in degrees).
        """

        aspect_definitions = {
            "Konjunktion": {"angle": 0.0, "orb": 8.0},
            "Sextil": {"angle": 60.0, "orb": 5.0},
            "Quadrat": {"angle": 90.0, "orb": 7.0},
            "Trigon": {"angle": 120.0, "orb": 7.0},
            "Opposition": {"angle": 180.0, "orb": 8.0},
        }

        def angular_distance(angle1: float, angle2: float) -> float:
            diff = abs((angle1 - angle2) % 360.0)
            return diff if diff <= 180.0 else 360.0 - diff

        aspects: List[Dict[str, Any]] = []
        for body1, body2 in combinations(planet_positions.keys(), 2):
            separation = angular_distance(planet_positions[body1], planet_positions[body2])
            for name, params in aspect_definitions.items():
                deviation = abs(separation - params["angle"])
                if deviation <= params["orb"]:
                    aspects.append(
                        {
                            "body1": body1,
                            "body2": body2,
                            "aspect": name,
                            "angle": params["angle"],
                            "orb": deviation,
                            "separation": separation,
                        }
                    )

        aspects.sort(key=lambda asp: asp["orb"])
        return aspects

    @staticmethod
    def calc_houses(jd_ut: float, latitude: float, longitude: float) -> Dict[str, Any]:
        """Calculate the 12 house cusps using Placidus (western standard).

        Args:
            jd_ut: Julian day in Universal Time.
            latitude: Geographic latitude in degrees.
            longitude: Geographic longitude in degrees.

        Returns:
            A dictionary containing a list of 12 house cusps (in degrees) and
            auxiliary angles (Ascendant and Midheaven).
        """

        cusps, ascmc = swe.houses_ex(jd_ut, latitude, longitude, b"P", swe.FLG_SWIEPH)
        normalized_cusps = [(cusp % 360.0) for cusp in cusps[:12]]
        return {
            "cusps": normalized_cusps,
            "ac": ascmc[0] % 360.0,
            "mc": ascmc[1] % 360.0,
        }

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
        ``longitude``. Latitude/longitude are required so Ascendant (AC),
        Midheaven (MC) and the 12 Placidus house cusps can be calculated.
        """

        date_str = payload["date"]
        time_str = payload.get("time", "00:00")
        timezone_name = payload.get("timezone", "UTC")

        latitude = payload.get("latitude")
        longitude = payload.get("longitude")
        if latitude is None or longitude is None:
            raise ValueError("Latitude and longitude are required to compute AC and MC")

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
        houses = self.calc_houses(jd_ut, latitude, longitude)
        planets = self.calc_planet_longitudes(jd_ut, latitude=latitude, longitude=longitude)
        planet_signs = {
            name: self._zodiac_for_longitude(longitude) for name, longitude in planets.items()
        }
        house_signs: List[Tuple[str, float]] = [
            self._zodiac_for_longitude(cusp_longitude) for cusp_longitude in houses["cusps"]
        ]
        aspects = self.calc_aspects(planets)

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
            "houses": houses["cusps"],
            "house_signs": house_signs,
            "ac": houses["ac"],
            "mc": houses["mc"],
            "aspects": aspects,
        }


if __name__ == "__main__":
    engine = SwissEphEngine()

    berlin_payload = {
        "name": "Thompson",
        "date": "1988-04-16",
        "time": "20:09",
        "timezone": "Europe/Berlin",
        "latitude": 50.9230079,
        "longitude": 6.8088915,
    }

    chart = engine.calc_birth_chart_from_payload(berlin_payload)

    print("Berechnetes Geburtshoroskop ")
    print(f"Name: {chart['name']}")
    print(f"Julianischer Tag (UT): {chart['jd_ut']:.6f}")

    sun_long = chart["planets"]["sun"]
    sun_sign, sun_pos = chart["planet_signs"]["sun"]
    moon_long = chart["planets"]["moon"]
    moon_sign, moon_pos = chart["planet_signs"]["moon"]
    asc_long = chart["ac"]
    asc_sign, asc_pos = chart["planet_signs"]["ac"]
    mc_long = chart["mc"]
    mc_sign, mc_pos = chart["planet_signs"]["mc"]

    print(f"Sonnenlänge: {sun_long:.6f}° ({sun_pos:.2f}° {sun_sign})")
    print(f"Mondlänge: {moon_long:.6f}° ({moon_pos:.2f}° {moon_sign})")
    print(f"AC: {asc_long:.6f}° ({asc_pos:.2f}° {asc_sign})")
    print(f"MC: {mc_long:.6f}° ({mc_pos:.2f}° {mc_sign})")

    print("Planetenkonstellation:")
    for planet, longitude in chart["planets"].items():
        sign, pos_in_sign = chart["planet_signs"][planet]
        display_name = "AC" if planet == "ac" else "MC" if planet == "mc" else planet.capitalize()
        print(f"  {display_name:<8}: {longitude:.6f}° – {pos_in_sign:.2f}° {sign}")

    print("\nHäuserspitzen (Placidus):")
    for idx, cusp_long in enumerate(chart["houses"], start=1):
        sign, pos_in_sign = chart["house_signs"][idx - 1]
        print(f"  Haus {idx:>2}: {cusp_long:.6f}° – {pos_in_sign:.2f}° {sign}")

    print("\nAspekte (Major):")
    for aspect in chart["aspects"]:
        body1 = aspect["body1"].upper() if aspect["body1"] in {"ac", "mc"} else aspect["body1"].capitalize()
        body2 = aspect["body2"].upper() if aspect["body2"] in {"ac", "mc"} else aspect["body2"].capitalize()
        print(
            "  "
            f"{body1:<9} {aspect['aspect']:<10} {body2:<9} "
            f"(Abstand: {aspect['separation']:.2f}°, Orb: {aspect['orb']:.2f}°)"
        )
