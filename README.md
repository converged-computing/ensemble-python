# ensemble

![PyPI - Version](https://img.shields.io/pypi/v/ensemble-python)

An HPC ensemble is an orchestration of jobs that can ideally be controlled by an algorithm. Ensemble (in python) is a project to do exactly that. As a user, you specify the parameters for your job, and then an algorithm and options for it. The library hear listens for the heartbeat of your ensemble -- events that come directly from the queue or entity that is controlling the jobs.
This means that we define:

- A number of executors (typically queues) that can deliver events (job completion events to start)
- Rules for when to submit jobs (at onset, at periods during running)
- Rules for when to stop, cancel, or terminate
- Parameters for the jobs (what will be converted into a job specification for the queue to consume)
- Rules for when to change the environment (cluster) like growing or shrinking, if supported
- A set of online (streaming) ML metrics (e.g., mean, median or MAD, min/max, etc) that are recorded for each job group and state (finished, failed succeeded)

At a high level, we need to be able to define events, and rules for transitioning to new states. This even means we could make infinite loops (I accidentally already did). There should be an executor or queue interface that can support any kind of workload manager queue that can return the expected types.

🚧 Under Construction! 🚧

## Design

This design will be translated into more consolidated design documentation. For now I'm putting it here.

### Concepts

- **Executor** provides a queue backend that should handle sending events. While a poll oriented design could work, it's not ideal. In the context of the ensemble, the queue executor is referred to as a **member**.
- **Ensemble Service**: provides grpc endpoints for one or more ensemble members to communicate with. This is an explicit design decision that, for example, would allow deploying one service that is orchestrating multiple things at once.
- **Rules**: A rule is composed of a trigger and action to take, and this is what drives the ensemble, more akin to a state machine than a traditional workflow DAG because the structure can be unknown at the start. For example, you might say "on the start of the ensemble, submit these jobs with label X."
- **Triggers**: A trigger is part of a rule (described above) and in the configuration file, and can be read as "when this trigger happens, do this action."
- **Action**: An actual is an operation that is the result of hitting a trigger condition. It is typically performed by the queue, and thus must be known to it. Example actions include submit, scale-up, scale-down, or terminate.
- **Metrics** are summary metrics collected for groups of jobs, for customized algorithms. To support this, we use online (or streaming) ML algorithms for things like mean, IQR, etc. While there could be a named entity called an algorithm, since it's just a set of rules (triggers and actions) that means we don't need to explicitly define them (yet). I can see at some point creating "packaged" rule sets that are called that.

#### Rules

A rule defines a trigger and action to take. The library is event driven, meaning that the queue is expected to send events, and we don't do any polling.

##### Triggers

The current triggers supported are the following. Triggered when:

- start: The init of the entire ensemble (only happens once)
- metric: Triggered when a queue metric is updated
- job-depend: A job is in the depends state
- job-sched: A job is in the sched state
- job-run: A job is in the run state
- job-cnacel: A job is cancelled
- job-cleanup: A job is in the cleanup state
- job-finish: A job is finished (success or failure)
- job-success: A job succeeds and has a zero exit code
- job-fail: A job finishes and has a non-zero exit code

#### Metrics

We use streaming ML "stats" for each job group, and then a subset of variables. For example, when a job finishes we calculate the duration and update stats for that family and the duration variable.

```console
🌊 Streaming ML Model Summary:
   name      : echo-duration
   variance  : 3.561605860855515e-07
   mean      : 0.013609373569488525
   iqr       : 0.00041562974899014317
   max       : 0.014329195022583008
   min       : 0.011783838272094727
   mad       : 0.00024357753771322735
```

Along with that, we take counts of everything! Here is after running two groups of jobs, where one job group was triggered to run after a count of the first was recorded.

```console
{'variance': {'sleep-duration': Var: 0.000006, 'echo-duration': Var: 0.}, 'mean': {'sleep-duration': Mean: 10.015157, 'echo-duration': Mean: 0.013609}, 'iqr': {'sleep-duration': IQR: 0.003083, 'echo-duration': IQR: 0.000416}, 'max': {'sleep-duration': Max: 10.020326, 'echo-duration': Max: 0.014329}, 'min': {'sleep-duration': Min: 10.012975, 'echo-duration': Min: 0.011784}, 'mad': {'sleep-duration': MAD: 0.001754, 'echo-duration': MAD: 0.000244}, 'count': {'sleep': {'finished': Count: 10., 'success': Count: 10.}, 'echo': {'finished': Count: 20., 'success': Count: 20.}}}
```

### Overview

Since this will need to handle many ensembles, I'm going to try designing it as a service. But note that it doesn't _need_ to be run as one (I'm developing and just running flux directly with the command line client, which works too). There will be grpc endpoints that can receive messages. Each queue or executor will have its own separate running process. E.g., for Flux we will have a script running alongside a broker with a flux handle. This should ideally use events (but is not required to if the queue does not support that).

I'm also thinking about what a very custom rule looks like. We have classes for each of rule and action, so I think some function that can fold into that could work. This could also allow customizing triggers (e.g., custom triggers not known to the library that come in the same way).

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

# Start the server (actually you don't need to do this, I'm not using it yet)
ensemble-server start

# Run your ensemble! it will submit and monitor job events, etc
ensemble run examples/hello-world.yaml
```

Right now, this will run any rules with "start" triggers, which for this hello world example includes a few hello world jobs! You'll then be able to watch and see flux events coming in!
Here is the full run - we run a bunch of sleep jobs (10) and when we hit a count of 5, we launch a bunch of echo jobs.

<details>

<summary>Example Ensemble Run</summary>

```console
$ ensemble run examples/hello-world.yaml
  ⭐️ Submit job ['sleep', '10']: ƒTQtKcDXFD
  ⭐️ Submit job ['sleep', '10']: ƒTQtLdX2X1
  ⭐️ Submit job ['sleep', '10']: ƒTQtMF6jHH
  ⭐️ Submit job ['sleep', '10']: ƒTQtMtARKu
  ⭐️ Submit job ['sleep', '10']: ƒTQtNVk86B
{'id': 3382379372609536, 'events': [{'timestamp': 1728526307.1155024, 'name': 'submit', 'context': {'userid': 1000, 'urgency': 16, 'flags': 0, 'version': 1}}, {'timestamp': 1728526307.1266649, 'name': 'validate'}, {'timestamp': 1728526307.138295, 'name': 'depend'}, {'timestamp': 1728526307.1384034, 'name': 'priority', 'context': {'priority': 16}}], 'jobspec': {'resources': [{'type': 'node', 'count': 1, 'with': [{'type': 'slot', 'count': 1, 'with': [{'type': 'core', 'count': 1}], 'label': 'task'}]}], 'tasks': [{'command': ['sleep', '10'], 'slot': 'task', 'count': {'per_slot': 1}}], 'attributes': {'system': {'duration': 0.0}, 'user': {'group': 'sleep'}}, 'version': 1}}
{'id': 3382378969956352, 'events': [{'timestamp': 1728526307.0910742, 'name': 'submit', 'context': {'userid': 1000, 'urgency': 16, 'flags': 0, 'version': 1}}, {'timestamp': 1728526307.1024692, 'name': 'validate'}, {'timestamp': 1728526307.1135828, 'name': 'depend'}, {'timestamp': 1728526307.1137195, 'name': 'priority', 'context': {'priority': 16}}, {'timestamp': 1728526307.1157665, 'name': 'alloc'}, {'timestamp': 1728526307.1175337, 'name': 'start'}], 'jobspec': {'resources': [{'type': 'node', 'count': 1, 'with': [{'type': 'slot', 'count': 1, 'with': [{'type': 'core', 'count': 1}], 'label': 'task'}]}], 'tasks': [{'command': ['sleep', '10'], 'slot': 'task', 'count': {'per_slot': 1}}], 'attributes': {'system': {'duration': 0.0}, 'user': {'group': 'sleep'}}, 'version': 1}, 'R': {'version': 1, 'execution': {'R_lite': [{'rank': '3', 'children': {'core': '4'}}], 'nodelist': ['08c63b4a360d'], 'starttime': 1728526307, 'expiration': 4881924701}}}
{'id': 3382378550525952, 'events': [{'timestamp': 1728526307.0665612, 'name': 'submit', 'context': {'userid': 1000, 'urgency': 16, 'flags': 0, 'version': 1}}, {'timestamp': 1728526307.0778031, 'name': 'validate'}, {'timestamp': 1728526307.0893135, 'name': 'depend'}, {'timestamp': 1728526307.0894418, 'name': 'priority', 'context': {'priority': 16}}, {'timestamp': 1728526307.0915422, 'name': 'alloc'}, {'timestamp': 1728526307.093729, 'name': 'start'}], 'jobspec': {'resources': [{'type': 'node', 'count': 1, 'with': [{'type': 'slot', 'count': 1, 'with': [{'type': 'core', 'count': 1}], 'label': 'task'}]}], 'tasks': [{'command': ['sleep', '10'], 'slot': 'task', 'count': {'per_slot': 1}}], 'attributes': {'system': {'duration': 0.0}, 'user': {'group': 'sleep'}}, 'version': 1}, 'R': {'version': 1, 'execution': {'R_lite': [{'rank': '3', 'children': {'core': '5'}}], 'nodelist': ['08c63b4a360d'], 'starttime': 1728526307, 'expiration': 4881924701}}}
{'id': 3382377476784128, 'events': [{'timestamp': 1728526307.0026248, 'name': 'submit', 'context': {'userid': 1000, 'urgency': 16, 'flags': 0, 'version': 1}}, {'timestamp': 1728526307.0282474, 'name': 'validate'}, {'timestamp': 1728526307.0407536, 'name': 'depend'}, {'timestamp': 1728526307.040926, 'name': 'priority', 'context': {'priority': 16}}, {'timestamp': 1728526307.0427854, 'name': 'alloc'}, {'timestamp': 1728526307.047113, 'name': 'start'}], 'jobspec': {'resources': [{'type': 'node', 'count': 1, 'with': [{'type': 'slot', 'count': 1, 'with': [{'type': 'core', 'count': 1}], 'label': 'task'}]}], 'tasks': [{'command': ['sleep', '10'], 'slot': 'task', 'count': {'per_slot': 1}}], 'attributes': {'system': {'duration': 0.0}, 'user': {'group': 'sleep'}}, 'version': 1}, 'R': {'version': 1, 'execution': {'R_lite': [{'rank': '3', 'children': {'core': '7'}}], 'nodelist': ['08c63b4a360d'], 'starttime': 1728526307, 'expiration': 4881924701}}}
{'id': 3382378147872768, 'events': [{'timestamp': 1728526307.0425975, 'name': 'submit', 'context': {'userid': 1000, 'urgency': 16, 'flags': 0, 'version': 1}}, {'timestamp': 1728526307.054647, 'name': 'validate'}, {'timestamp': 1728526307.0649085, 'name': 'depend'}, {'timestamp': 1728526307.0650547, 'name': 'priority', 'context': {'priority': 16}}, {'timestamp': 1728526307.0667632, 'name': 'alloc'}, {'timestamp': 1728526307.0686884, 'name': 'start'}], 'jobspec': {'resources': [{'type': 'node', 'count': 1, 'with': [{'type': 'slot', 'count': 1, 'with': [{'type': 'core', 'count': 1}], 'label': 'task'}]}], 'tasks': [{'command': ['sleep', '10'], 'slot': 'task', 'count': {'per_slot': 1}}], 'attributes': {'system': {'duration': 0.0}, 'user': {'group': 'sleep'}}, 'version': 1}, 'R': {'version': 1, 'execution': {'R_lite': [{'rank': '3', 'children': {'core': '6'}}], 'nodelist': ['08c63b4a360d'], 'starttime': 1728526307, 'expiration': 4881924701}}}
{'id': -1, 'events': []}
Sentinel is seen, starting event monitoring.
{'id': 3382379372609536, 'events': [{'timestamp': 1728526307.1404595, 'name': 'annotations', 'context': {'annotations': None}}]}
{'id': 3382379372609536, 'events': [{'timestamp': 1728526307.1405733, 'name': 'alloc'}], 'R': {'version': 1, 'execution': {'R_lite': [{'rank': '3', 'children': {'core': '3'}}], 'nodelist': ['08c63b4a360d'], 'starttime': 1728526307, 'expiration': 4881924701}}}
{'id': 3382379372609536, 'events': [{'timestamp': 1728526307.1429424, 'name': 'start'}]}
{'id': 3382377476784128, 'events': [{'timestamp': 1728526317.0632293, 'name': 'finish', 'context': {'status': 0}}]}
{'id': 3382377476784128, 'events': [{'timestamp': 1728526317.0646632, 'name': 'release', 'context': {'ranks': 'all', 'final': True}}]}
{'id': 3382377476784128, 'events': [{'timestamp': 1728526317.0648625, 'name': 'free'}]}
{'id': 3382377476784128, 'events': [{'timestamp': 1728526317.0649548, 'name': 'clean'}]}
{'id': 3382378147872768, 'events': [{'timestamp': 1728526317.0835757, 'name': 'finish', 'context': {'status': 0}}]}
{'id': 3382378147872768, 'events': [{'timestamp': 1728526317.084472, 'name': 'release', 'context': {'ranks': 'all', 'final': True}}]}
{'id': 3382378147872768, 'events': [{'timestamp': 1728526317.0846326, 'name': 'free'}]}
{'id': 3382378147872768, 'events': [{'timestamp': 1728526317.0846925, 'name': 'clean'}]}
{'id': 3382378550525952, 'events': [{'timestamp': 1728526317.1090896, 'name': 'finish', 'context': {'status': 0}}]}
{'variance': {'sleep-duration': Var: 0.}, 'mean': {'sleep-duration': Mean: 10.015455}, 'iqr': {'sleep-duration': IQR: 0.001229}, 'max': {'sleep-duration': Max: 10.016116}, 'min': {'sleep-duration': Min: 10.014887}, 'mad': {'sleep-duration': MAD: 0.}, 'count': {'sleep': {'finished': Count: 3., 'success': Count: 3.}}}
  ⭐️ Submit job ['echo', 'hello', 'world']: ƒTQxozuP1y
  ⭐️ Submit job ['echo', 'hello', 'world']: ƒTQxpfT4Lw
  ⭐️ Submit job ['echo', 'hello', 'world']: ƒTQxqH2m7D
  ⭐️ Submit job ['echo', 'hello', 'world']: ƒTQxqv6T9q
  ⭐️ Submit job ['echo', 'hello', 'world']: ƒTQxrZA9CT
{'id': 3382378550525952, 'events': [{'timestamp': 1728526317.1106362, 'name': 'release', 'context': {'ranks': 'all', 'final': True}}]}
{'variance': {'sleep-duration': Var: 0.}, 'mean': {'sleep-duration': Mean: 10.015455}, 'iqr': {'sleep-duration': IQR: 0.001229}, 'max': {'sleep-duration': Max: 10.016116}, 'min': {'sleep-duration': Min: 10.014887}, 'mad': {'sleep-duration': MAD: 0.}, 'count': {'sleep': {'finished': Count: 3., 'success': Count: 3.}}}
  ⭐️ Submit job ['echo', 'hello', 'world']: ƒTQxs9FrgP
  ⭐️ Submit job ['echo', 'hello', 'world']: ƒTQxskqZSf
  ⭐️ Submit job ['echo', 'hello', 'world']: ƒTQxtNRGCw
  ⭐️ Submit job ['echo', 'hello', 'world']: ƒTQxtyzxyD
  ⭐️ Submit job ['echo', 'hello', 'world']: ƒTQxubafjV
{'id': 3382378550525952, 'events': [{'timestamp': 1728526317.11091, 'name': 'free'}]}
{'variance': {'sleep-duration': Var: 0.}, 'mean': {'sleep-duration': Mean: 10.015455}, 'iqr': {'sleep-duration': IQR: 0.001229}, 'max': {'sleep-duration': Max: 10.016116}, 'min': {'sleep-duration': Min: 10.014887}, 'mad': {'sleep-duration': MAD: 0.}, 'count': {'sleep': {'finished': Count: 3., 'success': Count: 3.}}}
  ⭐️ Submit job ['echo', 'hello', 'world']: ƒTQxvG8M4T
  ⭐️ Submit job ['echo', 'hello', 'world']: ƒTQxvsi3pj
  ⭐️ Submit job ['echo', 'hello', 'world']: ƒTQxwWmjsM
  ⭐️ Submit job ['echo', 'hello', 'world']: ƒTQxx9qRuy
  ⭐️ Submit job ['echo', 'hello', 'world']: ƒTQxxmR8gF
{'id': 3382378550525952, 'events': [{'timestamp': 1728526317.1109884, 'name': 'clean'}]}
{'variance': {'sleep-duration': Var: 0.}, 'mean': {'sleep-duration': Mean: 10.015455}, 'iqr': {'sleep-duration': IQR: 0.001229}, 'max': {'sleep-duration': Max: 10.016116}, 'min': {'sleep-duration': Min: 10.014887}, 'mad': {'sleep-duration': MAD: 0.}, 'count': {'sleep': {'finished': Count: 3., 'success': Count: 3.}}}
  ⭐️ Submit job ['echo', 'hello', 'world']: ƒTQxyNzqSX
  ⭐️ Submit job ['echo', 'hello', 'world']: ƒTQxyzaYCo
  ⭐️ Submit job ['echo', 'hello', 'world']: ƒTQxzdeEFR
  ⭐️ Submit job ['echo', 'hello', 'world']: ƒTQy1FDw1h
  ⭐️ Submit job ['echo', 'hello', 'world']: ƒTQy1tHd4K
{'id': 3382378969956352, 'events': [{'timestamp': 1728526317.1329274, 'name': 'finish', 'context': {'status': 0}}]}
{'id': 3382378969956352, 'events': [{'timestamp': 1728526317.1338842, 'name': 'release', 'context': {'ranks': 'all', 'final': True}}]}
{'id': 3382378969956352, 'events': [{'timestamp': 1728526317.1340613, 'name': 'free'}]}
{'id': 3382378969956352, 'events': [{'timestamp': 1728526317.1341577, 'name': 'clean'}]}
{'id': 3382379372609536, 'events': [{'timestamp': 1728526317.1575787, 'name': 'finish', 'context': {'status': 0}}]}
{'id': 3382379372609536, 'events': [{'timestamp': 1728526317.158493, 'name': 'release', 'context': {'ranks': 'all', 'final': True}}]}
{'id': 3382379372609536, 'events': [{'timestamp': 1728526317.1586344, 'name': 'free'}]}
{'id': 3382379372609536, 'events': [{'timestamp': 1728526317.1586952, 'name': 'clean'}]}
{'id': 3382548386283520, 'events': [{'timestamp': 1728526317.1900442, 'name': 'submit', 'context': {'userid': 1000, 'urgency': 16, 'flags': 0, 'version': 1}}], 'jobspec': {'resources': [{'type': 'node', 'count': 1, 'with': [{'type': 'slot', 'count': 1, 'with': [{'type': 'core', 'count': 1}], 'label': 'task'}]}], 'tasks': [{'command': ['echo', 'hello', 'world'], 'slot': 'task', 'count': {'per_slot': 1}}], 'attributes': {'system': {'duration': 0.0}, 'user': {'group': 'echo'}}, 'version': 1}}
{'id': 3382548386283520, 'events': [{'timestamp': 1728526317.2019808, 'name': 'validate'}]}
{'id': 3382548386283520, 'events': [{'timestamp': 1728526317.2129207, 'name': 'depend'}]}
{'id': 3382548386283520, 'events': [{'timestamp': 1728526317.213049, 'name': 'priority', 'context': {'priority': 16}}]}
{'id': 3382548386283520, 'events': [{'timestamp': 1728526317.2153616, 'name': 'annotations', 'context': {'annotations': None}}]}
{'id': 3382548386283520, 'events': [{'timestamp': 1728526317.215548, 'name': 'alloc'}], 'R': {'version': 1, 'execution': {'R_lite': [{'rank': '3', 'children': {'core': '7'}}], 'nodelist': ['08c63b4a360d'], 'starttime': 1728526317, 'expiration': 4881924701}}}
{'id': 3382548386283520, 'events': [{'timestamp': 1728526317.217442, 'name': 'start'}]}
{'id': 3382548822491136, 'events': [{'timestamp': 1728526317.215159, 'name': 'submit', 'context': {'userid': 1000, 'urgency': 16, 'flags': 0, 'version': 1}}], 'jobspec': {'resources': [{'type': 'node', 'count': 1, 'with': [{'type': 'slot', 'count': 1, 'with': [{'type': 'core', 'count': 1}], 'label': 'task'}]}], 'tasks': [{'command': ['echo', 'hello', 'world'], 'slot': 'task', 'count': {'per_slot': 1}}], 'attributes': {'system': {'duration': 0.0}, 'user': {'group': 'echo'}}, 'version': 1}}
{'id': 3382548386283520, 'events': [{'timestamp': 1728526317.2302418, 'name': 'finish', 'context': {'status': 0}}]}
{'id': 3382548386283520, 'events': [{'timestamp': 1728526317.2314487, 'name': 'release', 'context': {'ranks': 'all', 'final': True}}]}
{'id': 3382548386283520, 'events': [{'timestamp': 1728526317.231568, 'name': 'free'}]}
{'id': 3382548386283520, 'events': [{'timestamp': 1728526317.2316272, 'name': 'clean'}]}
{'id': 3382548822491136, 'events': [{'timestamp': 1728526317.226369, 'name': 'validate'}]}
{'id': 3382548822491136, 'events': [{'timestamp': 1728526317.2381165, 'name': 'depend'}]}
{'id': 3382548822491136, 'events': [{'timestamp': 1728526317.2382553, 'name': 'priority', 'context': {'priority': 16}}]}
{'id': 3382548822491136, 'events': [{'timestamp': 1728526317.2401516, 'name': 'annotations', 'context': {'annotations': None}}]}
{'id': 3382548822491136, 'events': [{'timestamp': 1728526317.2402325, 'name': 'alloc'}], 'R': {'version': 1, 'execution': {'R_lite': [{'rank': '3', 'children': {'core': '7'}}], 'nodelist': ['08c63b4a360d'], 'starttime': 1728526317, 'expiration': 4881924701}}}
{'id': 3382548822491136, 'events': [{'timestamp': 1728526317.242433, 'name': 'start'}]}
{'id': 3382549225144320, 'events': [{'timestamp': 1728526317.2399433, 'name': 'submit', 'context': {'userid': 1000, 'urgency': 16, 'flags': 0, 'version': 1}}], 'jobspec': {'resources': [{'type': 'node', 'count': 1, 'with': [{'type': 'slot', 'count': 1, 'with': [{'type': 'core', 'count': 1}], 'label': 'task'}]}], 'tasks': [{'command': ['echo', 'hello', 'world'], 'slot': 'task', 'count': {'per_slot': 1}}], 'attributes': {'system': {'duration': 0.0}, 'user': {'group': 'echo'}}, 'version': 1}}
{'id': 3382548822491136, 'events': [{'timestamp': 1728526317.2560208, 'name': 'finish', 'context': {'status': 0}}]}
{'id': 3382548822491136, 'events': [{'timestamp': 1728526317.2567422, 'name': 'release', 'context': {'ranks': 'all', 'final': True}}]}
{'id': 3382548822491136, 'events': [{'timestamp': 1728526317.2568886, 'name': 'free'}]}
{'id': 3382548822491136, 'events': [{'timestamp': 1728526317.256976, 'name': 'clean'}]}
{'id': 3382549225144320, 'events': [{'timestamp': 1728526317.2510579, 'name': 'validate'}]}
{'id': 3382549225144320, 'events': [{'timestamp': 1728526317.262773, 'name': 'depend'}]}
{'id': 3382549225144320, 'events': [{'timestamp': 1728526317.2628748, 'name': 'priority', 'context': {'priority': 16}}]}
{'id': 3382549225144320, 'events': [{'timestamp': 1728526317.2646954, 'name': 'annotations', 'context': {'annotations': None}}]}
{'id': 3382549225144320, 'events': [{'timestamp': 1728526317.2648208, 'name': 'alloc'}], 'R': {'version': 1, 'execution': {'R_lite': [{'rank': '3', 'children': {'core': '7'}}], 'nodelist': ['08c63b4a360d'], 'starttime': 1728526317, 'expiration': 4881924701}}}
{'id': 3382549225144320, 'events': [{'timestamp': 1728526317.2668426, 'name': 'start'}]}
{'id': 3382549644574720, 'events': [{'timestamp': 1728526317.2648149, 'name': 'submit', 'context': {'userid': 1000, 'urgency': 16, 'flags': 0, 'version': 1}}], 'jobspec': {'resources': [{'type': 'node', 'count': 1, 'with': [{'type': 'slot', 'count': 1, 'with': [{'type': 'core', 'count': 1}], 'label': 'task'}]}], 'tasks': [{'command': ['echo', 'hello', 'world'], 'slot': 'task', 'count': {'per_slot': 1}}], 'attributes': {'system': {'duration': 0.0}, 'user': {'group': 'echo'}}, 'version': 1}}
{'id': 3382549225144320, 'events': [{'timestamp': 1728526317.279889, 'name': 'finish', 'context': {'status': 0}}]}
{'id': 3382549225144320, 'events': [{'timestamp': 1728526317.2808228, 'name': 'release', 'context': {'ranks': 'all', 'final': True}}]}
{'id': 3382549225144320, 'events': [{'timestamp': 1728526317.2809641, 'name': 'free'}]}
{'id': 3382549225144320, 'events': [{'timestamp': 1728526317.2810438, 'name': 'clean'}]}
{'id': 3382549644574720, 'events': [{'timestamp': 1728526317.2761183, 'name': 'validate'}]}
{'id': 3382549644574720, 'events': [{'timestamp': 1728526317.2872887, 'name': 'depend'}]}
{'id': 3382549644574720, 'events': [{'timestamp': 1728526317.2874835, 'name': 'priority', 'context': {'priority': 16}}]}
{'id': 3382549644574720, 'events': [{'timestamp': 1728526317.2890556, 'name': 'annotations', 'context': {'annotations': None}}]}
{'id': 3382549644574720, 'events': [{'timestamp': 1728526317.289176, 'name': 'alloc'}], 'R': {'version': 1, 'execution': {'R_lite': [{'rank': '3', 'children': {'core': '7'}}], 'nodelist': ['08c63b4a360d'], 'starttime': 1728526317, 'expiration': 4881924701}}}
{'id': 3382549644574720, 'events': [{'timestamp': 1728526317.291113, 'name': 'start'}]}
{'id': 3382550064005120, 'events': [{'timestamp': 1728526317.2890403, 'name': 'submit', 'context': {'userid': 1000, 'urgency': 16, 'flags': 0, 'version': 1}}], 'jobspec': {'resources': [{'type': 'node', 'count': 1, 'with': [{'type': 'slot', 'count': 1, 'with': [{'type': 'core', 'count': 1}], 'label': 'task'}]}], 'tasks': [{'command': ['echo', 'hello', 'world'], 'slot': 'task', 'count': {'per_slot': 1}}], 'attributes': {'system': {'duration': 0.0}, 'user': {'group': 'echo'}}, 'version': 1}}
{'id': 3382549644574720, 'events': [{'timestamp': 1728526317.303957, 'name': 'finish', 'context': {'status': 0}}]}
{'id': 3382549644574720, 'events': [{'timestamp': 1728526317.3046422, 'name': 'release', 'context': {'ranks': 'all', 'final': True}}]}
{'id': 3382549644574720, 'events': [{'timestamp': 1728526317.304741, 'name': 'free'}]}
{'id': 3382549644574720, 'events': [{'timestamp': 1728526317.3047988, 'name': 'clean'}]}
{'id': 3382550064005120, 'events': [{'timestamp': 1728526317.300353, 'name': 'validate'}]}
{'id': 3382550064005120, 'events': [{'timestamp': 1728526317.310683, 'name': 'depend'}]}
{'id': 3382550064005120, 'events': [{'timestamp': 1728526317.3107429, 'name': 'priority', 'context': {'priority': 16}}]}
{'id': 3382550064005120, 'events': [{'timestamp': 1728526317.3124356, 'name': 'annotations', 'context': {'annotations': None}}]}
{'id': 3382550064005120, 'events': [{'timestamp': 1728526317.312506, 'name': 'alloc'}], 'R': {'version': 1, 'execution': {'R_lite': [{'rank': '3', 'children': {'core': '7'}}], 'nodelist': ['08c63b4a360d'], 'starttime': 1728526317, 'expiration': 4881924701}}}
{'id': 3382550064005120, 'events': [{'timestamp': 1728526317.3147388, 'name': 'start'}]}
{'id': 3382550449881088, 'events': [{'timestamp': 1728526317.3124278, 'name': 'submit', 'context': {'userid': 1000, 'urgency': 16, 'flags': 0, 'version': 1}}], 'jobspec': {'resources': [{'type': 'node', 'count': 1, 'with': [{'type': 'slot', 'count': 1, 'with': [{'type': 'core', 'count': 1}], 'label': 'task'}]}], 'tasks': [{'command': ['echo', 'hello', 'world'], 'slot': 'task', 'count': {'per_slot': 1}}], 'attributes': {'system': {'duration': 0.0}, 'user': {'group': 'echo'}}, 'version': 1}}
{'id': 3382550064005120, 'events': [{'timestamp': 1728526317.3269544, 'name': 'finish', 'context': {'status': 0}}]}
🌊 Streaming ML Model Summary:
   name      : sleep-duration
   variance  : 3.2188056025020786e-07
   mean      : 10.015278863906861
   iqr       : 0.0005064010620117188
   max       : 10.016116380691528
   min       : 10.014636278152466
   mad       : 0.0
🌊 Streaming ML Model Summary:
   name      : echo-duration
   variance  : 2.439917182073257e-07
   mean      : 0.012898731231689452
   iqr       : 0.0002467632293701172
   max       : 0.013587713241577148
   min       : 0.012215614318847656
   mad       : 0.0
{'id': 3382550064005120, 'events': [{'timestamp': 1728526317.3277278, 'name': 'release', 'context': {'ranks': 'all', 'final': True}}]}
{'id': 3382550064005120, 'events': [{'timestamp': 1728526317.327839, 'name': 'free'}]}
{'id': 3382550064005120, 'events': [{'timestamp': 1728526317.3278995, 'name': 'clean'}]}
{'id': 3382550449881088, 'events': [{'timestamp': 1728526317.3234818, 'name': 'validate'}]}
{'id': 3382550449881088, 'events': [{'timestamp': 1728526317.3348186, 'name': 'depend'}]}
{'id': 3382550449881088, 'events': [{'timestamp': 1728526317.3348985, 'name': 'priority', 'context': {'priority': 16}}]}
{'id': 3382550449881088, 'events': [{'timestamp': 1728526317.3365633, 'name': 'annotations', 'context': {'annotations': None}}]}
{'id': 3382550449881088, 'events': [{'timestamp': 1728526317.336676, 'name': 'alloc'}], 'R': {'version': 1, 'execution': {'R_lite': [{'rank': '3', 'children': {'core': '7'}}], 'nodelist': ['08c63b4a360d'], 'starttime': 1728526317, 'expiration': 4881924701}}}
{'id': 3382550449881088, 'events': [{'timestamp': 1728526317.3385441, 'name': 'start'}]}
{'id': 3382550852534272, 'events': [{'timestamp': 1728526317.3364434, 'name': 'submit', 'context': {'userid': 1000, 'urgency': 16, 'flags': 0, 'version': 1}}], 'jobspec': {'resources': [{'type': 'node', 'count': 1, 'with': [{'type': 'slot', 'count': 1, 'with': [{'type': 'core', 'count': 1}], 'label': 'task'}]}], 'tasks': [{'command': ['echo', 'hello', 'world'], 'slot': 'task', 'count': {'per_slot': 1}}], 'attributes': {'system': {'duration': 0.0}, 'user': {'group': 'echo'}}, 'version': 1}}
{'id': 3382550449881088, 'events': [{'timestamp': 1728526317.3521721, 'name': 'finish', 'context': {'status': 0}}]}
{'id': 3382550449881088, 'events': [{'timestamp': 1728526317.3529115, 'name': 'release', 'context': {'ranks': 'all', 'final': True}}]}
{'id': 3382550449881088, 'events': [{'timestamp': 1728526317.3530135, 'name': 'free'}]}
{'id': 3382550449881088, 'events': [{'timestamp': 1728526317.3530772, 'name': 'clean'}]}
{'id': 3382550852534272, 'events': [{'timestamp': 1728526317.3482985, 'name': 'validate'}]}
{'id': 3382550852534272, 'events': [{'timestamp': 1728526317.3586028, 'name': 'depend'}]}
{'id': 3382550852534272, 'events': [{'timestamp': 1728526317.3587217, 'name': 'priority', 'context': {'priority': 16}}]}
{'id': 3382550852534272, 'events': [{'timestamp': 1728526317.3607626, 'name': 'annotations', 'context': {'annotations': None}}]}
{'id': 3382550852534272, 'events': [{'timestamp': 1728526317.3609514, 'name': 'alloc'}], 'R': {'version': 1, 'execution': {'R_lite': [{'rank': '3', 'children': {'core': '7'}}], 'nodelist': ['08c63b4a360d'], 'starttime': 1728526317, 'expiration': 4881924701}}}
{'id': 3382550852534272, 'events': [{'timestamp': 1728526317.3630965, 'name': 'start'}]}
{'id': 3382551255187456, 'events': [{'timestamp': 1728526317.3606033, 'name': 'submit', 'context': {'userid': 1000, 'urgency': 16, 'flags': 0, 'version': 1}}], 'jobspec': {'resources': [{'type': 'node', 'count': 1, 'with': [{'type': 'slot', 'count': 1, 'with': [{'type': 'core', 'count': 1}], 'label': 'task'}]}], 'tasks': [{'command': ['echo', 'hello', 'world'], 'slot': 'task', 'count': {'per_slot': 1}}], 'attributes': {'system': {'duration': 0.0}, 'user': {'group': 'echo'}}, 'version': 1}}
{'id': 3382550852534272, 'events': [{'timestamp': 1728526317.3771827, 'name': 'finish', 'context': {'status': 0}}]}
{'id': 3382550852534272, 'events': [{'timestamp': 1728526317.3778691, 'name': 'release', 'context': {'ranks': 'all', 'final': True}}]}
{'id': 3382550852534272, 'events': [{'timestamp': 1728526317.3779824, 'name': 'free'}]}
{'id': 3382550852534272, 'events': [{'timestamp': 1728526317.3780515, 'name': 'clean'}]}
{'id': 3382551255187456, 'events': [{'timestamp': 1728526317.3720236, 'name': 'validate'}]}
{'id': 3382551255187456, 'events': [{'timestamp': 1728526317.3835137, 'name': 'depend'}]}
{'id': 3382551255187456, 'events': [{'timestamp': 1728526317.3836148, 'name': 'priority', 'context': {'priority': 16}}]}
{'id': 3382551255187456, 'events': [{'timestamp': 1728526317.384916, 'name': 'annotations', 'context': {'annotations': None}}]}
{'id': 3382551255187456, 'events': [{'timestamp': 1728526317.385021, 'name': 'alloc'}], 'R': {'version': 1, 'execution': {'R_lite': [{'rank': '3', 'children': {'core': '7'}}], 'nodelist': ['08c63b4a360d'], 'starttime': 1728526317, 'expiration': 4881924701}}}
{'id': 3382551255187456, 'events': [{'timestamp': 1728526317.386854, 'name': 'start'}]}
{'id': 3382551657840640, 'events': [{'timestamp': 1728526317.384926, 'name': 'submit', 'context': {'userid': 1000, 'urgency': 16, 'flags': 0, 'version': 1}}], 'jobspec': {'resources': [{'type': 'node', 'count': 1, 'with': [{'type': 'slot', 'count': 1, 'with': [{'type': 'core', 'count': 1}], 'label': 'task'}]}], 'tasks': [{'command': ['echo', 'hello', 'world'], 'slot': 'task', 'count': {'per_slot': 1}}], 'attributes': {'system': {'duration': 0.0}, 'user': {'group': 'echo'}}, 'version': 1}}
{'id': 3382551255187456, 'events': [{'timestamp': 1728526317.3991315, 'name': 'finish', 'context': {'status': 0}}]}
{'id': 3382551255187456, 'events': [{'timestamp': 1728526317.4000545, 'name': 'release', 'context': {'ranks': 'all', 'final': True}}]}
{'id': 3382551255187456, 'events': [{'timestamp': 1728526317.4003353, 'name': 'free'}]}
{'id': 3382551255187456, 'events': [{'timestamp': 1728526317.4004354, 'name': 'clean'}]}
{'id': 3382551657840640, 'events': [{'timestamp': 1728526317.3960018, 'name': 'validate'}]}
{'id': 3382551657840640, 'events': [{'timestamp': 1728526317.4069932, 'name': 'depend'}]}
{'id': 3382551657840640, 'events': [{'timestamp': 1728526317.4072182, 'name': 'priority', 'context': {'priority': 16}}]}
{'id': 3382551657840640, 'events': [{'timestamp': 1728526317.4089165, 'name': 'annotations', 'context': {'annotations': None}}]}
{'id': 3382551657840640, 'events': [{'timestamp': 1728526317.4090393, 'name': 'alloc'}], 'R': {'version': 1, 'execution': {'R_lite': [{'rank': '3', 'children': {'core': '7'}}], 'nodelist': ['08c63b4a360d'], 'starttime': 1728526317, 'expiration': 4881924701}}}
{'id': 3382551657840640, 'events': [{'timestamp': 1728526317.4109707, 'name': 'start'}]}
{'id': 3382552060493824, 'events': [{'timestamp': 1728526317.4088879, 'name': 'submit', 'context': {'userid': 1000, 'urgency': 16, 'flags': 0, 'version': 1}}], 'jobspec': {'resources': [{'type': 'node', 'count': 1, 'with': [{'type': 'slot', 'count': 1, 'with': [{'type': 'core', 'count': 1}], 'label': 'task'}]}], 'tasks': [{'command': ['echo', 'hello', 'world'], 'slot': 'task', 'count': {'per_slot': 1}}], 'attributes': {'system': {'duration': 0.0}, 'user': {'group': 'echo'}}, 'version': 1}}
{'id': 3382551657840640, 'events': [{'timestamp': 1728526317.4255986, 'name': 'finish', 'context': {'status': 0}}]}
{'id': 3382551657840640, 'events': [{'timestamp': 1728526317.426341, 'name': 'release', 'context': {'ranks': 'all', 'final': True}}]}
{'id': 3382551657840640, 'events': [{'timestamp': 1728526317.4265099, 'name': 'free'}]}
{'id': 3382551657840640, 'events': [{'timestamp': 1728526317.4266434, 'name': 'clean'}]}
{'id': 3382552060493824, 'events': [{'timestamp': 1728526317.420142, 'name': 'validate'}]}
{'id': 3382552060493824, 'events': [{'timestamp': 1728526317.4309936, 'name': 'depend'}]}
{'id': 3382552060493824, 'events': [{'timestamp': 1728526317.431076, 'name': 'priority', 'context': {'priority': 16}}]}
{'id': 3382552060493824, 'events': [{'timestamp': 1728526317.4342852, 'name': 'annotations', 'context': {'annotations': None}}]}
{'id': 3382552060493824, 'events': [{'timestamp': 1728526317.4344735, 'name': 'alloc'}], 'R': {'version': 1, 'execution': {'R_lite': [{'rank': '3', 'children': {'core': '7'}}], 'nodelist': ['08c63b4a360d'], 'starttime': 1728526317, 'expiration': 4881924701}}}
{'id': 3382552060493824, 'events': [{'timestamp': 1728526317.4365342, 'name': 'start'}]}
{'id': 3382552496701440, 'events': [{'timestamp': 1728526317.4345498, 'name': 'submit', 'context': {'userid': 1000, 'urgency': 16, 'flags': 0, 'version': 1}}], 'jobspec': {'resources': [{'type': 'node', 'count': 1, 'with': [{'type': 'slot', 'count': 1, 'with': [{'type': 'core', 'count': 1}], 'label': 'task'}]}], 'tasks': [{'command': ['echo', 'hello', 'world'], 'slot': 'task', 'count': {'per_slot': 1}}], 'attributes': {'system': {'duration': 0.0}, 'user': {'group': 'echo'}}, 'version': 1}}
{'id': 3382552060493824, 'events': [{'timestamp': 1728526317.45027, 'name': 'finish', 'context': {'status': 0}}]}
{'id': 3382552060493824, 'events': [{'timestamp': 1728526317.4510524, 'name': 'release', 'context': {'ranks': 'all', 'final': True}}]}
{'id': 3382552060493824, 'events': [{'timestamp': 1728526317.451151, 'name': 'free'}]}
{'id': 3382552060493824, 'events': [{'timestamp': 1728526317.4512103, 'name': 'clean'}]}
{'id': 3382552496701440, 'events': [{'timestamp': 1728526317.445925, 'name': 'validate'}]}
{'id': 3382552496701440, 'events': [{'timestamp': 1728526317.4566839, 'name': 'depend'}]}
{'id': 3382552496701440, 'events': [{'timestamp': 1728526317.456779, 'name': 'priority', 'context': {'priority': 16}}]}
{'id': 3382552496701440, 'events': [{'timestamp': 1728526317.4584675, 'name': 'annotations', 'context': {'annotations': None}}]}
{'id': 3382552496701440, 'events': [{'timestamp': 1728526317.4585738, 'name': 'alloc'}], 'R': {'version': 1, 'execution': {'R_lite': [{'rank': '3', 'children': {'core': '7'}}], 'nodelist': ['08c63b4a360d'], 'starttime': 1728526317, 'expiration': 4881924701}}}
{'id': 3382552496701440, 'events': [{'timestamp': 1728526317.460425, 'name': 'start'}]}
{'id': 3382552899354624, 'events': [{'timestamp': 1728526317.4584472, 'name': 'submit', 'context': {'userid': 1000, 'urgency': 16, 'flags': 0, 'version': 1}}], 'jobspec': {'resources': [{'type': 'node', 'count': 1, 'with': [{'type': 'slot', 'count': 1, 'with': [{'type': 'core', 'count': 1}], 'label': 'task'}]}], 'tasks': [{'command': ['echo', 'hello', 'world'], 'slot': 'task', 'count': {'per_slot': 1}}], 'attributes': {'system': {'duration': 0.0}, 'user': {'group': 'echo'}}, 'version': 1}}
{'id': 3382552496701440, 'events': [{'timestamp': 1728526317.4778235, 'name': 'finish', 'context': {'status': 0}}]}
{'id': 3382552496701440, 'events': [{'timestamp': 1728526317.4785373, 'name': 'release', 'context': {'ranks': 'all', 'final': True}}]}
{'id': 3382552496701440, 'events': [{'timestamp': 1728526317.478649, 'name': 'free'}]}
{'id': 3382552496701440, 'events': [{'timestamp': 1728526317.4787092, 'name': 'clean'}]}
{'id': 3382552899354624, 'events': [{'timestamp': 1728526317.4696589, 'name': 'validate'}]}
{'id': 3382552899354624, 'events': [{'timestamp': 1728526317.4806852, 'name': 'depend'}]}
{'id': 3382552899354624, 'events': [{'timestamp': 1728526317.4807467, 'name': 'priority', 'context': {'priority': 16}}]}
{'id': 3382552899354624, 'events': [{'timestamp': 1728526317.483454, 'name': 'annotations', 'context': {'annotations': None}}]}
{'id': 3382552899354624, 'events': [{'timestamp': 1728526317.4836454, 'name': 'alloc'}], 'R': {'version': 1, 'execution': {'R_lite': [{'rank': '3', 'children': {'core': '7'}}], 'nodelist': ['08c63b4a360d'], 'starttime': 1728526317, 'expiration': 4881924701}}}
{'id': 3382552899354624, 'events': [{'timestamp': 1728526317.4855063, 'name': 'start'}]}
{'id': 3382553318785024, 'events': [{'timestamp': 1728526317.483651, 'name': 'submit', 'context': {'userid': 1000, 'urgency': 16, 'flags': 0, 'version': 1}}], 'jobspec': {'resources': [{'type': 'node', 'count': 1, 'with': [{'type': 'slot', 'count': 1, 'with': [{'type': 'core', 'count': 1}], 'label': 'task'}]}], 'tasks': [{'command': ['echo', 'hello', 'world'], 'slot': 'task', 'count': {'per_slot': 1}}], 'attributes': {'system': {'duration': 0.0}, 'user': {'group': 'echo'}}, 'version': 1}}
{'id': 3382552899354624, 'events': [{'timestamp': 1728526317.4995677, 'name': 'finish', 'context': {'status': 0}}]}
{'id': 3382552899354624, 'events': [{'timestamp': 1728526317.500376, 'name': 'release', 'context': {'ranks': 'all', 'final': True}}]}
{'id': 3382552899354624, 'events': [{'timestamp': 1728526317.5005121, 'name': 'free'}]}
{'id': 3382552899354624, 'events': [{'timestamp': 1728526317.5005794, 'name': 'clean'}]}
{'id': 3382553318785024, 'events': [{'timestamp': 1728526317.4946837, 'name': 'validate'}]}
{'id': 3382553318785024, 'events': [{'timestamp': 1728526317.5060394, 'name': 'depend'}]}
{'id': 3382553318785024, 'events': [{'timestamp': 1728526317.5061655, 'name': 'priority', 'context': {'priority': 16}}]}
{'id': 3382553318785024, 'events': [{'timestamp': 1728526317.5079794, 'name': 'annotations', 'context': {'annotations': None}}]}
{'id': 3382553318785024, 'events': [{'timestamp': 1728526317.508095, 'name': 'alloc'}], 'R': {'version': 1, 'execution': {'R_lite': [{'rank': '3', 'children': {'core': '7'}}], 'nodelist': ['08c63b4a360d'], 'starttime': 1728526317, 'expiration': 4881924701}}}
{'id': 3382553318785024, 'events': [{'timestamp': 1728526317.5098236, 'name': 'start'}]}
{'id': 3382553738215424, 'events': [{'timestamp': 1728526317.5080924, 'name': 'submit', 'context': {'userid': 1000, 'urgency': 16, 'flags': 0, 'version': 1}}], 'jobspec': {'resources': [{'type': 'node', 'count': 1, 'with': [{'type': 'slot', 'count': 1, 'with': [{'type': 'core', 'count': 1}], 'label': 'task'}]}], 'tasks': [{'command': ['echo', 'hello', 'world'], 'slot': 'task', 'count': {'per_slot': 1}}], 'attributes': {'system': {'duration': 0.0}, 'user': {'group': 'echo'}}, 'version': 1}}
{'id': 3382553318785024, 'events': [{'timestamp': 1728526317.5237067, 'name': 'finish', 'context': {'status': 0}}]}
{'id': 3382553318785024, 'events': [{'timestamp': 1728526317.5245516, 'name': 'release', 'context': {'ranks': 'all', 'final': True}}]}
{'id': 3382553318785024, 'events': [{'timestamp': 1728526317.5247254, 'name': 'free'}]}
{'id': 3382553318785024, 'events': [{'timestamp': 1728526317.5248342, 'name': 'clean'}]}
{'id': 3382553738215424, 'events': [{'timestamp': 1728526317.519369, 'name': 'validate'}]}
{'id': 3382553738215424, 'events': [{'timestamp': 1728526317.5303004, 'name': 'depend'}]}
{'id': 3382553738215424, 'events': [{'timestamp': 1728526317.5306756, 'name': 'priority', 'context': {'priority': 16}}]}
{'id': 3382553738215424, 'events': [{'timestamp': 1728526317.5325196, 'name': 'annotations', 'context': {'annotations': None}}]}
{'id': 3382553738215424, 'events': [{'timestamp': 1728526317.5327518, 'name': 'alloc'}], 'R': {'version': 1, 'execution': {'R_lite': [{'rank': '3', 'children': {'core': '7'}}], 'nodelist': ['08c63b4a360d'], 'starttime': 1728526317, 'expiration': 4881924701}}}
{'id': 3382553738215424, 'events': [{'timestamp': 1728526317.535861, 'name': 'start'}]}
{'id': 3382554140868608, 'events': [{'timestamp': 1728526317.5325792, 'name': 'submit', 'context': {'userid': 1000, 'urgency': 16, 'flags': 0, 'version': 1}}], 'jobspec': {'resources': [{'type': 'node', 'count': 1, 'with': [{'type': 'slot', 'count': 1, 'with': [{'type': 'core', 'count': 1}], 'label': 'task'}]}], 'tasks': [{'command': ['echo', 'hello', 'world'], 'slot': 'task', 'count': {'per_slot': 1}}], 'attributes': {'system': {'duration': 0.0}, 'user': {'group': 'echo'}}, 'version': 1}}
{'id': 3382553738215424, 'events': [{'timestamp': 1728526317.5503535, 'name': 'finish', 'context': {'status': 0}}]}
{'id': 3382553738215424, 'events': [{'timestamp': 1728526317.5511098, 'name': 'release', 'context': {'ranks': 'all', 'final': True}}]}
{'id': 3382553738215424, 'events': [{'timestamp': 1728526317.5512474, 'name': 'free'}]}
{'id': 3382553738215424, 'events': [{'timestamp': 1728526317.5513113, 'name': 'clean'}]}
{'id': 3382554140868608, 'events': [{'timestamp': 1728526317.5437162, 'name': 'validate'}]}
{'id': 3382554140868608, 'events': [{'timestamp': 1728526317.5546155, 'name': 'depend'}]}
{'id': 3382554140868608, 'events': [{'timestamp': 1728526317.554737, 'name': 'priority', 'context': {'priority': 16}}]}
{'id': 3382554140868608, 'events': [{'timestamp': 1728526317.5562613, 'name': 'annotations', 'context': {'annotations': None}}]}
{'id': 3382554140868608, 'events': [{'timestamp': 1728526317.55639, 'name': 'alloc'}], 'R': {'version': 1, 'execution': {'R_lite': [{'rank': '3', 'children': {'core': '7'}}], 'nodelist': ['08c63b4a360d'], 'starttime': 1728526317, 'expiration': 4881924701}}}
{'id': 3382554140868608, 'events': [{'timestamp': 1728526317.5582461, 'name': 'start'}]}
{'id': 3382554543521792, 'events': [{'timestamp': 1728526317.556594, 'name': 'submit', 'context': {'userid': 1000, 'urgency': 16, 'flags': 0, 'version': 1}}], 'jobspec': {'resources': [{'type': 'node', 'count': 1, 'with': [{'type': 'slot', 'count': 1, 'with': [{'type': 'core', 'count': 1}], 'label': 'task'}]}], 'tasks': [{'command': ['echo', 'hello', 'world'], 'slot': 'task', 'count': {'per_slot': 1}}], 'attributes': {'system': {'duration': 0.0}, 'user': {'group': 'echo'}}, 'version': 1}}
{'id': 3382554140868608, 'events': [{'timestamp': 1728526317.5718262, 'name': 'finish', 'context': {'status': 0}}]}
🌊 Streaming ML Model Summary:
   name      : sleep-duration
   variance  : 3.2188056025020786e-07
   mean      : 10.015278863906861
   iqr       : 0.0005064010620117188
   max       : 10.016116380691528
   min       : 10.014636278152466
   mad       : 0.0
🌊 Streaming ML Model Summary:
   name      : echo-duration
   variance  : 1.5480913221143136e-06
   mean      : 0.01375099817911784
   iqr       : 0.0010814874840791907
   max       : 0.017398595809936523
   min       : 0.012215614318847656
   mad       : 0.000602859479409677
{'id': 3382554140868608, 'events': [{'timestamp': 1728526317.5724711, 'name': 'release', 'context': {'ranks': 'all', 'final': True}}]}
{'id': 3382554140868608, 'events': [{'timestamp': 1728526317.5725935, 'name': 'free'}]}
{'id': 3382554140868608, 'events': [{'timestamp': 1728526317.57265, 'name': 'clean'}]}
{'id': 3382554543521792, 'events': [{'timestamp': 1728526317.567865, 'name': 'validate'}]}
{'id': 3382554543521792, 'events': [{'timestamp': 1728526317.579112, 'name': 'depend'}]}
{'id': 3382554543521792, 'events': [{'timestamp': 1728526317.5793118, 'name': 'priority', 'context': {'priority': 16}}]}
{'id': 3382554543521792, 'events': [{'timestamp': 1728526317.5808704, 'name': 'annotations', 'context': {'annotations': None}}]}
{'id': 3382554543521792, 'events': [{'timestamp': 1728526317.5810637, 'name': 'alloc'}], 'R': {'version': 1, 'execution': {'R_lite': [{'rank': '3', 'children': {'core': '7'}}], 'nodelist': ['08c63b4a360d'], 'starttime': 1728526317, 'expiration': 4881924701}}}
{'id': 3382554543521792, 'events': [{'timestamp': 1728526317.5841587, 'name': 'start'}]}
{'id': 3382554946174976, 'events': [{'timestamp': 1728526317.5808675, 'name': 'submit', 'context': {'userid': 1000, 'urgency': 16, 'flags': 0, 'version': 1}}], 'jobspec': {'resources': [{'type': 'node', 'count': 1, 'with': [{'type': 'slot', 'count': 1, 'with': [{'type': 'core', 'count': 1}], 'label': 'task'}]}], 'tasks': [{'command': ['echo', 'hello', 'world'], 'slot': 'task', 'count': {'per_slot': 1}}], 'attributes': {'system': {'duration': 0.0}, 'user': {'group': 'echo'}}, 'version': 1}}
{'id': 3382554543521792, 'events': [{'timestamp': 1728526317.59621, 'name': 'finish', 'context': {'status': 0}}]}
{'id': 3382554543521792, 'events': [{'timestamp': 1728526317.5968475, 'name': 'release', 'context': {'ranks': 'all', 'final': True}}]}
{'id': 3382554543521792, 'events': [{'timestamp': 1728526317.596943, 'name': 'free'}]}
{'id': 3382554543521792, 'events': [{'timestamp': 1728526317.5970035, 'name': 'clean'}]}
{'id': 3382554946174976, 'events': [{'timestamp': 1728526317.5919206, 'name': 'validate'}]}
{'id': 3382554946174976, 'events': [{'timestamp': 1728526317.6031823, 'name': 'depend'}]}
{'id': 3382554946174976, 'events': [{'timestamp': 1728526317.6033008, 'name': 'priority', 'context': {'priority': 16}}]}
{'id': 3382554946174976, 'events': [{'timestamp': 1728526317.6053457, 'name': 'annotations', 'context': {'annotations': None}}]}
{'id': 3382554946174976, 'events': [{'timestamp': 1728526317.605482, 'name': 'alloc'}], 'R': {'version': 1, 'execution': {'R_lite': [{'rank': '3', 'children': {'core': '7'}}], 'nodelist': ['08c63b4a360d'], 'starttime': 1728526317, 'expiration': 4881924701}}}
{'id': 3382554946174976, 'events': [{'timestamp': 1728526317.6070838, 'name': 'start'}]}
{'id': 3382555365605376, 'events': [{'timestamp': 1728526317.6054714, 'name': 'submit', 'context': {'userid': 1000, 'urgency': 16, 'flags': 0, 'version': 1}}], 'jobspec': {'resources': [{'type': 'node', 'count': 1, 'with': [{'type': 'slot', 'count': 1, 'with': [{'type': 'core', 'count': 1}], 'label': 'task'}]}], 'tasks': [{'command': ['echo', 'hello', 'world'], 'slot': 'task', 'count': {'per_slot': 1}}], 'attributes': {'system': {'duration': 0.0}, 'user': {'group': 'echo'}}, 'version': 1}}
{'id': 3382554946174976, 'events': [{'timestamp': 1728526317.6195636, 'name': 'finish', 'context': {'status': 0}}]}
{'id': 3382554946174976, 'events': [{'timestamp': 1728526317.6204507, 'name': 'release', 'context': {'ranks': 'all', 'final': True}}]}
{'id': 3382554946174976, 'events': [{'timestamp': 1728526317.6206203, 'name': 'free'}]}
{'id': 3382554946174976, 'events': [{'timestamp': 1728526317.6207159, 'name': 'clean'}]}
{'id': 3382555365605376, 'events': [{'timestamp': 1728526317.6167521, 'name': 'validate'}]}
{'id': 3382555365605376, 'events': [{'timestamp': 1728526317.6280649, 'name': 'depend'}]}
{'id': 3382555365605376, 'events': [{'timestamp': 1728526317.6281362, 'name': 'priority', 'context': {'priority': 16}}]}
{'id': 3382555365605376, 'events': [{'timestamp': 1728526317.6296341, 'name': 'annotations', 'context': {'annotations': None}}]}
{'id': 3382555365605376, 'events': [{'timestamp': 1728526317.629764, 'name': 'alloc'}], 'R': {'version': 1, 'execution': {'R_lite': [{'rank': '3', 'children': {'core': '7'}}], 'nodelist': ['08c63b4a360d'], 'starttime': 1728526317, 'expiration': 4881924701}}}
{'id': 3382555365605376, 'events': [{'timestamp': 1728526317.6315897, 'name': 'start'}]}
{'id': 3382555768258560, 'events': [{'timestamp': 1728526317.6297207, 'name': 'submit', 'context': {'userid': 1000, 'urgency': 16, 'flags': 0, 'version': 1}}], 'jobspec': {'resources': [{'type': 'node', 'count': 1, 'with': [{'type': 'slot', 'count': 1, 'with': [{'type': 'core', 'count': 1}], 'label': 'task'}]}], 'tasks': [{'command': ['echo', 'hello', 'world'], 'slot': 'task', 'count': {'per_slot': 1}}], 'attributes': {'system': {'duration': 0.0}, 'user': {'group': 'echo'}}, 'version': 1}}
{'id': 3382555365605376, 'events': [{'timestamp': 1728526317.6452532, 'name': 'finish', 'context': {'status': 0}}]}
{'id': 3382555365605376, 'events': [{'timestamp': 1728526317.645931, 'name': 'release', 'context': {'ranks': 'all', 'final': True}}]}
{'id': 3382555365605376, 'events': [{'timestamp': 1728526317.6460829, 'name': 'free'}]}
{'id': 3382555365605376, 'events': [{'timestamp': 1728526317.646146, 'name': 'clean'}]}
{'id': 3382555768258560, 'events': [{'timestamp': 1728526317.641006, 'name': 'validate'}]}
{'id': 3382555768258560, 'events': [{'timestamp': 1728526317.6521618, 'name': 'depend'}]}
{'id': 3382555768258560, 'events': [{'timestamp': 1728526317.6522305, 'name': 'priority', 'context': {'priority': 16}}]}
{'id': 3382555768258560, 'events': [{'timestamp': 1728526317.6543744, 'name': 'annotations', 'context': {'annotations': None}}]}
{'id': 3382555768258560, 'events': [{'timestamp': 1728526317.654491, 'name': 'alloc'}], 'R': {'version': 1, 'execution': {'R_lite': [{'rank': '3', 'children': {'core': '7'}}], 'nodelist': ['08c63b4a360d'], 'starttime': 1728526317, 'expiration': 4881924701}}}
{'id': 3382555768258560, 'events': [{'timestamp': 1728526317.6569462, 'name': 'start'}]}
{'id': 3382556187688960, 'events': [{'timestamp': 1728526317.6541598, 'name': 'submit', 'context': {'userid': 1000, 'urgency': 16, 'flags': 0, 'version': 1}}], 'jobspec': {'resources': [{'type': 'node', 'count': 1, 'with': [{'type': 'slot', 'count': 1, 'with': [{'type': 'core', 'count': 1}], 'label': 'task'}]}], 'tasks': [{'command': ['echo', 'hello', 'world'], 'slot': 'task', 'count': {'per_slot': 1}}], 'attributes': {'system': {'duration': 0.0}, 'user': {'group': 'echo'}}, 'version': 1}}
{'id': 3382555768258560, 'events': [{'timestamp': 1728526317.669901, 'name': 'finish', 'context': {'status': 0}}]}
{'id': 3382555768258560, 'events': [{'timestamp': 1728526317.6707256, 'name': 'release', 'context': {'ranks': 'all', 'final': True}}]}
{'id': 3382555768258560, 'events': [{'timestamp': 1728526317.6709268, 'name': 'free'}]}
{'id': 3382555768258560, 'events': [{'timestamp': 1728526317.6710675, 'name': 'clean'}]}
{'id': 3382556187688960, 'events': [{'timestamp': 1728526317.6663375, 'name': 'validate'}]}
{'id': 3382556187688960, 'events': [{'timestamp': 1728526317.6767154, 'name': 'depend'}]}
{'id': 3382556187688960, 'events': [{'timestamp': 1728526317.6769104, 'name': 'priority', 'context': {'priority': 16}}]}
{'id': 3382556187688960, 'events': [{'timestamp': 1728526317.6791162, 'name': 'annotations', 'context': {'annotations': None}}]}
{'id': 3382556187688960, 'events': [{'timestamp': 1728526317.6792202, 'name': 'alloc'}], 'R': {'version': 1, 'execution': {'R_lite': [{'rank': '3', 'children': {'core': '7'}}], 'nodelist': ['08c63b4a360d'], 'starttime': 1728526317, 'expiration': 4881924701}}}
{'id': 3382556187688960, 'events': [{'timestamp': 1728526317.6810815, 'name': 'start'}]}
{'id': 3382556187688960, 'events': [{'timestamp': 1728526317.6957073, 'name': 'finish', 'context': {'status': 0}}]}
{'id': 3382556187688960, 'events': [{'timestamp': 1728526317.6963577, 'name': 'release', 'context': {'ranks': 'all', 'final': True}}]}
{'id': 3382556187688960, 'events': [{'timestamp': 1728526317.6964583, 'name': 'free'}]}
{'id': 3382556187688960, 'events': [{'timestamp': 1728526317.6965184, 'name': 'clean'}]}
```

</details>

It's a little verbose because I'm still debugging a lot. We can likely stream this down a bit!

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
