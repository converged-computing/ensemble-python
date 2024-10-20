workers = 10
port = 50051

valid_actions = ["submit", "custom", "terminate"]
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
