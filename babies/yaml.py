from ruamel.yaml import YAML

yaml = YAML(typ='safe')
yaml.default_flow_style = False
yaml.sort_base_mapping_type_on_output = False
