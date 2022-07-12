import requests
import time
import streamlit as st
from streamlit_autorefresh import st_autorefresh
from datetime import time as datetime

headers = {
    'authority': 'better-admin.org.uk',
    'accept': 'application/json',
    'accept-language': 'en-GB,en-US;q=0.9,en;q=0.8',
    'dnt': '1',
    'origin': 'https://bookings.better.org.uk',
    'referer': 'https://bookings.better.org.uk/location/west-reservoir-centre/open-water-swimming/<REPLACEME>/by-time',
    'sec-ch-ua': '".Not/A)Brand";v="99", "Google Chrome";v="103", "Chromium";v="103"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"macOS"',
    'sec-fetch-dest': 'empty',
    'sec-fetch-mode': 'cors',
    'sec-fetch-site': 'cross-site',
    'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/103.0.0.0 Safari/537.36',
}
api_url = 'https://better-admin.org.uk/api/activities/venue/west-reservoir-centre/activity/open-water-swimming/times'

def check_swimming(date, headers, api_url):
    params = {'date' : date}
    headers['referer'] = headers['referer'].replace("<REPLACEME>", date)
    response = requests.get(api_url, params=params, headers=headers)
    
    if response.status_code == 200:
        return response.json()
    else:
        print("Error")
        print(response.text)

def find_available(response_json):
    if isinstance(response_json["data"], dict):
        response_json["data"] = list(response_json["data"].values())
    return [_ for _ in response_json["data"] if _['action_to_show']['status'] is not None]

def check_for_changes(date="2022-07-03", headers=headers, api_url=api_url):
    cache = st.session_state['cache']
    response = check_swimming(date, headers, api_url)
    available = find_available(response)
    times = [_["starts_at"]["format_24_hour"] for _ in available]
    times = sorted(times, key = lambda x: x.split(":")[0]*60+x.split(":")[1])
    if cache.union(set(times)).difference(cache):
        ding()
        print(times)
    st.session_state['cache'] = set(times)
    st.session_state['last_update'] = time.strftime('%H:%M', time.localtime(time.time()))

def ding():
    html_string = """
            <audio controls autoplay>
              <source src="https://www.orangefreesounds.com/wp-content/uploads/2022/04/Small-bell-ringing-short-sound-effect.mp3" type="audio/mp3">
            </audio>
            """

    sound = st.empty()
    sound.markdown(html_string, unsafe_allow_html=True)
    time.sleep(2)  # wait for 2 seconds to finish the playing of the audio
    sound.empty()  # optionally delete the element afterwards

def clear():
    st.session_state['cache'] = set()
    
def main():
    count = st_autorefresh(interval=60000, limit=60*6, key="fizzbuzzcounter")
    
    print("entry")
    if 'cache' not in st.session_state:
        st.session_state['cache'] = set()
    if 'last_update' not in st.session_state:   
        st.session_state['last_update'] = 0
        
    date = st.date_input("Select date:", on_change=clear)
    check_for_changes(date=str(date), headers=headers, api_url=api_url)
    
    st.markdown('#')
    status = st.write(f'Available times: {" ".join(st.session_state["cache"])}')
    
    st.markdown('#')
    st.markdown('#')
    st.markdown('#')
    st.markdown('#')
    last_update = st.markdown(f"*Last refresh: {st.session_state['last_update']}*")
    

if __name__ == "__main__":
    main()
