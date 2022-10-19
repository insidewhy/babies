from os import path
from xdg import BaseDirectory
from typing import Dict, Optional, Tuple, TypedDict
from datetime import datetime

from .yaml import load_yaml_file, save_yaml_file

DEFAULT_SPOTIFY_MARKET = "US"


def _load_first_data(path: str) -> Optional[str]:
    for path in BaseDirectory.load_data_paths(path):
        return path
    return None


class ConfigDisplay(TypedDict):
    output: str
    mode: str


ConfigDisplays = Dict[str, ConfigDisplay]


class Config:
    def __init__(self):
        self.config = {}

    def load(self):
        if not self.config:
            config_path = BaseDirectory.load_first_config("babies.yaml")
            if not config_path:
                raise ValueError("No configuration found")
            self.config = load_yaml_file(config_path)

    def get_youtube_api_key(self) -> str:
        api_key = self.config.get("youtube-api-key", None)
        if not api_key:
            raise ValueError("No youtube-api-key configuration element found")
        return api_key

    def get_displays(self) -> ConfigDisplays:
        return self.config.get("displays", {})

    def get_spotify_access_token(self) -> Optional[str]:
        data_path = _load_first_data("babies.yaml")
        if not data_path:
            return None

        data = load_yaml_file(data_path)
        spotify = data.get("spotify", None)
        if not spotify:
            return None

        if datetime.now() >= spotify["expires"]:
            return None

        return spotify["access_token"]

    def save_spotify_access_token(self, token, expires) -> None:
        data_path = path.join(BaseDirectory.xdg_data_home, "babies.yaml")
        save_yaml_file(
            data_path, {"spotify": {"access_token": token, "expires": expires}}
        )

    def get_spotify_client_id_and_secret(self) -> Tuple[str, str]:
        spotify_config = self.config.get("spotify", None)
        if not spotify_config:
            raise ValueError("No spotify configuration element found")
        client_id = spotify_config.get("client-id", None)
        if not client_id:
            raise ValueError("No spotify.client-id configuration element found")
        client_secret = spotify_config.get("client-secret", None)
        if not client_secret:
            raise ValueError("No spotify.client-secret configuration element found")
        return client_id, client_secret

    def get_spotify_market(self) -> Optional[str]:
        spotify_config = self.config.get("spotify", None)
        if not spotify_config:
            return DEFAULT_SPOTIFY_MARKET
        else:
            return spotify_config.get("market", DEFAULT_SPOTIFY_MARKET)
