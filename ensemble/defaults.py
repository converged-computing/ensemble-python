workers = 10
port = 50051

supported_members = ["flux", "minicluster"]
valid_actions = ["submit", "custom", "terminate", "grow", "shrink"]
heartbeat_seconds = 60

job_events = [
    "job-depend",
    "job-sched",
    "job-run",
    "job-cancel",
    "job-cleanup",
    "job-finish",
    "job-success",
    "job-fail",
]
