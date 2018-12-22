import os
from .yaml import yaml

# set this when the end is unknown... assume it finished sometime
UNKNOWN_END = 'sometime at finished?'

def _load_yaml_file(filepath):
    with open(filepath, 'r') as stream:
        try:
            return yaml.load(stream)
        except yaml.YAMLError as err:
            raise ValueError(*err.args)

def _dump_yaml_file(filepath, data, mode = 'w'):
    with open(filepath, mode) as stream:
        try:
            return yaml.dump(data, stream)
        except yaml.YAMLError as err:
            raise ValueError(*err.args)

def _load_old_db(filepath, global_variation):
    db_entries = []
    with open(filepath, 'r') as fp:
        for _, line in enumerate(fp):
            line = line.rstrip('\n')
            video_data = {}

            if global_variation or line[0] == '*':
                if not global_variation:
                    # remove the *
                    line = line[1:]

                start = 'sometime'
                space_idx = line.index(' ')
                if line[0] != ' ':
                    start = line[:space_idx].replace('-', '/').replace('~', ' ')
                video_file = line[space_idx + 1:]
                video_data['video'] = video_file
                video_data['viewings'] = [ { 'start': start, 'end': UNKNOWN_END } ]
            else:
                video_data['video'] = line
            db_entries.append(video_data)
    return db_entries

def _series_entry_to_global_record(video_data):
    record = video_data.copy()
    # convert viewings to simpler form for global log
    record.pop('viewings', None)
    viewings = video_data.get('viewings', None)
    if viewings:
        record['start'] = viewings[0]['start']
        end = viewings[0].get('end', UNKNOWN_END)
        if end != UNKNOWN_END:
            record['end'] = end
    return record

class Db:
    def __init__(self):
        self.__series_db = []
        self.__db = []

    def load_series(self, dirpath):
        db_path = Db.get_series_db_path(dirpath)
        self.__series_db = _load_yaml_file(db_path)

    def load_series_v0(self, dirpath):
        filepath = os.path.join(dirpath, '.showlist')
        if not os.path.isfile(filepath):
            raise ValueError('database does not exist in this directory')
        old_entries = _load_old_db(filepath, False)
        for video_data in old_entries:
            self.add_show_to_series(video_data)

    def get_next_in_series(self):
        for show in self.__series_db:
            viewings = show.get('viewings', None)
            if not viewings:
                return show

            # get duration component of end field
            final_viewing = viewings[-1]['end'].split(' at ')[1]

            # if the final viewing didn't complete the show then it is next
            if final_viewing != 'finished?' and final_viewing != show.get('duration', None):
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

    def load_global_record_v0(self):
        old_db_path = os.path.expanduser('~/.showtimes')
        old_entries = _load_old_db(old_db_path, True)
        for video_data in old_entries:
            record = _series_entry_to_global_record(video_data)
            self.add_show_to_global_record(record)

    def write_global_record(self):
        _dump_yaml_file(Db.get_global_record_db_path(), self.__db)

    def append_global_record(self, record):
        _dump_yaml_file(Db.get_global_record_db_path(), [record], 'a')

    @staticmethod
    def get_global_record_db_path():
        return os.path.expanduser('~/.videorecord.yaml')
