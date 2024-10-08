import ensemble.utils as utils
from ensemble import schema
import jsonschema


def load_config(config_path):
    """
    Load the config path, validating with the schema
    """
    cfg = utils.read_yaml(config_path)
    jsonschema.validate(cfg, schema=schema.ensemble_config_schema)
    return cfg
