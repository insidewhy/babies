import os
from typing import List, Dict, Optional
from mypy_extensions import TypedDict

from .yaml import load_yaml_file, save_yaml_file

# set this when the end is unknown... assume it finished sometime
UNKNOWN_END = "sometime at finished?"


class VideoData(TypedDict, total=False):
    video: str
    viewings: List[Dict[str, str]]
    duration: str


VideoDb = List[VideoData]


def _load_old_db(filepath, global_variation):
    db_entries = []
    with open(filepath, "r") as fp:
        for _, line in enumerate(fp):
            line = line.rstrip("\n")
            video_data: VideoData = {}

            if global_variation or line[0] == "*":
                if not global_variation:
                    # remove the *
                    line = line[1:]

                start = "sometime"
                space_idx = line.index(" ")
                if line[0] != " ":
                    start = line[:space_idx].replace("-", "/").replace("~", " ")
                video_file = line[space_idx + 1 :]
                video_data["video"] = video_file
                video_data["viewings"] = [{"start": start, "end": UNKNOWN_END}]
            else:
                video_data["video"] = line
            db_entries.append(video_data)
    return db_entries


class Db:
    def __init__(self):
        self.__video_db: VideoDb = []
        self.aliased_db: Optional[Db] = None

    def load_series(self, dirpath: str) -> bool:
        db_path = Db.get_series_db_path(dirpath)
        try:
            self.__video_db = load_yaml_file(db_path)
            return True
        except FileNotFoundError:
            self.__video_db = []
            return False

    @staticmethod
    def path_has_series_db(dirpath: str) -> bool:
        db_path = Db.get_series_db_path(dirpath)
        return os.path.isfile(db_path)

    def get_next_index_in_series(self):
        for idx, show in enumerate(self.__video_db):
            viewings = show.get("viewings", None)
            if not viewings:
                return idx

            # get duration component of end field
            final_viewing = viewings[-1]["end"].split(" at ")[1]

            # if the final viewing didn't complete the show then it is next
            if final_viewing != "finished?" and final_viewing != show.get(
                "duration", None
            ):
                return idx

        return None

    def get_next_in_series(self):
        next_index = self.get_next_index_in_series()
        if next_index is None:
            return None
        else:
            next_entry = self.__video_db[next_index]
            alias = next_entry.get("alias", None)
            if alias:
                self.aliased_db = Db()
                self.aliased_db.load_series(alias)
            return next_entry

    def prune_watched(self):
        next_index = self.get_next_index_in_series()
        if next_index:
            self.__video_db = self.__video_db[next_index:]

    def add_show_to_series(self, video_data):
        self.__video_db.append(video_data)

    def write_series(self, dirpath):
        filepath = Db.get_series_db_path(dirpath)
        save_yaml_file(filepath, self.__video_db)

    def get_series_video_set(self):
        return set(map(lambda entry: entry["video"], self.__video_db))

    @staticmethod
    def get_series_db_path(dirpath):
        return os.path.join(dirpath, ".videos.yaml")

    def load_global_record(self):
        self.__video_db = load_yaml_file(Db.get_global_record_db_path())

    def get_matching_entries(self, filter_expression):
        return filter(filter_expression, self.__video_db)

    def filter_db(self, filter_expression):
        self.__video_db = list(self.get_matching_entries(filter_expression))

    def append_global_record(self, record):
        save_yaml_file(Db.get_global_record_db_path(), [record], "a")

    @staticmethod
    def get_global_record_db_path():
        return os.path.expanduser("~/.videorecord.yaml")
