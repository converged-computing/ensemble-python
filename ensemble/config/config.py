import jsonschema

import ensemble.utils as utils
from ensemble import schema

# Right now assume all executors have the same actions
valid_actions = ["submit"]


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

    def check_supported(self, supported):
        """
        Check that all rules all supported
        """
        supported = set(supported)
        for trigger in self.rules:
            if trigger not in supported:
                raise ValueError(f"Rule trigger '{trigger}' is not supported by {self.name}")

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

    def parse(self):
        """
        Parse config into organized pieces for more efficient lookup.
        """
        for rule in self._cfg["rules"]:
            rule = Rule(rule)

            # Group rules with common trigger together
            if rule.trigger not in self.rules:
                self.rules[rule.trigger] = []

            # Rules are removed when they are performed
            self.rules[rule.trigger].append(rule)

        for job in self._cfg["jobs"]:
            if job["name"] not in self.jobs:
                self.jobs[job["name"]] = []
            self.jobs[job["name"]].append(job)


class Rule:
    """
    A rule wraps an action with additional metadata
    """

    def __init__(self, rule):
        self._rule = rule
        self.disabled = False
        self.action = Action(rule["action"])
        self.validate()

    @property
    def name(self):
        return self._rule["name"]

    @property
    def trigger(self):
        return self._rule["trigger"]

    @property
    def when(self):
        return self._rule["when"]

    def validate(self):
        """
        Validate the rule and associated action
        """
        # Is the action name valid?
        if self.action.name not in valid_actions:
            raise ValueError(
                f"Rule trigger {self.trigger} has invalid action name {self.action.name}"
            )


class Action:
    """
    An action holds a name, and metadata about the action.
    """

    def __init__(self, action):
        self._action = action

        # All actions start not being run. By default, we assume
        # they should be run once. This can change.
        self.performed = False

    @property
    def name(self):
        return self._action.get("name")

    @property
    def label(self):
        return self._action.get("label")
