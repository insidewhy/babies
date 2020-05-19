import sys
import html
from typing import List
import requests

from .config import Config
from .yaml import yaml


def search_youtube(config: Config, search_terms: List[str], duration: str):
    config.load()
    api_key = config.get_youtube_api_key()

    results = requests.get(
        "https://www.googleapis.com/youtube/v3/search", {
            "part": "snippet",
            "type": "video",
            "q": " ".join(search_terms),
            "maxResults": 50,
            "key": api_key,
            "videoDuration": duration or "any"
        }
    )

    def format_search_entry(entry):
        snippet = entry['snippet']
        return {
            'title': html.unescape(snippet['title']),
            'description': html.unescape(snippet['description']),
            'channel title': html.unescape(snippet['channelTitle']),
            'id': entry['id']['videoId'],
        }

    yaml.dump(
        # json.loads(results.text)['items'],
        list(map(format_search_entry, results.json()['items'])),
        sys.stdout
    )
