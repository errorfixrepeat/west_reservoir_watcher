import os
import threading
import time
import datetime
import requests
from flask import Flask, request
from twilio.rest import Client
from twilio.twiml.messaging_response import MessagingResponse

app = Flask(__name__)

ACCOUNT_SID   = os.environ['TWILIO_ACCOUNT_SID']
AUTH_TOKEN    = os.environ['TWILIO_AUTH_TOKEN']
FROM_NUMBER   = 'whatsapp:+14155238886'          # Twilio sandbox number
MY_NUMBER     = os.environ['MY_WHATSAPP_NUMBER']  # e.g. whatsapp:+447700900000

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

# date string -> set of known slot times
watching = {}
watching_lock = threading.Lock()
polling = False
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


def send_whatsapp(msg):
    client.messages.create(body=msg, from_=FROM_NUMBER, to=MY_NUMBER)


def poll_loop():
    global polling
    while polling:
        with watching_lock:
            dates = list(watching.keys())

        for date in dates:
            try:
                slots = fetch_slots(date)
                with watching_lock:
                    if date not in watching:
                        continue
                    new_slots = [s for s in slots if s not in watching[date]]
                    if new_slots:
                        send_whatsapp(f"Slot{'s' if len(new_slots) > 1 else ''} available on {date}: {', '.join(new_slots)}")
                    watching[date] = set(slots)
            except Exception as e:
                print(f"Poll error for {date}: {e}")

        time.sleep(20)


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


@app.route('/webhook', methods=['POST'])
def webhook():
    from_number = request.form.get('From', '')
    if from_number != MY_NUMBER:
        return '', 403

    body = request.form.get('Body', '').strip()
    cmd = body.lower()
    resp = MessagingResponse()

    global polling, poll_thread

    if cmd.startswith('watch'):
        arg = body[5:].strip()
        date = parse_date(arg) if arg else None
        if not date:
            resp.message("Couldn't parse that date.\nTry: watch 31 May  or  watch 2026-05-31")
        else:
            with watching_lock:
                watching[date] = set()
            if not polling:
                polling = True
                poll_thread = threading.Thread(target=poll_loop, daemon=True)
                poll_thread.start()
            resp.message(f"Watching {date}, checking every 20s.")

    elif cmd.startswith('stop '):
        date = parse_date(body[5:].strip())
        if date:
            with watching_lock:
                watching.pop(date, None)
                if not watching:
                    polling = False
            resp.message(f"Stopped watching {date}.")
        else:
            resp.message("Couldn't parse that date.")

    elif cmd == 'stop':
        polling = False
        with watching_lock:
            watching.clear()
        resp.message("Stopped.")

    elif cmd == 'status':
        with watching_lock:
            dates = list(watching.keys())
        if dates:
            resp.message("Watching:\n" + "\n".join(dates))
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
                    resp.message(f"Available on {date}:\n{', '.join(slots)}")
                else:
                    resp.message(f"No slots on {date}.")
            except Exception as e:
                resp.message(f"Error: {e}")

    else:
        resp.message(
            "Commands:\n"
            "  watch 31 May\n"
            "  stop\n"
            "  stop 31 May\n"
            "  status\n"
            "  check 31 May"
        )

    return str(resp)


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, threaded=True)
