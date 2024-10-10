import shlex
import sys

from ensemble.members.base import MemberBase

try:
    import flux
    import flux.constants
    import flux.job
    import flux.rpc
except ImportError:
    sys.exit("flux python is required to use the flux queue member")

rules = ["start", "metric"]


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
        group = self.jobids.get(record["id"])

        # This should only be one, but we will not assume
        for event in record.get("events", []):
            # Skip these events... but note that alloc has the R in it
            # if we eventually want that for something.
            if event in ["annotations", "alloc"]:
                continue

            # We want to keep the start time
            if event["name"] == "start":
                self.jobids[record["id"]]["start"] = event["timestamp"]

            if event["name"] == "finish":
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

        # Once events are recorded, trigger actions associated
        # with event updates. This is usually counts, etc.
        for rule in self.iter_rules("metric"):
            self.execute_rule(rule)

        # TODO custom triggers -> actions!

    def summarize(self):
        """
        Summarize the jobs at some frequency
        """
        self.completion_counter += 1

        # Time for a summary?
        if self.completion_counter == self.summary_freqency:
            self.metrics.summarize_all()
            self.completion_counter = 0

    def record_event(self, event):
        """
        Record the event. This needs to be specific to the workload manager.
        """
        # The sentinel tells us when the "backlog" is finished
        if not self.seen_sentinel:
            if event["id"] == -1:
                print("Sentinel is seen, starting event monitoring.")
                self.seen_sentinel = True
                return

        # Record metrics for the event
        self.record_metrics(event)

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
            # TODO be more selective about what we print here
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
                print(f"  ⭐️ Submit job {job['command']}: {jobid}")

                # This is the job id that will show up in events
                numerical = jobid.as_integer_ratio()[0]
                self.jobids[numerical] = {"name": group["name"]}

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
