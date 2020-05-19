import sys
from xdg import BaseDirectory
from typing import List
from datetime import datetime, timedelta
import requests
from requests.auth import HTTPBasicAuth

from .config import Config
from .yaml import yaml


def search_spotify(config: Config, search_terms: List[str], limit=50, raw=False):
    access_token = config.get_spotify_access_token()

    if not access_token:
        config.load()
        [client_id, client_secret] = config.get_spotify_client_id_and_secret()

        results = requests.post('https://accounts.spotify.com/api/token', {
            "grant_type": "client_credentials",
        }, auth=HTTPBasicAuth(client_id, client_secret))

        json = results.json()
        access_token = json['access_token']

        expires = datetime.now() + timedelta(seconds=json['expires_in'])
        config.save_spotify_access_token(access_token, expires)

    results = requests.get('https://api.spotify.com/v1/search', {
        'q': ' '.join(search_terms),
        'type': 'album,artist,track',
        'limit': limit
    }, headers={
        'Authorization': f'Bearer {access_token}',
    })

    if raw:
        yaml.dump(results.json(), sys.stdout)
        return

    # TODO: format results
    yaml.dump(results.json(), sys.stdout)

