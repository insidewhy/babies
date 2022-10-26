import sys
from math import floor
from typing import List, Optional, Tuple
from datetime import datetime, timedelta
from threading import Lock
import requests
from requests.auth import HTTPBasicAuth
import dbus
import time

from .config import Config
from .input import ReadInput
from .yaml import yaml
from .formatting import format_duration

PLAYER_URI = "org.mpris.MediaPlayer2.Player"


def search_spotify(config: Config, search_terms: List[str], limit=50, raw=False):
    access_token = config.get_spotify_access_token()
    config.load()

    if not access_token:
        [client_id, client_secret] = config.get_spotify_client_id_and_secret()

        results = requests.post(
            "https://accounts.spotify.com/api/token",
            {"grant_type": "client_credentials"},
            auth=HTTPBasicAuth(client_id, client_secret),
        )

        json = results.json()
        access_token = json["access_token"]

        expires = datetime.now() + timedelta(seconds=json["expires_in"])
        config.save_spotify_access_token(access_token, expires)

    results = requests.get(
        "https://api.spotify.com/v1/search",
        {
            "q": " ".join(search_terms),
            "type": "album,artist,track,episode",
            "limit": limit,
            "market": config.get_spotify_market(),
        },
        headers={"Authorization": f"Bearer {access_token}"},
    )

    if raw:
        yaml.dump(results.json(), sys.stdout)
    else:
        yaml.dump(_format_spotify_results(results.json()), sys.stdout)


def _format_spotify_results(results):
    outputs = []
    for album in results["albums"]["items"]:
        # TODO:
        pass

    for track in results["tracks"]["items"]:
        artists = list(map(lambda a: a["name"], track["artists"]))
        album = track["album"]
        outputs.append(
            {
                "type": "track",
                "artist": artists[0],
                "contributors": artists[1:],
                "album": album["name"],
                "name": track["name"],
                "track_number": track["track_number"],
                "uri": track["uri"],
                "album_uri": album["uri"],
            }
        )

    episodes = []
    for episode in results["episodes"]["items"]:
        episodes.append(
            {
                "type": "episode",
                "name": episode["name"],
                "uri": episode["uri"],
                "release_date": episode["release_date"],
            }
        )
    episodes.sort(key=lambda x: x["release_date"])

    return outputs + episodes


class SpotifyPlayer:
    def __init__(self):
        bus = dbus.SessionBus()
        proxy = bus.get_object(
            "org.mpris.MediaPlayer2.spotify", "/org/mpris/MediaPlayer2"
        )
        self.player = dbus.Interface(proxy, dbus_interface=PLAYER_URI)
        self.properties = dbus.Interface(
            proxy, dbus_interface="org.freedesktop.DBus.Properties"
        )
        self.playing = None
        self.bus_lock = Lock()

    def play_track(self, uri: str):
        with self.bus_lock:
            self.player.OpenUri(uri)
        self.playing = uri
        self.__mpris_trackid = "/com/" + uri.replace(":", "/")

    def stop(self):
        with self.bus_lock:
            # Stop alone pauses the track, so go Next first then Stop, annoying
            self.player.Next()
            self.player.Stop()

    def toggle_pause(self):
        with self.bus_lock:
            self.player.PlayPause()

    def __get_metadata(self):
        with self.bus_lock:
            return self.properties.Get(PLAYER_URI, "Metadata")

    def __get_playback_status(self):
        with self.bus_lock:
            return str(self.properties.Get(PLAYER_URI, "PlaybackStatus"))

    def wait_for_track_to_start(self):
        while True:
            metadata = self.__get_metadata()
            if (
                str(metadata["mpris:trackid"]) == self.__mpris_trackid
                and self.__get_playback_status() == "Playing"
            ):
                break
            else:
                time.sleep(0.05)

    def get_duration(self):
        while True:
            metadata = self.__get_metadata()
            length = metadata["mpris:length"]
            if length > 0:
                return length
            else:
                # sometimes it takes a while after the track has started for
                # the duration to be available
                time.sleep(0.05)

    def wait_for_track_to_end(self):
        # TODO: use events instead
        playback_status = "Playing"
        while True:
            metadata = self.__get_metadata()
            if str(metadata["mpris:trackid"]) != self.__mpris_trackid:
                break
            else:
                new_playback_status = self.__get_playback_status()
                if new_playback_status != playback_status:
                    if new_playback_status == "Paused":
                        print("pause: paused", flush=True)
                    elif new_playback_status == "Playing":
                        print("pause: resumed", flush=True)
                    else:
                        break
                    playback_status = new_playback_status
                time.sleep(0.1)

    def get_position(self):
        with self.bus_lock:
            return self.properties.Get(PLAYER_URI, "Position")


player: Optional[SpotifyPlayer] = None


def handle_keypress(key: str):
    global player
    if not player:
        return

    if key == "q":
        player.stop()
    elif key == " ":
        player.toggle_pause()


def listen_to_track(read_input: ReadInput, track_uri: str) -> Tuple[int, str, datetime]:
    global player
    if not player:
        player = SpotifyPlayer()

    read_input.start(handle_keypress)

    player.play_track(track_uri)
    player.wait_for_track_to_start()
    print(f"start: {track_uri}", flush=True)

    duration = player.get_duration()
    # floor duration etc. spotify player isn't very accurate
    formatted_duration = format_duration(duration / 1_000_000)
    print(f"position: {format_duration(0)}/{formatted_duration}", flush=True)

    player.wait_for_track_to_end()
    # spotify automatically transitions to the next track
    player.stop()

    position = player.get_position()
    # another hack
    if position < 2_000_000:
        position = duration

    print(f"end: {format_duration(position / 1_000_000)}/{formatted_duration}")
    read_input.stop()

    return floor(position), formatted_duration, datetime.now()
