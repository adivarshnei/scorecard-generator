import json
import requests
import urllib

link: str = (
    "https://hs-consumer-api.espncricinfo.com/v1/pages/matches/current?lang=en&latest=true"
)

req = urllib.request.Request(
    link,
    data=None,
    headers={
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_9_3) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/35.0.1916.47 Safari/537.36"
    },
)

json_contents = urllib.request.urlopen(req).read().decode("utf-8")
json_file = json.loads(json_contents)


print(
    "\n".join(
        [
            f"{x['objectId']}: "
            + f"{x['teams'][0]['team']['abbreviation']:5}"
            + " vs "
            + f"{x['teams'][1]['team']['abbreviation']:5}"
            + f" ({x['series']['name']})"
            + ": "
            + f"{x['statusText']}"
            for x in json_file["matches"]
        ]
    )
)
