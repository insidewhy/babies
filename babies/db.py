import os
from .yaml import yaml
from ruamel.yaml import YAMLError
from typing import Dict, List, Union

# set this when the end is unknown... assume it finished sometime
UNKNOWN_END = 'sometime at finished?'

VideoData = Dict[str, Union[str, List[Dict[str, str]]]]
VideoDb = List[VideoData]


def _load_yaml_file(filepath):
    with open(filepath, 'r') as stream:
        try:
            return yaml.load(stream)
        except YAMLError as err:
            raise ValueError(*err.args)


def _dump_yaml_file(filepath, data, mode='w'):
    with open(filepath, mode) as stream:
        try:
            return yaml.dump(data, stream)
        except YAMLError as err:
            raise ValueError(*err.args)


def _load_old_db(filepath, global_variation):
    db_entries = []
    with open(filepath, 'r') as fp:
        for _, line in enumerate(fp):
            line = line.rstrip('\n')
            video_data: VideoData = {}

            if global_variation or line[0] == '*':
                if not global_variation:
                    # remove the *
                    line = line[1:]

                start = 'sometime'
                space_idx = line.index(' ')
                if line[0] != ' ':
                    start = line[:space_idx]\
                        .replace('-', '/').replace('~', ' ')
                video_file = line[space_idx + 1:]
                video_data['video'] = video_file
                video_data['viewings'] = [{'start': start, 'end': UNKNOWN_END}]
            else:
                video_data['video'] = line
            db_entries.append(video_data)
    return db_entries


class Db:
    def __init__(self):
        self.__series_db: VideoDb = []
        self.__db: VideoDb = []

    def load_series(self, dirpath):
        db_path = Db.get_series_db_path(dirpath)
        self.__series_db = _load_yaml_file(db_path)

    def get_next_in_series(self):
        for show in self.__series_db:
            viewings = show.get('viewings', None)
            if not viewings:
                return show

            # get duration component of end field
            final_viewing = viewings[-1]['end'].split(' at ')[1]

            # if the final viewing didn't complete the show then it is next
            if (final_viewing != 'finished?' and
                    final_viewing != show.get('duration', None)):
                return show

        return None

    def add_show_to_series(self, video_data):
        self.__series_db.append(video_data)

    def write_series(self, dirpath):
        filepath = Db.get_series_db_path(dirpath)
        _dump_yaml_file(filepath, self.__series_db)

    @staticmethod
    def get_series_db_path(dirpath):
        return os.path.join(dirpath, '.videos.yaml')

    def load_global_record(self):
        self.__series_db = _load_yaml_file(Db.get_global_record_db_path())

    def filter_global_record(self, filter_expression):
        return filter(filter_expression, self.__series_db)

    def add_show_to_global_record(self, record):
        self.__db.append(record)

    def write_global_record(self):
        _dump_yaml_file(Db.get_global_record_db_path(), self.__db)

    def append_global_record(self, record):
        _dump_yaml_file(Db.get_global_record_db_path(), [record], 'a')

    @staticmethod
    def get_global_record_db_path():
        return os.path.expanduser('~/.videorecord.yaml')
