// Cloudflare Worker — proxy for the Better.org.uk API
// Runs server-side so there's no CORS issue when the browser calls it.
//
// Python equivalent of what this does:
//   def worker(request):
//       date = request.params.get("date", today())
//       response = requests.get(API_URL, params={"date": date}, headers=HEADERS)
//       return Response(response.json(), headers={"Access-Control-Allow-Origin": "*"})

const API_BASE =
  "https://better-admin.org.uk/api/activities/venue/west-reservoir-centre/activity/open-water-swimming/times";

export default {
  async fetch(request) {
    const url = new URL(request.url);
    const date = url.searchParams.get("date") || todayISO();

    const apiUrl = `${API_BASE}?date=${date}`;

    const apiResponse = await fetch(apiUrl, {
      headers: {
        accept: "application/json",
        "accept-language": "en-GB,en-US;q=0.9,en;q=0.8",
        origin: "https://bookings.better.org.uk",
        referer: `https://bookings.better.org.uk/location/west-reservoir-centre/open-water-swimming/${date}/by-time`,
        "user-agent":
          "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/103.0.0.0 Safari/537.36",
      },
    });

    const body = await apiResponse.text();

    // Allow any webpage (including your GitHub Pages site) to read this response
    return new Response(body, {
      status: apiResponse.status,
      headers: {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": "*",
      },
    });
  },
};

function todayISO() {
  return new Date().toISOString().split("T")[0];
}
