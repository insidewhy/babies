import yaml
import os

def __load_yaml_file(filepath):
    with open(filepath, 'r') as stream:
        try:
            return yaml.safe_load(stream)
        except yaml.YAMLError as err:
            raise ValueError(*err.args)

def dump_yaml_file(filepath, data):
    with open(filepath, 'w') as stream:
        try:
            return yaml.safe_dump(data, stream, default_flow_style=False)
        except yaml.YAMLError as err:
            raise ValueError(*err.args)

class Db:
    def __init__(self):
        self.__series_db = []

    def load_series(self, dirpath):
        print('TODO: load series database', dirpath)

    def load_series_v0(self, dirpath):
        filepath = os.path.join(dirpath, '.showlist')
        if not os.path.isfile(filepath):
            raise ValueError('database does not exist in this directory')

        with open(filepath, 'r') as fp:
            for _, line in enumerate(fp):
                line = line.rstrip('\n')
                video_data = {}
                if line[0] == '*':
                    start = 'unknown'
                    space_idx = line.index(' ')
                    if line[1] != ' ':
                        start = line[1:space_idx].replace('-', '/').replace('~', ' ') + ' at 00:00'
                    video_file = line[space_idx + 1:]
                    video_data['video'] = video_file
                    video_data['viewings'] = [ { 'start': start, 'end': 'finished?' } ]
                else:
                    video_data['video'] = line
                self.__series_db.append(video_data)

    def write_series(self, dirpath):
        filepath = self.get_series_db_path(dirpath)
        dump_yaml_file(filepath, self.__series_db)

    def get_series_db_path(self, dirpath):
        return os.path.join(dirpath, '.showlist.yaml')

