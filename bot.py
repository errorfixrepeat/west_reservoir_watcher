import os
import re
import threading
import time
import datetime
import requests
from flask import Flask, request
from twilio.rest import Client
from twilio.twiml.messaging_response import MessagingResponse

app = Flask(__name__)

ACCOUNT_SID = os.environ['TWILIO_ACCOUNT_SID']
AUTH_TOKEN  = os.environ['TWILIO_AUTH_TOKEN']
FROM_NUMBER = 'whatsapp:+14155238886'           # Twilio sandbox number
MY_NUMBER   = os.environ['MY_WHATSAPP_NUMBER']  # e.g. whatsapp:+447700900000

client = Client(ACCOUNT_SID, AUTH_TOKEN)

API_URL = (
    'https://better-admin.org.uk/api/activities/venue/'
    'west-reservoir-centre/activity/open-water-swimming/v2/times'
)
HEADERS = {
    'accept': 'application/json',
    'origin': 'https://bookings.better.org.uk',
    'referer': 'https://bookings.better.org.uk/location/west-reservoir-centre/open-water-swimming/by-time',
    'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/103.0.0.0 Safari/537.36',
}

HELP = (
    "Commands:\n"
    "  watch 31 May\n"
    "  watch 31 May 12:00-14:30\n"
    "  drop 31 May  — stop watching one date\n"
    "  pause        — stop watching everything\n"
    "  status       — show what's being watched\n"
    "  check 31 May — one-off check right now"
)

# date -> {'known': set of times, 'from': '12:00' or None, 'to': '14:30' or None}
watching = {}
watching_lock = threading.Lock()
stop_event = threading.Event()
poll_thread = None


def fetch_slots(date):
    r = requests.get(API_URL, params={'date': date}, headers=HEADERS, timeout=10)
    r.raise_for_status()
    data = r.json().get('data', [])
    if isinstance(data, dict):
        data = list(data.values())
    return sorted(
        item['starts_at']['format_24_hour']
        for item in data
        if item.get('action_to_show', {}).get('status') is not None
    )


def in_range(slot, from_time, to_time):
    if not from_time:
        return True
    return from_time <= slot <= to_time


def send_whatsapp(msg):
    client.messages.create(body=msg, from_=FROM_NUMBER, to=MY_NUMBER)


def poll_loop():
    while not stop_event.is_set():
        with watching_lock:
            snapshot = {d: dict(v) for d, v in watching.items()}

        for date, cfg in snapshot.items():
            if stop_event.is_set():
                return
            try:
                all_slots = fetch_slots(date)
                slots = [s for s in all_slots if in_range(s, cfg['from'], cfg['to'])]
                with watching_lock:
                    if date not in watching:
                        continue
                    new_slots = [s for s in slots if s not in watching[date]['known']]
                    if new_slots:
                        send_whatsapp(
                            f"Slot{'s' if len(new_slots) > 1 else ''} available on {date}:\n"
                            + ', '.join(new_slots)
                        )
                    watching[date]['known'] = set(slots)
            except Exception as e:
                print(f"Poll error for {date}: {e}")

        stop_event.wait(20)


def parse_date(text):
    text = text.strip()
    if text.lower() == 'today':
        return str(datetime.date.today())
    if text.lower() == 'tomorrow':
        return str(datetime.date.today() + datetime.timedelta(days=1))
    for fmt in ('%Y-%m-%d', '%d %B %Y', '%d %b %Y', '%d %B', '%d %b'):
        try:
            d = datetime.datetime.strptime(text, fmt)
            if '%Y' not in fmt:
                d = d.replace(year=datetime.date.today().year)
                if d.date() < datetime.date.today():
                    d = d.replace(year=d.year + 1)
            return str(d.date())
        except ValueError:
            continue
    return None


def parse_watch_arg(text):
    """Parse 'watch' argument into (date_str, from_time, to_time).
    e.g. '31 May 12:00-14:30' -> ('2026-05-31', '12:00', '14:30')
         '31 May'              -> ('2026-05-31', None, None)
    """
    m = re.search(r'(\d{1,2}:\d{2})\s*[-–]\s*(\d{1,2}:\d{2})', text)
    if m:
        from_time = m.group(1)
        to_time   = m.group(2)
        date_text = text[:m.start()].strip()
    else:
        from_time = to_time = None
        date_text = text.strip()

    date = parse_date(date_text) if date_text else None
    return date, from_time, to_time


@app.route('/webhook', methods=['POST'])
def webhook():
    from_number = request.form.get('From', '')
    if from_number != MY_NUMBER:
        return '', 403

    body = request.form.get('Body', '').strip()
    cmd  = body.lower()
    resp = MessagingResponse()

    global poll_thread

    if cmd.startswith('watch'):
        arg = body[5:].strip()
        date, from_time, to_time = parse_watch_arg(arg)

        if not date:
            resp.message("Couldn't parse that date.\n\n" + HELP)
        else:
            with watching_lock:
                watching[date] = {'known': set(), 'from': from_time, 'to': to_time}
            if poll_thread is None or not poll_thread.is_alive():
                stop_event.clear()
                poll_thread = threading.Thread(target=poll_loop, daemon=True)
                poll_thread.start()

            range_note = f" ({from_time}–{to_time})" if from_time else ""
            resp.message(
                f"Watching {date}{range_note}, checking every 20s.\n\n" + HELP
            )

    elif cmd.startswith('drop '):
        date = parse_date(body[5:].strip())
        if date:
            with watching_lock:
                watching.pop(date, None)
                if not watching:
                    stop_event.set()
            resp.message(f"Stopped watching {date}.")
        else:
            resp.message("Couldn't parse that date.")

    elif cmd == 'pause':
        stop_event.set()
        with watching_lock:
            watching.clear()
        resp.message("Paused. Send 'watch DATE' to start again.")

    elif cmd == 'status':
        with watching_lock:
            items = list(watching.items())
        if items:
            lines = []
            for d, cfg in items:
                r = f" ({cfg['from']}–{cfg['to']})" if cfg['from'] else ""
                lines.append(f"  {d}{r}")
            resp.message("Watching:\n" + "\n".join(lines))
        else:
            resp.message("Not watching anything.")

    elif cmd.startswith('check'):
        arg = body[6:].strip()
        date = parse_date(arg) if arg else str(datetime.date.today())
        if not date:
            resp.message("Couldn't parse that date.")
        else:
            try:
                slots = fetch_slots(date)
                if slots:
                    resp.message(f"Available on {date}:\n" + ', '.join(slots))
                else:
                    resp.message(f"No slots on {date}.")
            except Exception as e:
                resp.message(f"Error: {e}")

    else:
        resp.message(HELP)

    return str(resp)


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, threaded=True)
