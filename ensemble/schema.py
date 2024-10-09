import ensemble.defaults as defaults

ensemble_config_schema = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "$id": "https://github.com/converged-computing/ensemble/tree/main/ensemble/schema.py",
    "title": "ensemble-01",
    "description": "Ensemble Python Config",
    "type": "object",
    # The only required thing is the algorithm, since we can respond to jobs that
    # are submit otherwise in the queue.
    "required": ["rules"],
    "properties": {
        "attributes": {"$ref": "#/definitions/algorithm"},
        "jobs": {"$ref": "#/definitions/jobs"},
        "rules": {"$ref": "#/definitions/rules"},
        "additionalProperties": False,
    },
    "definitions": {
        "jobs": {
            "type": ["array"],
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "command": {"type": "string"},
                    "workdir": {"type": "string"},
                    "count": {"type": "number", "default": 1},
                    "nodes": {"type": "number", "default": 1},
                    "tasks": {"type": "number"},
                    "duration": {"type": "number"},
                },
                "required": ["name", "command"],
            },
        },
        "rules": {
            "description": "rules that govern ensemble behavior",
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    # the trigger can coincide with a job state
                    # and error / result code (non zero or not). For now:
                    # job-depend, job-sched, job-run, job-cleanup,
                    # job-success, job-inactive, job-fail, job-cancel. These are events that
                    # coincide with setting up the tool here:
                    # start, interval
                    "trigger": {
                        "type": "string",
                        "enum": defaults.job_events
                        + [
                            "start",
                            "interval",
                        ],
                    },
                    "action": {
                        "type": "object",
                        "items": {
                            "properties": {
                                "name": {"type": "string"},
                                "label": {"type": "string"},
                            },
                            "required": ["name"],
                        },
                    },
                },
                "required": ["trigger", "action"],
            },
        },
    },
}
