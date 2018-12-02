import yaml
import os

def __load_yaml_file(filepath):
    with open(filepath, 'r') as stream:
        try:
            return yaml.safe_load(stream)
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
                print('TODO: load line into DB', line)

        print('debug: ', self.__series_db)

    def write_series(self, dirpath):
        print('TODO: write current ', dirpath)

    def get_series_db_path(self, dirpath):
        return os.path.join(dirpath, '.showlist.yaml')

