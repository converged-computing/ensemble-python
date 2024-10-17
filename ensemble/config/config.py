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
        result = ""
        jobs = self.jobs[name]
        for i, job in enumerate(jobs):
            result += "".join(f"({k}:{v})," for k, v in job.items())
            if len(jobs) > 1 and i != len(jobs) - 1:
                result += "\n"
        return result.strip(",")

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
        return self.trigger

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

        # We parse this because the value will change
        # and we don't want to destroy the original setting
        self.parse_frequency()

    def parse_frequency(self):
        """
        Parse the action frequency, which by default, is to run
        it once. An additional backoff period (number of periods to skip)
        can also be provided.
        """
        self.repetitions = self._action.get("repetitions", 1)

        # Backoff between repetitions (this is global setting)
        # Setting to None indicates backoff is not active
        self.backoff = self._action.get("backoff")

        # Counter between repetitions
        self.backoff_counter = 0

    def perform(self):
        """
        Return True or False to indicate performing an action.
        """
        # If we are out of repetitions, no matter what, we don't run
        if self.finished:
            return False

        # The action is flagged to have some total backoff periods between repetitions
        if self.backoff is not None and self.backoff >= 0:
            return self.perform_backoff()

        # If we get here, backoff is not set (None) and repetitions > 0
        self.repetitions -= 1
        return True

    def perform_backoff(self):
        """
        Perform backoff (going through the logic of checking the
        period we are on, and deciding to run or not, and decrementing
        counters) to return a boolean if we should run the action or not.
        """
        # But we are still going through a period
        if self.backoff_counter > 0:
            self.backoff_counter -= 1
            return False

        # The backoff counter has expired - it is zero here
        # reset the counter to the original value
        self.backoff_counter = self.backoff

        # Decrement repetitions
        self.repetitions -= 1

        # And signal to run the action
        return True

    @property
    def name(self):
        return self._action.get("name")

    @property
    def finished(self):
        """
        An action is finished when it has no more repetitions
        It should never go below zero, in practice.
        """
        return self.repetitions <= 0

    @property
    def label(self):
        return self._action.get("label")
