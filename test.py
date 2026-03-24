import requests
import json

# Let's query a specific week where we know severe weather occurred
start_date = "20230501"
end_date = "20230507"

# Notice how the date range is at the end of the URL path separated by a colon
url = f"https://www.ncei.noaa.gov/swdiws/json/nx3tvs/{start_date}:{end_date}"

try:
    print(f"Querying URL: {url}\n")
    response = requests.get(url)
    response.raise_for_status()

    data = response.json()

    # Check if we got results
    if "result" in data and len(data["result"]) > 0:
        print(f"✅ Success! Found {len(data['result'])} radar signatures.\n")

        # Print just the first record to see the structure
        print("Example Record:")
        print(json.dumps(data["result"][0], indent=2))
    else:
        print("⚠️ Connected, but no tornado signatures were found for this date range.")

except Exception as e:
    print(f"Error: {e}")
