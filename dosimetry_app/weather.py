from __future__ import annotations

import json
from urllib.parse import urlencode
from urllib.request import Request, urlopen

IP_GEO_ENDPOINT = "https://ipapi.co/json/"
OPEN_METEO_ENDPOINT = "https://api.open-meteo.com/v1/forecast"
OPEN_METEO_GEOCODE_ENDPOINT = "https://geocoding-api.open-meteo.com/v1/search"
OPEN_METEO_REVERSE_GEOCODE_ENDPOINT = "https://geocoding-api.open-meteo.com/v1/reverse"
HTTP_TIMEOUT_SECONDS = 10
AFRICA_COUNTRY_CODES = {
    "DZ",
    "AO",
    "BJ",
    "BW",
    "BF",
    "BI",
    "CM",
    "CV",
    "CF",
    "TD",
    "KM",
    "CG",
    "CD",
    "DJ",
    "EG",
    "GQ",
    "ER",
    "SZ",
    "ET",
    "GA",
    "GM",
    "GH",
    "GN",
    "GW",
    "CI",
    "KE",
    "LS",
    "LR",
    "LY",
    "MG",
    "MW",
    "ML",
    "MR",
    "MU",
    "MA",
    "MZ",
    "NA",
    "NE",
    "NG",
    "RW",
    "ST",
    "SN",
    "SC",
    "SL",
    "SO",
    "ZA",
    "SS",
    "SD",
    "TZ",
    "TG",
    "TN",
    "UG",
    "ZM",
    "ZW",
}


def _fetch_json(url: str) -> dict:
    request = Request(url, headers={"User-Agent": "dosimetry-streamlit-app/1.0"})
    with urlopen(request, timeout=HTTP_TIMEOUT_SECONDS) as response:  # noqa: S310
        body = response.read().decode("utf-8")
    return json.loads(body)


def detect_location_from_ip() -> dict:
    payload = _fetch_json(IP_GEO_ENDPOINT)
    latitude = payload.get("latitude") or payload.get("lat")
    longitude = payload.get("longitude") or payload.get("lon")
    city = payload.get("city")
    region = payload.get("region")
    country = payload.get("country_name") or payload.get("country")
    country_code = payload.get("country_code")

    if latitude is None or longitude is None:
        raise ValueError("Could not determine latitude/longitude from IP geolocation provider.")

    parts = [part for part in (city, region, country) if part]
    label = ", ".join(parts) if parts else "Unknown Location"
    return {
        "location_label": label,
        "latitude": float(latitude),
        "longitude": float(longitude),
        "city": str(city) if city else "",
        "country": str(country) if country else "",
        "country_code": str(country_code) if country_code else "",
    }


def geocode_location(location_query: str) -> dict:
    query = urlencode({"name": location_query, "count": 10, "language": "en", "format": "json"})
    payload = _fetch_json(f"{OPEN_METEO_GEOCODE_ENDPOINT}?{query}")
    results = payload.get("results") or []
    if not results:
        raise ValueError(f"No geocoding results for '{location_query}'.")

    african_results = [result for result in results if str(result.get("country_code", "")).upper() in AFRICA_COUNTRY_CODES]
    selected = african_results[0] if african_results else results[0]

    name = selected.get("name")
    admin1 = selected.get("admin1")
    country = selected.get("country")
    latitude = selected.get("latitude")
    longitude = selected.get("longitude")
    country_code = selected.get("country_code")

    if latitude is None or longitude is None:
        raise ValueError("Geocoding result missing latitude/longitude.")

    parts = [part for part in (name, admin1, country) if part]
    label = ", ".join(parts) if parts else str(location_query)
    return {
        "location_label": label,
        "latitude": float(latitude),
        "longitude": float(longitude),
        "city": str(name) if name else "",
        "country": str(country) if country else "",
        "country_code": str(country_code) if country_code else "",
    }


def reverse_geocode_coordinates(latitude: float, longitude: float) -> dict:
    query = urlencode(
        {
            "latitude": latitude,
            "longitude": longitude,
            "count": 10,
            "language": "en",
            "format": "json",
        }
    )
    payload = _fetch_json(f"{OPEN_METEO_REVERSE_GEOCODE_ENDPOINT}?{query}")
    results = payload.get("results") or []
    if not results:
        raise ValueError("No reverse geocoding results for the provided coordinates.")

    african_results = [
        result for result in results if str(result.get("country_code", "")).upper() in AFRICA_COUNTRY_CODES
    ]
    selected = african_results[0] if african_results else results[0]

    name = selected.get("name")
    admin1 = selected.get("admin1")
    country = selected.get("country")
    country_code = selected.get("country_code")

    parts = [part for part in (name, country) if part]
    label = ", ".join(parts) if parts else "Current location"
    return {
        "location_label": label,
        "city": str(name) if name else "",
        "admin1": str(admin1) if admin1 else "",
        "country": str(country) if country else "",
        "country_code": str(country_code) if country_code else "",
    }


def fetch_current_environment(latitude: float, longitude: float) -> dict:
    query = urlencode(
        {
            "latitude": latitude,
            "longitude": longitude,
            "current": "temperature_2m,surface_pressure",
            "timezone": "auto",
        }
    )
    payload = _fetch_json(f"{OPEN_METEO_ENDPOINT}?{query}")
    current = payload.get("current") or {}
    temperature_c = current.get("temperature_2m")
    pressure_hpa = current.get("surface_pressure")

    if temperature_c is None or pressure_hpa is None:
        raise ValueError("Weather provider did not return temperature and surface pressure.")

    return {
        "temperature_c": float(temperature_c),
        "pressure_kpa": float(pressure_hpa) / 10.0,
        "raw_pressure_hpa": float(pressure_hpa),
    }


def auto_detect_environment(preferred_location: str | None = None) -> dict:
    if preferred_location and preferred_location.strip():
        location = geocode_location(preferred_location.strip())
        geolocation_provider = "open-meteo-geocoding"
    else:
        location = detect_location_from_ip()
        geolocation_provider = "ipapi.co"

    weather = fetch_current_environment(location["latitude"], location["longitude"])
    return {
        "source": "auto_weather",
        "location": location["location_label"],
        "latitude": location["latitude"],
        "longitude": location["longitude"],
        "city": location.get("city", ""),
        "country": location.get("country", ""),
        "country_code": location.get("country_code", ""),
        "temperature_c": weather["temperature_c"],
        "pressure_kpa": weather["pressure_kpa"],
        "provider": {
            "geolocation": geolocation_provider,
            "weather": "open-meteo.com",
        },
    }
