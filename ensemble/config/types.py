import re

import ensemble.defaults as defaults


class Rule:
    """
    A rule wraps an action with additional metadata
    """

    def __init__(self, rule, module=None):
        self._rule = rule
        self.disabled = False
        self.action = Action(rule["action"], module)
        self.validate()

    @property
    def name(self):
        return self._rule.get("name") or self.trigger

    @property
    def trigger(self):
        return self._rule["trigger"]

    def run_when(self, value):
        """
        Check if "when" is relevant to be run now, return True/False
        to say to run or not.
        """
        # No when is set, so we just continue assuming there is no when
        if self.when is None:
            return True

        # If we have a direct value, we check for equality
        if isinstance(value, int) and value != self.when:
            return False

        # Otherwise, parse for inequality
        match = re.search(r"(?P<inequality>[<>]=?)\s*(?P<comparator>\w+)", value).groupdict()

        # This could technically be a float value
        comparator = float(match["comparator"])
        inequality = match["inequality"]
        assert inequality in {"<", ">", "<=", ">=", "==", "="}

        # Evaluate! Not sure there is a better way than this :)
        if inequality == "<":
            return value < comparator
        if inequality == "<=":
            return value <= comparator
        if inequality == ">":
            return value > comparator
        if inequality == ">=":
            return value >= comparator
        if inequality in ["==", "="]:
            return value == comparator
        raise ValueError(f"Invalid comparator {comparator} for rule when")

    def check_when(self):
        """
        Ensure we have a valid inequality before running anything!
        """
        # If a number, we require greater than == 0
        if isinstance(self.when, int) and self.when >= 0:
            return

        # Check running the function with a value, should not raise error
        try:
            self.run_when(10)
        except Exception as err:
            raise ValueError(f"when: for rule {self} is not valid: {err}")

    @property
    def when(self):
        return self._rule.get("when")

    def validate(self):
        """
        Validate the rule and associated action
        """
        # Is the action name valid?
        if self.action.name not in defaults.valid_actions:
            raise ValueError(
                f"Rule trigger {self.trigger} has invalid action name {self.action.name}"
            )
        # Ensure we have a valid number or inequality
        self.check_when()


class Action:
    """
    An action holds a name, and metadata about the action.
    """

    def __init__(self, action, module=None):
        self._action = action

        # We parse this because the value will change
        # and we don't want to destroy the original setting
        self.parse_frequency()
        if self.name == "custom":
            self.customize(module)

    def customize(self, module):
        """
        For custom actions, we need have already written
        and loaded the module, and need to check that the
        function is defined.
        """
        self.func = getattr(module, self.label, None)
        if not self.func:
            raise ValueError(f"Custom function {self.label} is not defined.")

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
