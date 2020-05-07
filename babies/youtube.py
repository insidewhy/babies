import sys
import json
import html
from typing import List
from xdg import BaseDirectory
import requests

from .yaml import yaml, load_yaml_file


def _get_api_key():
    config_path = BaseDirectory.load_first_config('babies.yaml')
    if not config_path:
        raise ValueError('No configuration found')
    config = load_yaml_file(config_path)
    api_key = config['youtube-api-key']
    if not api_key:
        raise ValueError('No youtube-api-key configuration element found')
    return api_key


def search_youtube(search_terms: List[str], duration: str):
    api_key = _get_api_key()

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
        list(map(format_search_entry, json.loads(results.text)['items'])),
        sys.stdout
    )
