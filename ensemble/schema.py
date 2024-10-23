import ensemble.defaults as defaults

ensemble_config_schema = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "$id": "https://github.com/converged-computing/ensemble/tree/main/ensemble/schema.py",
    "title": "ensemble-01",
    "description": "Ensemble Python Config",
    "type": "object",
    # The only required thing is the algorithm, since we can respond to jobs that
    # are submit otherwise in the queue.
    "required": ["rules", "jobs"],
    "properties": {
        "jobs": {"$ref": "#/definitions/jobs"},
        "rules": {"$ref": "#/definitions/rules"},
        "logging": {"$ref": "#/definitions/logging"},
        "custom": {"type": "string"},
        "additionalProperties": False,
    },
    "definitions": {
        "logging": {
            "type": "object",
            "properties": {
                "debug": {"type": "boolean", "default": False},
                "heartbeat": {"type": "number"},
            },
            "additionalProperties": False,
        },
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
                    "name": {"type": "string"},
                    "when": {"type": ["string", "number"]},
                    "trigger": {
                        "type": "string",
                        "enum": defaults.job_events
                        + [
                            "start",
                            "metric",
                        ],
                    },
                    "action": {
                        "type": "object",
                        "items": {
                            "properties": {
                                "name": {"type": "string"},
                                "value": {"type": ["number", "string"]},
                                "label": {"type": ["number", "string"]},
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
