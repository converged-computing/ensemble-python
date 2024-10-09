import json
import shlex
import sys

import ensemble.members as members
import ensemble.members.flux.metrics as metrics
from ensemble.members.base import MemberBase
from ensemble.protos import ensemble_service_pb2

try:
    import flux
    import flux.constants
    import flux.job
    import flux.rpc
except ImportError:
    sys.exit("flux python is required to use the flux queue member")

rules = ["start"]


class FluxQueue(MemberBase):
    """
    The Flux Queue member type
    """

    # Rule triggers supported by the flux queue - the "on" directive
    rules = rules

    def __init__(self, job_filters=None, include_inactive=False, refresh_interval=0, **kwargs):
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

        # TODO this is where we can add streaming ML algorithms to learn things.
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
                self.metrics.summary(group_name)

        # TODO custom triggers -> actions!

    def record_event(self, event):
        """
        Record the event. This needs to be specific to the workload manager.
        """
        # Is this the sentinel?
        # The sentinel tells us when the "backlog" is finished
        if not self.seen_sentinel:
            if event["id"] == -1:
                print("Sentinel is seen, starting event monitoring.")
                self.seen_sentinel = True
                return

        # Record metrics for the event
        self.record_metrics(event)

        # print("respond to event")
        # print(event)

    def start(self):
        """
        Init the events subscriber (no longer pub sub but a callback)
        to the flux queue. See:

        https://github.com/flux-framework/flux-core/blob/master/src/modules/job-manager/journal.c#L11-L41
        """
        # Start events are different.
        for rule in self.iter_rules("start"):
            self.run_action(rule["action"])

        def event_callback(response):
            """
            Receive callback when a flux job posts an event.
            """
            payload = response.get()
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
        label = action.get("label")

        # Default to all jobs
        jobs = self.cfg["jobs"]
        if label is not None:
            # Get labeled jobs (can be more than one set)
            jobs = self.get_labeled_jobs(label)
            if not jobs:
                print(f"Warning: no jobs match label {label}")
                return

        # Now submit, likely randomized
        for group in jobs:
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


