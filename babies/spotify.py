import sys
from math import floor
from typing import List, Optional, Tuple, Any
from datetime import datetime, timedelta
import requests
from requests.auth import HTTPBasicAuth
from dbus_next.aio import MessageBus
import asyncio

from .config import Config
from .input import ReadInput
from .yaml import yaml
from .formatting import format_duration


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
        pass

    async def start(self):
        bus = await MessageBus().connect()
        introspection = await bus.introspect(
            "org.mpris.MediaPlayer2.spotify", "/org/mpris/MediaPlayer2"
        )
        proxy = bus.get_proxy_object(
            "org.mpris.MediaPlayer2.spotify", "/org/mpris/MediaPlayer2", introspection
        )
        self.player: Any = proxy.get_interface("org.mpris.MediaPlayer2.Player")
        self.properties = proxy.get_interface("org.freedesktop.DBus.Properties")
        self.playing = None

    async def play_track(self, uri: str):
        await self.player.call_open_uri(uri)
        self.playing = uri
        self.__mpris_trackid = "/com/" + uri.replace(":", "/")

    async def stop(self):
        # Stop alone pauses the track, so go Next first then Stop, annoying
        await self.player.call_next()
        await self.player.call_stop()

    async def toggle_pause(self):
        await self.player.call_play_pause()

    async def __get_metadata(self):
        return await self.player.get_metadata()

    async def __get_playback_status(self):
        return await self.player.get_playback_status()

    async def wait_for_track_to_start(self):
        while True:
            metadata = await self.__get_metadata()
            if (
                metadata["mpris:trackid"].value == self.__mpris_trackid
                and await self.__get_playback_status() == "Playing"
            ):
                break
            else:
                await asyncio.sleep(0.05)

    async def get_duration(self):
        while True:
            metadata = await self.__get_metadata()
            length = metadata["mpris:length"].value
            if length > 0:
                return length
            else:
                # sometimes it takes a while after the track has started for
                # the duration to be available
                await asyncio.sleep(0.05)

    async def wait_for_track_to_end(self):
        # TODO: use events instead
        playback_status = "Playing"
        while True:
            metadata = await self.__get_metadata()
            if metadata["mpris:trackid"].value != self.__mpris_trackid:
                break
            else:
                new_playback_status = await self.__get_playback_status()
                if new_playback_status != playback_status:
                    if new_playback_status == "Paused":
                        print("pause: paused", flush=True)
                    elif new_playback_status == "Playing":
                        print("pause: resumed", flush=True)
                    else:
                        break
                    playback_status = new_playback_status
                await asyncio.sleep(0.1)

    async def get_position(self):
        return await self.player.get_position()


player: Optional[SpotifyPlayer] = None


async def handle_keypress(key: str):
    global player
    if not player:
        return

    if key == "q":
        await player.stop()
    elif key == " ":
        await player.toggle_pause()


async def __listen_to_track_helper(
    read_input: ReadInput, track_uri: str
) -> Tuple[int, str, datetime]:
    loop = asyncio.get_event_loop()

    global player
    if not player:
        player = SpotifyPlayer()
        await player.start()

    def handle_keypress_helper(key: str) -> None:
        loop.create_task(handle_keypress(key))

    read_input.start(handle_keypress_helper)

    await player.play_track(track_uri)
    await player.wait_for_track_to_start()
    print(f"start: {track_uri}", flush=True)

    duration = await player.get_duration()
    # floor duration etc. spotify player isn't very accurate
    formatted_duration = format_duration(duration / 1_000_000)
    print(f"position: {format_duration(0)}/{formatted_duration}", flush=True)

    await player.wait_for_track_to_end()
    # spotify automatically transitions to the next track
    await player.stop()

    position = await player.get_position()
    # another hack
    if position < 2_000_000:
        position = duration

    print(f"end: {format_duration(position / 1_000_000)}/{formatted_duration}")
    read_input.stop()

    return floor(position), formatted_duration, datetime.now()


def listen_to_track(read_input: ReadInput, track_uri: str) -> Tuple[int, str, datetime]:
    loop = asyncio.get_event_loop()
    ret = loop.run_until_complete(__listen_to_track_helper(read_input, track_uri))
    loop.close()
    return ret
