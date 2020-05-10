from ruamel.yaml import YAML, YAMLError

yaml = YAML(typ='safe')
yaml.default_flow_style = False
yaml.width = 1000  # type: ignore
yaml.sort_base_mapping_type_on_output = False  # type: ignore


def load_yaml_file(filepath):
    with open(filepath, 'r') as stream:
        try:
            return yaml.load(stream)
        except YAMLError as err:
            raise ValueError(*err.args)
