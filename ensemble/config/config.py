import jsonschema

import ensemble.utils as utils
from ensemble import schema
from ensemble.logger.generate import JobNamer
from ensemble.config.types import Rule
import shutil
import importlib
import random
import os

# Right now assume all executors have the same actions
script_template = """from ensemble.config.types import Action, Rule
"""


def load_config(config_path):
    """
    Load the config path, validating with the schema
    """
    cfg = utils.read_yaml(config_path)
    jsonschema.validate(cfg, schema=schema.ensemble_config_schema)
    return EnsembleConfig(cfg)


class EnsembleConfig:
    """
    An ensemble config better organizes rules
    for easier access. It's expected to only be loaded once.
    """

    def __init__(self, cfg):
        self._cfg = cfg
        self.jobs = {}
        self.rules = {}
        self.parse()

        # Cache of action names
        self.actions = set()

    @property
    def debug_logging(self):
        return self._cfg.get("logging", {}).get("debug") is True

    def pretty_job(self, name):
        """
        Pretty print a job (for the logger) across a single line
        """
        if name not in self.jobs:
            raise ValueError(f'job with name "{name}" is not known')

        # Each job group can have more than one set
        return utils.pretty_print_list(self.jobs[name])

    def check_supported(self, supported):
        """
        Check that all rules all supported
        """
        supported = set(supported)
        for trigger in self.rules:
            if trigger not in supported:
                raise ValueError(f"Rule trigger '{trigger}' is not supported.")

    def iter_jobs(self, label=None):
        """
        Yield jobs by name (or not)
        """
        if not label:
            labels = list(self.jobs)
        else:
            labels = [label]
        for label in labels:
            for jobset in self.jobs[label]:
                yield jobset

    def customize(self):
        """
        For custom actions, we need to write to a template
        file, and then import and make the function available on
        the action.
        """
        # Add imports to the custom script
        script = script_template + self._cfg["custom"]
        tmpdir = utils.get_tmpdir()
        script_name = "_".join([random.choice(JobNamer._descriptors) for _ in range(2)])
        script_path = os.path.join(tmpdir, f"{script_name}.py")
        utils.write_file(script, script_path)

        # module will have custom functions
        spec = importlib.util.spec_from_file_location(script_name, script_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.custom = module
        shutil.rmtree(tmpdir)

    def parse(self):
        """
        Parse config into organized pieces for more efficient lookup.
        """
        self.custom = None
        if self._cfg.get("custom") is not None:
            self.customize()

        for rule in self._cfg["rules"]:
            rule = Rule(rule, self.custom)

            # Group rules with common trigger together
            if rule.trigger not in self.rules:
                self.rules[rule.trigger] = []

            # Rules are removed when they are performed
            self.rules[rule.trigger].append(rule)

        for job in self._cfg["jobs"]:
            if job["name"] not in self.jobs:
                self.jobs[job["name"]] = []
            self.jobs[job["name"]].append(job)
