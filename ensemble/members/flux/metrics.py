import collections
import sys

try:
    import flux
    import flux.job
    import flux.resource
except ImportError:
    sys.exit("Cannot import flux. Please ensure that flux Python bindings are on the PYTHONPATH.")


def get_node_metrics(handle):
    """
    Single function to get node metrics:

    core free count
    core up count
    node up count
    node free count
    """
    rpc = flux.resource.list.resource_list(handle)
    listing = rpc.get()
    return {
        "node_cores_free": listing.free.ncores,
        "node_cores_up": listing.up.ncores,
        "node_up_count": len(listing.up.nodelist),
        "node_free_count": len(listing.free.nodelist),
    }


def get_next_jobs(handle, stop_at=None, states=None):
    """
    Get the next N jobs in the queue. States include:

    DEPEND, PRIORITY, SCHED, RUN, CLEANUP, and INACTIVE
    """
    states = states or ["DEPEND", "PRIORITY", "SCHED", "RUN", "CLEANUP", "INACTIVE"]
    jobs = flux.job.job_list(handle)
    listing = jobs.get()
    next_jobs = []

    count = 0
    for item in listing.get("jobs", []):
        # We only want jobs that aren't running or inactive
        state = flux.job.info.statetostr(item["state"])

        # Assume these might need resources.
        # If the cluster had enough nodes and they were free,
        # it would be running, so we don't include RUN
        if state not in states:
            continue
        next_jobs.append(item)

        # Arbitrary cutoff
        if stop_at is not None and count == stop_at:
            break
        count += 1

    # Sort by submit time - the ones we submit first should
    # go back to the operator first
    return sorted(next_jobs, key=lambda d: d["t_submit"])


def get_waiting_sizes(handle):
    """
    Get waiting sizes (nodes that each jobs needs)

    This is the granularity the ensemble operator can adjust.
    """
    jobs = flux.job.job_list(handle)
    listing = jobs.get()
    counts = {}

    # Get counts of nodes needed
    # this is a lookup of node counts to jobs that need it
    for item in listing.get("jobs", []):
        key = item["nnodes"]
        if key not in counts:
            counts[key] = 0
        counts[key] += 1
    return counts


def get_queue_metrics(handle):
    """
    Get updated metrics for counts of jobs in the queue

    See https://github.com/flux-framework/flux-core/blob/master/src/common/libjob/job.h#L45-L53
    for identifiers.
    """
    jobs = flux.job.job_list(handle)
    listing = jobs.get()

    # Organize based on states
    states = [x["state"] for x in listing["jobs"]]
    counter = collections.Counter(states)

    # Lookup of state name to integer
    lookup = {
        "new": 1,
        "depend": 2,
        "priority": 4,
        "sched": 8,
        "run": 16,
        "cleanup": 32,
        "inactive": 64,
    }

    # This is how to get states
    counts = {}
    for stateint, count in counter.items():
        state = flux.job.info.statetostr(stateint)
        state = state.lower()
        counts[state] = count
    for state in lookup:
        if state not in counts:
            counts[state] = 0

    return counts


# Organize metric functions by name
metrics = {
    "nodes": get_node_metrics,
    "queue": get_queue_metrics,
    "waiting": get_waiting_sizes,
    "nextJobs": get_next_jobs,
}
