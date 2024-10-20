import ensemble.config as cfg
from ensemble.logger import LogColors
from ensemble.members.metrics import QueueMetrics

# Examples for status in the future
# "{LogColors.OKBLUE}{js.name}{LogColors.ENDC} {LogColors.RED}NOT OK{LogColors.ENDC}"                    )
# "{LogColors.OKBLUE}{js.name}{LogColors.ENDC} {LogColors.RED}NOT OK{LogColors.ENDC}"


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

    def terminate(self):
        """
        Custom termination function

        Often the executor needs custom logic to work.
        """
        pass

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

    def execute_rule(self, rule, record=None):
        """
        Given a rule and associated action extracted, run it!
        """
        # Was the rule already done?
        if rule.disabled:
            return

        # Metrics can have a "when"
        if rule.trigger == "metric":
            return self.execute_metric_action(rule)

        # Do we want to submit a job?
        self.execute_action(rule, record)

    def announce(self, message, meta=None, ljust=15, color="cyan"):
        """
        Announce an event (with colors for the viewer)
        """
        end = "\n"
        extra = ""
        if meta is not None:
            end = ""

        prefix = message.ljust(ljust)
        if color == "cyan":
            print(f"{LogColors.OKCYAN}{prefix}{LogColors.ENDC}{extra}", end=end)
        elif color == "blue":
            print(f"{LogColors.OKBLUE}{prefix}{LogColors.ENDC}{extra}", end=end)
        if meta is not None:
            print(f"{LogColors.PURPLE}{meta}{LogColors.ENDC}".ljust(10))

    def execute_action(self, rule, record=None):
        """
        Execute a general action, it's assumed that
        the trigger was called if we get here. Those supported by
        Flux and the MiniCluster: submit, custom, terminate.
        MiniCluster Only: shrink and grow.
        """
        # This function checks for repetitions and backoff
        # periods, and determines if we should continue (to run)
        # or not this time. If it returns True, the action is
        # also updated to indicate running.
        if not rule.action.perform():
            return

        self.announce(f" => trigger {rule.name}", color="blue")
        if rule.action.name == "submit":
            self.announce(f"   submit {rule.action.label} ", self.cfg.pretty_job(rule.action.label))
            return self.submit(rule, record)

        # These all have the same logic to call the function of the same name
        if rule.action.name in ["custom", "grow", "shrink"]:
            run_action = getattr(self, rule.action.name, None)

            # Not supported if the function does not exist
            if not run_action:
                raise NotImplementedError("Action {rule.action.name} is not supported.")
            self.announce(f"   {rule.action.name} {rule.action.label}")
            run_action(rule, record)

        # Note that terminate exits but does not otherwise touch
        # the queue, etc. Given a reactor, we should just stop it
        if rule.action.name == "terminate":
            self.announce("   terminate ensemble session")
            self.terminate()

    def execute_metric_action(self, rule, record=None):
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
        if self.cfg.debug_logging:
            print(self.metrics.models)
        return self.execute_action(rule, record)

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
