import urllib.request
import xml.etree.ElementTree as ET

RSS_FEEDS = {
    "MetaTrends": "https://metatrends.substack.com/feed",
    "ARK Invest": "https://ark-invest.com/feed/",
    "a16z": "https://www.a16z.news/feed"
}


def fetch_rss_titles(source_name, url):

    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0"
        }
    )

    response = urllib.request.urlopen(request)
    data = response.read()

    root = ET.fromstring(data)

    channel = root.find("channel")
    if channel is None:
        print(f"\nNo channel found for {source_name}")
        return

    items = channel.findall("item")

    print(f"\n===== {source_name} =====\n")

    for item in items[:5]:
        title = item.find("title")
        if title is not None and title.text is not None:
            print("-", title.text)


if __name__ == "__main__":

    for source_name, url in RSS_FEEDS.items():
        fetch_rss_titles(source_name, url)