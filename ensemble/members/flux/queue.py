import shlex
import sys
from datetime import datetime

from ensemble.members.base import MemberBase

try:
    import flux
    import flux.constants
    import flux.job
    import flux.rpc
except ImportError:
    sys.exit("flux python is required to use the flux queue member")

# These are triggers supported for rules
rules = ["start", "metric"]

# Through cleanup are actual flux events, and the rest we derive
# Note that each of these has custom metadata we could use (but don't yet)
# https://flux-framework.readthedocs.io/projects/flux-rfc/en/latest/spec_21.html
job_events = [
    "submit",
    "jobspec-update",
    "resource-update",
    "validate",
    "invalidate",
    "set-flags",
    "dependency-add",
    "dependency-remove",
    "depend",
    "priority",
    "flux-restart",
    "urgency",
    "alloc",
    "prolog-start",
    "prolog-finish",
    "epilog-start",
    "epilog-finish",
    "free",
    "start",
    "release",
    "finish",
    "clean",
    "exception",
    "memo",
    "debug",
]
rules += [f"job-{x}" for x in job_events]


class FluxQueue(MemberBase):
    """
    The Flux Queue member type
    """

    # Rule triggers supported by the flux queue - the "on" directive
    rules_supported = rules

    def __init__(
        self,
        job_filters=None,
        include_inactive=False,
        refresh_interval=0,
        summary_frequency=10,
        **kwargs,
    ):
        """
        Create a new flux handle to monitor a queue.

        Parameters:
        job_filters (dict)     : key value pairs for attributes or states to filter jobs to
        include_inactive (bool): consider and include inactive jobs when doing initial parse
        refresh_interval (int) : number of seconds to refresh all metrics (0 indicates no refresh)
        """
        # Filter jobs to any attributes, states, or similar.
        self.filters = job_filters or {}
        self.handle = flux.Flux()
        self.include_inactive = include_inactive
        self.refresh_interval = refresh_interval

        # How often on job completions to summarize?
        self.summary_freqency = summary_frequency
        self.completion_counter = 0

        # The flux sentinel tells us when we have finished with the backlog
        # https://github.com/flux-framework/flux-core/blob/master/src/modules/job-manager/journal.c#L28-L33
        self.seen_sentinel = False

        # We store the job id associated with a group until it's cleaned up
        self.jobids = {}
        super().__init__(**kwargs)

    @property
    def name(self):
        return "FluxQueue"

    def record_metrics(self, record):
        """
        Parse a Flux event and record metrics for the group.
        """
        # This should only be one after the sentinal, but we will not assume
        for event in record.get("events", []):
            # Skip these events... but note that alloc has the R in it
            # if we eventually want that for something.
            if event in ["annotations", "alloc"]:
                continue

            # We want to keep the start timestamp for duration
            if event["name"] == "start":
                self.record_start_metrics(event, record)

            # We want to keep the submit timestamp for time in queue
            if event["name"] == "submit":
                self.record_submit_metrics(event, record)

            # Job finish
            if event["name"] == "finish":
                self.record_finish_metrics(event, record)

        # Once events are recorded, trigger actions associated
        # with metric event updates. This is usually counts, etc.
        for rule in self.iter_rules("metric"):
            self.execute_rule(rule)

        # TODO custom triggers -> actions!

    def record_start_metrics(self, event, record):
        """
        We typically want to keep the job start time for the
        overall job duration, and calculate time in queue (pending)
        """
        group = self.jobids.get(record["id"])

        # We are interested in time in the queue
        self.jobids[record["id"]]["start"] = event["timestamp"]

        # Time in the queue is the start time (larger) - submit time
        time_in_queue = event["timestamp"] - group["submit"]

        # Pending time is time in the queue
        group_name = f"{group['name']}-pending"
        self.metrics.record_datum(group_name, time_in_queue)

    def record_submit_metrics(self, event, record):
        """
        We typically want to keep the job submit time to calculate
        time in the queue, which is the start timestamp - submit ts.
        """
        self.jobids[record["id"]]["submit"] = event["timestamp"]

    def record_finish_metrics(self, event, record):
        """
        Record metrics at the finish of jobs, typically duration
        and breaking apart by success / failure vs. just completed
        """
        group = self.jobids.get(record["id"])

        # We are interested in duration
        duration = event["timestamp"] - group["start"]

        # Let's do a group name of group-<variable>
        group_name = f"{group['name']}-duration"
        self.metrics.record_datum(group_name, duration)

        # Clean up the job from history here, we are done
        del self.jobids[record["id"]]

        # Increment finished jobs by one
        self.metrics.increment(group["name"], "finished")
        if event["context"]["status"] == 0:
            self.metrics.increment(group["name"], "success")
        else:
            self.metrics.increment(group["name"], "failed")
        self.summarize()

    def summarize(self):
        """
        Summarize the jobs at some frequency
        """
        self.completion_counter += 1

        # Time for a summary?
        if self.completion_counter == self.summary_freqency:
            if self.cfg.debug_logging:
                self.metrics.summarize_all()
            self.completion_counter = 0

    def record_event(self, record):
        """
        Record the event. This needs to be specific to the workload manager.
        """
        # The sentinel tells us when the "backlog" is finished
        if not self.seen_sentinel:
            if record["id"] == -1:
                if self.cfg.debug_logging:
                    print("Sentinel is seen, starting event monitoring.")
                self.seen_sentinel = True
                return

        # Record metrics for the event
        self.record_metrics(record)

        # Check to see if the ensemble has any triggers for the event
        # Unlike metrics (automated) these are event triggers from
        # the ensemble rules
        for event in record["events"]:
            self.check_event(record, event)

    def check_event(self, record, event):
        """
        Given a record (with a job id and other metadata) and an associated
        event, check if there are any rules for it
        """
        # The rules that the user defines are namespaced to jobs, so
        # we add the prefix of "job-" the event, assuming it is a job
        # I'm not sure if there are other prefixes relevant here, but
        # I am namespacing it to prepare for that possibility
        job_event = f"job-{event['name']}"
        for rule in self.iter_rules(job_event):
            self.execute_rule(rule)

    def start(self):
        """
        Init the events subscriber (no longer pub sub but a callback)
        to the flux queue. See:

        https://github.com/flux-framework/flux-core/blob/master/src/modules/job-manager/journal.c#L11-L41
        """
        # Iterate through actions provided by the rule
        for rule in self.iter_rules("start"):
            self.execute_rule(rule)

        def event_callback(response):
            """
            Receive callback when a flux job posts an event.
            """
            payload = response.get()

            # Only print if the config has logging->debug set to true
            if self.cfg.debug_logging:
                print(payload)
            response.reset()
            self.record_event(payload)

        events = self.handle.rpc(
            "job-manager.events-journal",
            {},
            flux.constants.FLUX_NODEID_ANY,
            flags=flux.constants.FLUX_RPC_STREAMING,
        )
        events.then(event_callback)
        self.handle.reactor_run()

    def submit(self, action):
        """
        Receive the flux handle and StatusRequest payload to act on.
        """
        # Dp we want to target a specific job label?
        # Now submit, likely randomized
        for group in self.cfg.iter_jobs(action.label):
            jobset = self.extract_jobs(group)

            for job in jobset:
                jobspec = flux.job.JobspecV1.from_command(
                    command=job["command"], num_nodes=job["nodes"], num_tasks=job["tasks"]
                )
                workdir = job["workdir"]

                # Set user attribute we can later retrieve to identify group
                jobspec.attributes["user"] = {"group": group["name"]}

                # Do we have a working directory?
                if workdir:
                    jobspec.cwd = workdir

                # Use direction or default to 0, unlimited
                jobspec.duration = job["duration"]
                jobid = flux.job.submit(self.handle, jobspec)

                # Don't rely on an event here, this is when the user (us) submits
                submit_time = datetime.now().timestamp()

                # This is the job id that will show up in events
                numerical = jobid.as_integer_ratio()[0]
                self.jobids[numerical] = {"name": group["name"], "submit-timestamp": submit_time}

    def extract_jobs(self, group):
        """
        Given the payload, extract and order jobs
        """
        jobs = []
        tasks = group.get("tasks") or 1
        nodes = group.get("nodes") or 1

        for _ in range(group.get("count", 1)):
            jobs.append(
                {
                    "command": shlex.split(group["command"]),
                    "workdir": group.get("workdir"),
                    "nodes": nodes,
                    "duration": group.get("duration") or 0,
                    "tasks": tasks,
                }
            )
        return jobs
