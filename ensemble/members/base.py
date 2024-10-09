import ensemble.config as cfg
from ensemble.members.metrics import QueueMetrics

# Right now assume all executors have the same actions
valid_actions = ["submit"]


class MemberBase:
    """
    The MemberBase is an abstract base to show functions defined.
    """

    def __init__(self, **options):
        """
        Create a new member type (e.g., FluxQueue)
        """
        # Set options as attributes
        for key, value in options.items():
            setattr(self, key, value)

        # Common queue metrics
        self.metrics = QueueMetrics()
        if not hasattr(self, "rules") or not self.rules:
            raise ValueError("The queue executor needs to have a list of supported rules.")

    @property
    def name(self):
        raise NotImplementedError

    def record_metrics(self, event):
        """
        Record group metrics for the event.
        """
        raise NotImplementedError

    def iter_rules(self, name):
        """
        Yield events that match a name
        """
        for rule in self.cfg.get("rules", []):
            if rule["trigger"] == name:
                yield rule

    def get_labeled_jobs(self, label):
        """
        Get jobs that match a specific label
        """
        jobs = []
        for jobset in self.cfg["jobs"]:
            name = jobset.get("name")
            if name and name == label:
                jobs.append(jobset)
        return jobs

    def run_action(self, action):
        """
        Given an action extracted from a rule, run it!
        """
        if action["name"] == "submit":
            self.submit(action)

    def validate_rules(self):
        """
        Validate that rules from cfg are supported by the executor queue.

        We also check the actions contained within.
        """
        supported = set(self.rules)
        for rule in self.cfg["rules"]:
            trigger = rule["trigger"]
            if trigger not in supported:
                raise ValueError(f"Rule trigger {trigger} is not supported by {self.name}")
            action_name = rule["action"]["name"]
            if action_name not in valid_actions:
                raise ValueError(f"Rule trigger {trigger} has invalid action name {action_name}")

    def load(self, config_path):
        """
        Load and validate the config path
        """
        self.cfg = cfg.load_config(config_path)
        # All rules that the ensemble provides must be
        # supported by the queue executor
        self.validate_rules()

    def start(self, *args, **kwargs):
        """
        Submit a job
        """
        raise NotImplementedError

    def submit(self, *args, **kwargs):
        """
        Submit a job
        """
        raise NotImplementedError

    def status(self, *args, **kwargs):
        """
        Ask the member for a status
        """
        raise NotImplementedError
