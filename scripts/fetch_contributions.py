#!/usr/bin/env python3
"""Saves the last year of GitHub's contribution calendar to data/contributions.json.

Usage: GITHUB_TOKEN=... GITHUB_LOGIN=<user> python3 scripts/fetch_contributions.py
"""
import json
import os
import pathlib
import sys
import urllib.request

OUT = pathlib.Path(__file__).resolve().parent.parent / "data" / "contributions.json"
QUERY = """
query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      contributionCalendar {
        weeks { contributionDays { date contributionCount contributionLevel } }
      }
    }
  }
}
"""
LEVELS = {"NONE": 0, "FIRST_QUARTILE": 1, "SECOND_QUARTILE": 2, "THIRD_QUARTILE": 3, "FOURTH_QUARTILE": 4}


def main():
    token, login = os.environ.get("GITHUB_TOKEN"), os.environ.get("GITHUB_LOGIN")
    if not token or not login:
        sys.exit("Set GITHUB_TOKEN and GITHUB_LOGIN.")
    request = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"login": login}}).encode(),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json", "User-Agent": "profile-readme-figures"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.load(response)
    if payload.get("errors") or not payload.get("data", {}).get("user"):
        sys.exit(f"GitHub did not return a contribution calendar for {login}: {payload.get('errors')}")
    weeks = payload["data"]["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]
    days = [
        {"date": day["date"], "count": day["contributionCount"], "level": LEVELS[day["contributionLevel"]]}
        for week in weeks for day in week["contributionDays"]
    ]
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps({"login": login, "days": days}, indent=1) + "\n")
    print(f"Saved {len(days)} days for {login}.")


if __name__ == "__main__":
    main()
