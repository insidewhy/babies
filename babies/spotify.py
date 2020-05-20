import sys
from xdg import BaseDirectory
from typing import List
from datetime import datetime, timedelta
import requests
from requests.auth import HTTPBasicAuth
import dbus
import time

from .config import Config
from .yaml import yaml


PLAYER_URI = 'org.mpris.MediaPlayer2.Player'


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

    yaml.dump(_format_spotify_results(results.json()), sys.stdout)


def _format_spotify_results(results):
    outputs = []
    for album in results['albums']['items']:
        # TODO:
        pass

    for track in results['tracks']['items']:
        artists = list(map(lambda a: a['name'], track['artists']))
        album = track['album']
        output = {
            'type': 'track',
            'artist': artists[0],
            'contributors': artists[1:],
            'album': album['name'],
            'name': track['name'],
            'track_number': track['track_number'],
            'uri': track['uri'],
            'album_uri': album['uri'],
        }
        outputs.append(output)

    return outputs


class SpotifyPlayer:
    def __init__(self):
        bus = dbus.SessionBus()
        proxy = bus.get_object('org.mpris.MediaPlayer2.spotify', '/org/mpris/MediaPlayer2')
        self.player = dbus.Interface(proxy, dbus_interface=PLAYER_URI)
        self.properties = dbus.Interface(proxy, dbus_interface='org.freedesktop.DBus.Properties')
        self.playing = None

    def play_track(self, uri: str):
        self.player.OpenUri(uri)
        self.playing = uri

    def __get_metadata(self):
        return self.properties.Get(PLAYER_URI, "Metadata")

    def __get_playback_status(self):
        return str(self.properties.Get(PLAYER_URI, "PlaybackStatus"))

    def wait_for_track_to_start(self):
        while True:
            metadata = self.__get_metadata()
            if str(metadata["mpris:trackid"]) == self.playing:
                break
            else:
                time.sleep(0.05)

    def wait_for_track_to_end(self):
        while True:
            metadata = self.__get_metadata()
            if str(metadata["mpris:trackid"]) != self.playing or self.__get_playback_status() != 'Playing':
                break
            else:
                time.sleep(0.1)


def listen_to_tracks(tracks: List[str]):
    player = SpotifyPlayer()
    for track in tracks:
        player.play_track(track)
        player.wait_for_track_to_start()
        # TODO: get more data?
        player.wait_for_track_to_end()
