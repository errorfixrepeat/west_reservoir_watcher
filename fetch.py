"""
Fetches open water swimming slot availability from Better.org.uk
and writes results to data.json for the GitHub Pages frontend to read.
Run by GitHub Actions every 5 minutes.
"""
import requests
import json
import datetime

HEADERS = {
    'accept': 'application/json',
    'accept-language': 'en-GB,en-US;q=0.9,en;q=0.8',
    'dnt': '1',
    'origin': 'https://bookings.better.org.uk',
    'referer': 'https://bookings.better.org.uk/location/west-reservoir-centre/open-water-swimming/by-time',
    'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/103.0.0.0 Safari/537.36',
}

API_URL = (
    'https://better-admin.org.uk/api/activities/venue/'
    'west-reservoir-centre/activity/open-water-swimming/times'
)

DAYS_AHEAD = 14


def fetch_slots(date_str):
    try:
        r = requests.get(API_URL, params={'date': date_str}, headers=HEADERS, timeout=10)
        r.raise_for_status()
        data = r.json().get('data', [])
        if isinstance(data, dict):
            data = list(data.values())
        return sorted(
            item['starts_at']['format_24_hour']
            for item in data
            if item.get('action_to_show', {}).get('status') is not None
        )
    except Exception as e:
        print(f"  {date_str}: error — {e}")
        return None  # None = fetch failed; [] = fetched but no slots


today = datetime.date.today()
slots = {}

for i in range(DAYS_AHEAD):
    d = str(today + datetime.timedelta(days=i))
    print(f"Fetching {d}...")
    result = fetch_slots(d)
    slots[d] = result  # None if error, list otherwise

output = {
    'updated': datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ'),
    'slots': slots,
}

with open('data.json', 'w') as f:
    json.dump(output, f)

print("Wrote data.json")
