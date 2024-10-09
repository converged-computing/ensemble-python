# ensemble

![PyPI - Version](https://img.shields.io/pypi/v/ensemble-python)

An HPC ensemble is an orchestration of jobs that can ideally be controlled by an algorithm. Ensemble (in python) is a project to do exactly that. As a user, you specify the parameters for your job, and then an algorithm and options for it. The library hear listens for the heartbeat of your ensemble -- events that come directly from the queue or entity that is controlling the jobs.
This means that we define:

- A number of executors (typically queues) that can deliver events (heartbeats)
- Rules for when to submit jobs (at onset, at periods during running)
- Rules for when to stop, cancel, or terminate
- Parameters for the jobs (what will be converted into a job specification for the queue to consume)
- Rules for when to change the environment (cluster) like growing or shrinking, if supported

At a high level, we need to be able to define events, and rules for transitioning to new states.  There should be an executor or queue interface that can support any kind of workload manager queue that can return the expected types.

🚧 Under Construction! 🚧

## Design

This design will be translated into more consolidated design documentation. For now I'm putting it here.

### Concepts

- **Executor** provides a queue backend that should handle sending events. While a poll oriented design could work, it's not ideal. In the context of the ensemble, the queue executor is referred to as a **member**.
- **Ensemble Service**: provides grpc endpoints for one or more ensemble members to communicate with. This is an explicit design decision that, for example, would allow deploying one service that is orchestrating multiple things at once.
- **Rules**: A rule is composed of a trigger and action to take, and this is what drives the ensemble, more akin to a state machine than a traditional workflow DAG because the structure can be unknown at the start. For example, you might say "on the start of the ensemble, submit these jobs with label X."
- **Triggers**: A trigger is part of a rule (described above) and in the configuration file, and can be read as "when this trigger happens, do this action."
- **Action**: An actual is an operation that is the result of hitting a trigger condition. It is typically performed by the queue, and thus must be known to it. Example actions include submit, scale-up, scale-down, or terminate.
- **Metrics** are summary metrics collected for groups of jobs, for FYI or (coming soon) customized algorithms. To support this, we use online (or streaming) ML algorithms for things like mean, IQR, etc.

#### Rules

A rule defines a trigger "on" and action to take. The library is event driven, meaning that the queue is expected to send events, and we don't do any polling.

##### Triggers

The current triggers supported are the following. Triggered when:

- job-depend: A job is in the depends state
- job-sched: A job is in the sched state
- job-run: A job is in the run state
- job-cnacel: A job is cancelled
- job-cleanup: A job is in the cleanup state
- job-finish: A job is finished (success or failure)
- job-success: A job succeeds and has a zero exit code
- job-fail: A job finishes and has a non-zero exit code
- start: The init of the entire ensemble (only happens once)
- interval: Occurs at an interval (requires interval in seconds as an option)

#### Metrics

We use streaming ML "stats" for each job group, and then a subset of variables. For example, when a job finishes we calculate the duration and update stats for that family and the duration variable.

```console
🌊 Streaming ML Model Summary:
   name      : sleep-duration
   variance  : 5.186765321241182e-06
   mean      : 10.02671468257904
   iqr       : 0.003220796585083008
   max       : 10.028325080871582
   min       : 10.025104284286499
   mad       : 0.003220796585083008
   count     : 2
```

That only has two entries (so the data isn't huge) but it's a start.
Also note that this does not distinguish between failed and successful runs. We would either want to only include successful, or keep them separate.

### Overview

Since this will need to handle many ensembles, I'm going to try designing it as a service. There will be grpc endpoints that can receive messages.

- Each queue or executor will have its own separate running process. E.g., for Flux we will have a script running alongside a broker with a flux handle. This should ideally use events (but is not required to if the queue does not support that).
- A custom rule can have a trigger, and then return another rule. This means that:
 - return "None" to do nothing
 - return an action to do the action immediately
 - return a rule to add to the set

## Example

Let's do an example running in the Development container, where we have flux. You can do the following:

```bash
# Start a flux instance
flux start --test-size=4

# Install in development mode, and run "make" to rebuild proto if necessary
sudo pip install -e .

# Start the server
ensemble-server start

# Run your ensemble! it will submit and monitor job events, etc
ensemble run examples/hello-world.yaml
```

Right now, this will run any rules with "start" triggers, which for this hello world example includes a few hello world jobs! You'll then be able to watch and see flux events coming in!

<details>

<summary>Example Ensemble Run</summary>

```console
 ensemble run examples/hello-world.yaml
  ⭐️ Submit job ['sleep', '10']: ƒD2kHJipp7
  ⭐️ Submit job ['sleep', '10']: ƒD2kHtpYJ3
{'id': 1540612620812288, 'events': [{'timestamp': 1728416529.2622762, 'name': 'submit', 'context': {'userid': 1000, 'urgency': 16, 'flags': 0, 'version': 1}}, {'timestamp': 1728416529.2734637, 'name': 'validate'}, {'timestamp': 1728416529.2843053, 'name': 'depend'}, {'timestamp': 1728416529.284362, 'name': 'priority', 'context': {'priority': 16}}, {'timestamp': 1728416529.2854803, 'name': 'alloc'}, {'timestamp': 1728416529.287176, 'name': 'start'}], 'jobspec': {'resources': [{'type': 'node', 'count': 1, 'with': [{'type': 'slot', 'count': 1, 'with': [{'type': 'core', 'count': 1}], 'label': 'task'}]}], 'tasks': [{'command': ['sleep', '10'], 'slot': 'task', 'count': {'per_slot': 1}}], 'attributes': {'system': {'duration': 0.0}}, 'version': 1}, 'R': {'version': 1, 'execution': {'R_lite': [{'rank': '3', 'children': {'core': '7'}}], 'nodelist': ['08c63b4a360d'], 'starttime': 1728416529, 'expiration': 4881924701}}}
{'id': 1540613006688256, 'events': [{'timestamp': 1728416529.285812, 'name': 'submit', 'context': {'userid': 1000, 'urgency': 16, 'flags': 0, 'version': 1}}, {'timestamp': 1728416529.2962706, 'name': 'validate'}, {'timestamp': 1728416529.3070736, 'name': 'depend'}, {'timestamp': 1728416529.307108, 'name': 'priority', 'context': {'priority': 16}}], 'jobspec': {'resources': [{'type': 'node', 'count': 1, 'with': [{'type': 'slot', 'count': 1, 'with': [{'type': 'core', 'count': 1}], 'label': 'task'}]}], 'tasks': [{'command': ['sleep', '10'], 'slot': 'task', 'count': {'per_slot': 1}}], 'attributes': {'system': {'duration': 0.0}}, 'version': 1}}
{'id': -1, 'events': []}
{'id': 1540613006688256, 'events': [{'timestamp': 1728416529.308137, 'name': 'annotations', 'context': {'annotations': None}}]}
{'id': 1540613006688256, 'events': [{'timestamp': 1728416529.3081472, 'name': 'alloc'}], 'R': {'version': 1, 'execution': {'R_lite': [{'rank': '3', 'children': {'core': '6'}}], 'nodelist': ['08c63b4a360d'], 'starttime': 1728416529, 'expiration': 4881924701}}}
{'id': 1540613006688256, 'events': [{'timestamp': 1728416529.3094273, 'name': 'start'}]}
```


</details>

## Development

We are going to use flux, so the provided [Development Container](.devcontainer) supports that.
Once you are in the container:

```bash
flux start --test-size=4
```

You can then test the MiniCluster monitoring tool (separately):

```bash
python3 -m ensemble.members.flux
```

### Questions or Items to DO

- What if we want to change the algorithm used for different parts of the run? Possible or too complex?
- We will want parameters, etc. to vary based on custom functions.
- Likely a custom function should be able to return None and then actions or other rules.
- Move verbose readme into proper docs
- Add metrics that can keep summary stats for job groups, and for the queue, and we should be able to act on them. Then add other action triggers and finish the simple hello world example.
- The metrics recording is a source of data for ML learning, need to figure out the right interface for that.
- Should we separate fails/successes or just record successes for now?

## License

HPCIC DevTools is distributed under the terms of the MIT license.
All new contributions must be made under this license.

See [LICENSE](https://github.com/converged-computing/cloud-select/blob/main/LICENSE),
[COPYRIGHT](https://github.com/converged-computing/cloud-select/blob/main/COPYRIGHT), and
[NOTICE](https://github.com/converged-computing/cloud-select/blob/main/NOTICE) for details.

SPDX-License-Identifier: (MIT)

LLNL-CODE- 842614