# (api.EnsembleOperatorServicer)
class EnsembleEndpoint:
    """
    An EnsembleEndpoint runs inside the cluster.
    """

    def job_info(self):
        """
        Return job info (more detailed than status)
        """
        listing = flux.job.job_list(self.handle)
        return listing.get()

    def status(self):
        """
        Ask the flux queue (metrics) for a status
        """
        # Prepare a payload to send back
        payload = {}

        # The payload is the metrics listing
        for name, func in metrics.metrics.items():
            payload[name] = func()

        return payload

    def count_inactive(self, queue):
        """
        Keep a count of inactive jobs.

        Each time we cycle through, we want to check if the queue is active
        (or not). If not, we add one to the increment, and this represents the number
        of subsequent inactive queue states we have seen. If we see the queue is active
        we reset the counter at 0. An algorithm can use this to determine a cluster
        termination status e.g., "terminate after inactive for N checks."
        Return the increment to the counter, plus a boolean to say "reset" (or not)
        """
        active_jobs = (
            queue["new"]
            + queue["run"]
            + queue["depend"]
            + queue["sched"]
            + queue["priority"]
            + queue["cleanup"]
        )
        if active_jobs == 0:
            return 1, False
        return 0, True

    def count_waiting(self, queue):
        """
        Keep a count of waiting jobs
        """
        return queue["new"] + queue["depend"] + queue["sched"] + queue["priority"]

    def record_event(self, event):
        """
        A global log to keep track of state.
        """
        global cache
        if event not in cache:
            cache[event] = 0
        cache[event] += 1

    def get_event(self, event, default):
        """
        Get an event from the log
        """
        global cache
        return cache.get(event) or default

    def count_inactive_periods(self, increment, reset=False):
        """
        Keep a count of inactive jobs.

        Each time we cycle through, we want to check if the queue is active
        (or not). If not, we add one to the increment, because an algorithm can
        use this to determine a cluster termination status.
        """
        return self.increment_period("inactive_periods", increment, reset)

    def reset_counter(self, payload):
        """
        Reset a named counter
        """
        global cache
        payload = json.loads(payload)
        if isinstance(payload, str):
            payload = [payload]
        for key in payload:
            if key in cache:
                print(f"Resetting counter for {key}")
                cache[key] = 0

    def count_waiting_periods(self, current_waiting):
        """
        Count subsequent waiting periods that are == or greater than last count

        This is an indicator that the queue is not moving. We are interested to see
        if the number of waiting has changed. We would want to trigger scaling events,
        for example, if the number waiting does not change over some period.
        We return the number waiting, and waiting periods >= the last check.
        """
        global cache
        previous_waiting = cache.get("waiting")

        # If we don't have a previous value, it's akin to 0
        # And this is an increase in waiting
        if previous_waiting is None or (current_waiting >= previous_waiting):
            return self.increment_period("waiting_periods", 1, False)

        # If we get here, the current waiting is < previous waiting, so we reset
        return self.increment_period("waiting_periods", 0, True)

    def count_free_nodes_increasing_periods(self, nodes):
        """
        Given nodes, count number of free nodes, and increasing periods.
        """
        global cache
        current_free = nodes.get("node_free_count")
        previous_free = cache.get("free_nodes")

        # If we haven't set this before, or we have more free nodes
        # add a count of 1 to the period
        if previous_free is None or (current_free > previous_free):
            return self.increment_period("free_nodes", 1, False)

        # This means current free is less than the previous free
        # so the nodes are being used (and we reset)
        return self.increment_period("free_nodes", 0, True)

    def increment_period(self, key, increment, reset):
        """
        Given a counter in in the cache, increment it or reset
        """
        global cache
        if key not in cache:
            cache[key] = 0
        if increment:
            cache[key] += increment
        elif reset:
            cache[key] = 0
        return cache[key]

    def RequestStatus(self, request, context):
        """
        Request information about queues and jobs.
        """
        global cache
        global metrics

        print(context)
        print(f"Member type: {request.member}")

        # Record count of check to our cache
        self.record_event("status")

        # This will raise an error if the member type is not known
        member = members.get_member(request.member)

        # If the flux handle didn't work, this might error
        try:
            payload = member.status()
        except Exception as e:
            print(e)
            return ensemble_service_pb2.Response(
                status=ensemble_service_pb2.Response.ResultType.ERROR
            )

        # Prepare counts for the payload
        payload["counts"] = {}

        # Add the count of status checks to our payload
        payload["counts"]["status"] = self.get_event("status", 0)

        # Increment by 1 if we are still inactive, otherwise reset
        # note that we don't send over an actual inactive count, inactive here is the
        # period, largely because we don't need it. This isn't true for waiting
        increment, reset = member.count_inactive(payload["queue"])
        payload["counts"]["inactive"] = self.count_inactive_periods(increment, reset)

        # Increment by 1 if number waiting is the same or greater
        waiting_jobs = member.count_waiting(payload["queue"])
        payload["counts"]["waiting_periods"] = self.count_waiting_periods(payload["counts"])

        # This needs to be updated after so the cache has the previous waiting for the call above
        payload["counts"]["waiting"] = waiting_jobs

        # Finally, keep track of number of periods that we have free nodes increasing
        payload["counts"]["free_nodes"] = self.count_free_nodes_increasing_periods(payload["nodes"])

        # Always update the last timestamp when we do a status
        metrics.tick()
        payload["metrics"] = metrics.to_dict()
        print(json.dumps(payload))

        return ensemble_service_pb2.Response(
            payload=json.dumps(payload),
            status=ensemble_service_pb2.Response.ResultType.SUCCESS,
        )

    def RequestAction(self, request, context):
        """
        Request an action is performed according to an algorithm.
        """
        print(f"Algorithm {request.algorithm}")
        print(f"Action {request.action}")
        print(f"Payload {request.payload}")

        # Assume first successful response
        # status = ensemble_service_pb2.Response.ResultType.SUCCESS
        response = ensemble_service_pb2.Response()

        # The member primarily is directed to take the action
        member = members.get_member(request.member)
        if request.action == "submit":
            try:
                member.submit(request.payload)
            except Exception as e:
                print(e)
                response.status = ensemble_service_pb2.Response.ResultType.ERROR

        # Reset a counter, typically after an update event
        elif request.action == "resetCounter":
            try:
                self.reset_counter(request.payload)
            except Exception as e:
                print(e)
                response.status = ensemble_service_pb2.Response.ResultType.ERROR

        # This can give a final dump / view of job info
        elif request.action == "jobinfo":
            try:
                infos = member.job_info()
                if infos:
                    print(json.dumps(infos, indent=4))
                    response.payload = json.dumps(infos)
            except Exception as e:
                print(e)
                response.status = ensemble_service_pb2.Response.ResultType.ERROR

        return response
