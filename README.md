# ensemble

![PyPI - Version](https://img.shields.io/pypi/v/ensemble-python)

An HPC ensemble is an orchestration of jobs that can ideally be controlled by an algorithm. Ensemble (in python) is a project to do exactly that. As a user, you specify the parameters for your job, and then an algorithm and options for it. But when you think about it, an algorithm *could* have a known name or label, but in its simplest form it is a set of rules (triggers and actions) that make up a state machine. In that light, ensemble python is a simple tool to create state machines to orchestrate units of work with workload managers. Specific sets of rules could be packaged up to be called an algorithm, and in fact that might be what we eventually call the yaml file that defines them. For now, we call them ensembles.

The library here listens for the heartbeat of your ensemble -- events that come directly from the queue or entity that is controlling the jobs.
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

The current triggers supported are [events for flux](https://flux-framework.readthedocs.io/projects/flux-rfc/en/latest/spec_21.html). In addition, we have added:

- metric: Triggered when a queue metric is updated

For example, the following snippet defines two rules. The first says "on the start of the ensemble, submit the job group labeled as lammps." And then when lammps has 3 successful runs, submit the job group amg (groups are not shown).

```yaml
rules:
  - trigger: start
    action:
      name: submit
      label: lammps

  - trigger: metric
    name: count.lammps.success
    when: 3
    action:
      name: submit
      label: amg
```

Note that yes, this means "submit" is both an action and an event.

##### Actions

The design of a rule is to have an action, and the action is something your ensemble can be tasked to do when an event is triggered. Right now we support the following:

- **submit**: submit a job
- **custom**: run a custom function that will receive known kwargs, and then should return an action (read more below)

We see "submit" as two examples in the above, which is a common thing you'd want to do! For each action, you should minimally define the "name" and a "label" that typically corresponds to a job group.
You can also optionally define "repetitions," which are the number of times the action should be run before expiring. If you want a backoff period between repetitions, set "backoff" to a non zero value.
By default, when no repetitions or backoff are set, the action is assumed to have a repetition of 1. It will be run once! Let's now look at a custom action. Here is what your function should look like in your `ensemble.yaml`


##### Actions


Custom actions are also supported, where you define a custom function that in and of itself returns an action! Here is an example to extend the above. Let's say we want to run

I'm also thinking about what a very custom rule looks like. We have classes for each of rule and action, so I think some function that can fold into that could work. This could also allow customizing triggers (e.g., custom triggers not known to the library that come in the same way).

- A custom rule can have a trigger, and then return another rule. This means that:
 - return "None" to do nothing
 - return an action to do the action immediately
 - return a rule to add to the set


#### Metrics

We use streaming ML "stats" for each job group, and then a subset of variables. Right now we support, for each job group:

- **duration** Each of variance, mean, iqr, max, min, and mad (mean absolute deviation) for the duration of the job
- **pending-time** Each of variance, mean, iqr, max, min, and mad (mean absolute deviation) for the time the job spent in the queue (pending state)

Here is an example that shows duration for a job group called "echo."

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


## Example

Let's do an example running in the Development container, where we have flux. You can do the following:

```bash
# Start a flux instance
flux start --test-size=4

# Install in development mode, and run "make" to rebuild proto if necessary
sudo pip install -e .

# Start the server (actually you don't need to do this, I'm not using it yet)
ensemble-server start

# Run the hello-world example ensemble! it will submit and monitor job events, etc
ensemble run examples/hello-world.yaml

# This example shows using repetitions and backoff
ensemble run examples/backoff-example.yaml
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

- We probably want some kind of cron or heartbeat functionality (does flux have a job like this?)
- I've added logging->debug that disables most of verbose event printing. What DO we want to print?
- We will want parameters, etc. to vary based on custom functions.
- Likely a custom function should be able to return None and then actions or other rules.
- Move verbose readme into proper docs
- Add metrics that can keep summary stats for job groups, and for the queue, and we should be able to act on them. Then add other action triggers and finish the simple hello world example.
- The metrics recording is a source of data for ML learning, need to figure out the right interface for that.
- Should we separate fails/successes or just record successes for now?
- What if we want to change the algorithm used for different parts of the run? Possible or too complex?
- Actions needed: stop, cancel, end
- Likely bug - when we have a huge backlog to parse and can't get all previous ids.

## License

HPCIC DevTools is distributed under the terms of the MIT license.
All new contributions must be made under this license.

See [LICENSE](https://github.com/converged-computing/cloud-select/blob/main/LICENSE),
[COPYRIGHT](https://github.com/converged-computing/cloud-select/blob/main/COPYRIGHT), and
[NOTICE](https://github.com/converged-computing/cloud-select/blob/main/NOTICE) for details.

SPDX-License-Identifier: (MIT)

LLNL-CODE- 842614
