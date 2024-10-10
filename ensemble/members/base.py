import ensemble.config as cfg
from ensemble.members.metrics import QueueMetrics


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
        if not hasattr(self, "rules_supported") or not self.rules_supported:
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
        if name not in self.cfg.rules:
            return
        for rule in self.cfg.rules[name]:
            yield rule

    def execute_rule(self, rule):
        """
        Given a rule and associated action extracted, run it!
        """
        # Metrics can have a "when"
        if rule.trigger == "metric":
            return self.execute_metric_action(rule)

        # Do we want to submit a job?
        return self.execute_action(rule.action)

    def execute_action(self, action):
        """
        Execute a general action, it's assumed that
        the trigger was called if we get here.
        """
        if action.name == "submit":
            return self.submit(action)

        # TODO add actions for job states
        print("UNSEEN ACTION")
        import IPython

        IPython.embed()

    def execute_metric_action(self, rule):
        """
        Execute a metric action.
        """
        # Parse the metric
        metric_path = rule.name.split(".")
        item = self.metrics.models
        for path in metric_path:
            if path not in item:
                return
            item = item[path]

        # The user set a "when" and it must match exactly.
        if rule.when is not None and item.get() != rule.when:
            return
        print(self.metrics.models)
        return self.execute_action(rule.action)

    def validate_rules(self):
        """
        Validate that rules from cfg are supported by the executor queue.

        We also check the actions contained within.
        """
        self.cfg.check_supported(self.rules_supported)

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
