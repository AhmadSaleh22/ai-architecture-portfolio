"""Travel adapter: expand pilgrim groups (flights in, flights out) into one itinerary job each.

Time rules per group (hard):
  arrival transfer: starts after landing + 60 min (immigration), ends within 4 hours of landing
  departure transfer: arrives at the airport 3 hours before the flight
Soft: the ziyarah tour and museum in the morning of the 2nd and 3rd day after arrival.
"""
import csv
from datetime import datetime, timedelta

from . import services as sv


def _iso(dt):
    return dt.isoformat(timespec="minutes")


def requests(groups, cfg):
    out = []
    for g in groups:
        arr = datetime.fromisoformat(g["arrive"])
        dep = datetime.fromisoformat(g["depart"])
        d1 = (arr + timedelta(days=1)).replace(hour=7, minute=0)
        d2 = (arr + timedelta(days=2)).replace(hour=7, minute=0)
        out.append({
            "id": g["group"], "class": "package", "service": "umrah_package", "who": g["group"],
            "lang": g["lang"], "group": g["group"], "size": cfg["resources"][g["group"]]["attrs"]["size"],
            "attr_group": g["group"], "release": _iso(arr + timedelta(minutes=60)),
            "due": _iso(dep - timedelta(hours=3)),
            "steps": {
                "arrival": {"release": _iso(arr + timedelta(minutes=60)), "deadline": _iso(arr + timedelta(hours=4))},
                "ziyarah": {"pref_from": _iso(d1), "pref_to": _iso(d1 + timedelta(hours=3))},
                "museum": {"pref_from": _iso(d2), "pref_to": _iso(d2 + timedelta(hours=4))},
                "departure": {"release": _iso(dep - timedelta(hours=8)), "deadline": _iso(dep - timedelta(hours=3))},
            }})
    return out


def read_groups(path):
    with open(path, newline="", encoding="utf-8") as f:
        return [dict(r) for r in csv.DictReader(f)]


def build(cfg, groups, start):
    return sv.build(cfg, requests(groups, cfg), start)
