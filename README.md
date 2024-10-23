# ensemble

> create state machines to orchestrate units of work

![PyPI - Version](https://img.shields.io/pypi/v/ensemble-python)

An HPC ensemble is an orchestration of jobs that can ideally be controlled by an algorithm. Ensemble (in python) is a project that provides a state machine to do exactly that. As a user, you specify one or more job groups, and then rules (triggers and actions) for how to act on different events. These rules, likely customized for a workflow or application, are what encompass your algorithm. This means that we define:

- A number of ensemble members (typically workload managers, queues, or job abstractions) that can deliver events
- Groups of jobs (converted into a job specification for the queue to consume)
- Rules for when to submit or otherwise interact with jobs (at onset, at periods during running, etc.)
- Rules for when to stop, cancel, or terminate
- Rules for when to change the environment (cluster) like growing or shrinking, if supported
- A set of online (streaming) ML metrics (e.g., mean, median or MAD, IRQ, min/max, etc) that are recorded for each job group and state (finished, failed, succeeded, etc.)

At a high level, we are reacting to events with rules for transitioning to new states. This even means we can make infinite loops (I accidentally already did). There can be an executor or queue interface that can support any kind of workload manager queue that can return the expected types.

🚧 Under Construction! 🚧

## Design

This design will be translated into more consolidated design documentation. You can see how it works in Kubernetes via the [Ensemble Operator here](https://converged-computing.org/ensemble-operator/getting_started/design.html). For now I'm putting design notes and features supported here.

### Concepts

- **Executor** provides a queue backend that should handle sending events. While a poll oriented design could work, it's not ideal. In the context of the ensemble, the queue executor is referred to as a **member**.
- **Ensemble Service**: provides grpc endpoints for one or more ensemble members to communicate with. This is an explicit design decision that, for example, would allow deploying one service that is orchestrating multiple things at once.
- **Rules**: A rule is composed of a trigger and action to take, and this is what drives the ensemble, more akin to a state machine than a traditional workflow DAG because the structure can be unknown at the start. For example, you might say "on the start of the ensemble, submit these jobs with label X."
- **Triggers**: A trigger is part of a rule (described above) and in the configuration file, and can be read as "when this trigger happens, do this action."
- **Action**: An actual is an operation that is the result of hitting a trigger condition. One type of action is performed by the queue, and are known to it. For example, queue actions include submit, scale-up, scale-down, or terminate. Actions are typically called by triggers under rules. Actions can be customized, and these are called custom actions.
- **Plugins**: A plugin is a collection of custom actions that are typically associated with a particular application. For example, a plugin for LAMMPS might know how to check LAMMPS output and act on a specific parsing of a result. Plugins are used equivalently to custom functions, and can accept arguments.
- **Metrics** are summary metrics collected for groups of jobs, for customized algorithms. To support this, we use online (or streaming) ML algorithms for things like mean, IQR, etc. While there could be a named entity called an algorithm, since it's just a set of rules (triggers and actions) that means we don't need to explicitly define them (yet). I can see at some point creating "packaged" rule sets that are called that.


#### Logging

By default, we have a pretty printed set of the "main" events (triggers and submissions). However, to see ALL events from Flux (good for debugging) you can turn them on:

```yaml
logging:
  debug: true
```

To set the event heartbeat to fire at some increment in seconds, set it:

```yaml
logging:
  debug: true
  heartbeat: 3
```

Note that by default it is turned off (set to 0 seconds) unless you include a grow or shrink action. In that case, it turns on and defaults to 60, unless you've specified another interval. If you have grow/shrink and explicitly turn it off, it will still default to 60 seconds, because grow/shrink won't work as expected without the heartbeat.

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

Note that yes, this means "submit" is both an action and an event. For each action, you should minimally define the "name" and a "label" that typically corresponds to a job group. You can also optionally define "repetitions," which are the number of times the action should be run before expiring. If you want a backoff period between repetitions, set "backoff" to a non zero value.
By default, when no repetitions or backoff are set, the action is assumed to have a repetition of 1. It will be run once.

##### Actions

The design of a rule is to have an action, and the action is something your ensemble can be tasked to do when an event is triggered. Right now we support the following:

**Flux and MiniCluster**

- *submit*: submit a job
- *terminate*: terminate the member. This is usually what you want to call to have the entire thing exit on 0
- *custom*: run a custom function that will receive known kwargs, and then should return an action (read more below)

**MiniCluster Only**

- *grow*: grow (or request) the cluster to scale up
- *shrink*: shrink (or request) the cluster to scale down

For the scale operations, since this brings in the issue of resource contention between different ensembles, this will typically fall under the responsibility of the GRPC service that can see multiple ensembles and implement something like fair share. I have not tested this use case yet. The default for each of the above (and all actions) are to be run just once, so if you want to allow grow multiple times, you will need to set `replications`. To space them out over heartbeats (checks) you can set a `backoff` period.

When it is time to run several ensembles at once, I am intending on putting this logic (or fair share algorithm) in the grpc service. I have not yet because this is another level of complexity that is not warranted yet. 

###### Heartbeat

Also note that since scale operation triggers might not be linked to job events (e.g., if we want to trigger when a job group has been in the queue for too long) we added support for a heartbeat. The heartbeat isn't a trigger in and of itself, but when it runs, it will run through rules that are relevant to queue metrics. 

##### Actions

Custom actions are also supported, where you define a custom function that in and of itself returns an action! Here is an example to extend the above. Let's say we want to run the group "echo" again, we might do the following:

```python
   def echo_again(**kwargs):
      """
      For a custom function, you can assume the following in kwargs,
        and note that this set of metadata can vary based on the ensemble type.
      metrics: the full QueueMetrics object to use as needed
      event: the full event that triggered the custom action
      rule: the original rule that triggered the action
      action: your custom action
      handle: the active flux handle (Flux ensemble specific!)

      You should (must) return an action in your response, or None to take
      no action. E.g.,: return Action({"name": "submit", "label": "echo"})
      """
      return Action({"name": "submit", "label": "echo"})
```

Note that in the above, we get access to the following via kwargs:

- metrics: the full QueueMetrics object to use as needed
- event: the full event that triggered the custom action
- rule: the original rule that triggered the action
- action: your custom action
- handle: the active flux handle (Flux ensemble specific!)

- A custom rule can have a trigger, and then return another rule. This means that:
 - return "None" to do nothing
 - return an action to follow up your custom function

You can do whatever you like in custom rules! Try interacting with other APIs on the host that are related to resources of interest.

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

These metrics are important because "metric" is a trigger, and then you can define a specific metric and threshold and action. E.g., "When the mean pending time of job group N is greater than 5, do this action."

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

# Here is how to add on the fly debug (logging->debug true)
ensemble run --debug examples/hello-world.yaml

# This example shows using repetitions and backoff
ensemble run examples/backoff-example.yaml

# This shows a custom action
ensemble run examples/custom-action-example.yaml

# This shows termination, which is necessary for when you want an exit
ensemble run examples/terminate-example.yaml

# Run a heartbeat every 3 seconds.
# This will trigger a check to see if actions need to be performed
ensemble run examples/heartbeat-example.yaml

# Grow/shrink requires a minicluster (flux doesn't support it) but we can mock it here
# Note that a --name with <namespace>/<name> is required
ensemble run --name default/ensemble --executor minicluster examples/grow-shrink-example.yaml
```

Right now, this will run any rules with "start" triggers, which for this hello world example includes a few hello world jobs! You'll then be able to watch and see flux events coming in!
Here is the full run - we run a bunch of sleep jobs (10) and when we hit a count of 5, we launch a bunch of echo jobs.

```console
$ ensemble run examples/hello-world.yaml
 => trigger start
   submit sleep (name:sleep),(command:sleep 10),(count:5),(nodes:1)
 => trigger count.sleep.success
   submit echo (name:echo),(command:echo hello world),(count:5),(nodes:1)
```

The above output is colored! Note that in any ensemble file, you can turn on debug mode to see more verbose output (events, etc.)

<details>

<summary>Example Ensemble Run</summary>

This run shows having verbose enabled.

```console
$ ensemble run examples/hello-world.yaml
 => trigger start
   submit sleep (name:sleep),(command:sleep 10),(count:5),(nodes:1)
{'id': 513684799488, 'events': [{'timestamp': 1729181750.7627614, 'name': 'submit', 'context': {'userid': 1000, 'urgency': 16, 'flags': 0, 'version': 1}}, {'timestamp': 1729181750.7731683, 'name': 'validate'}, {'timestamp': 1729181750.7839293, 'name': 'depend'}, {'timestamp': 1729181750.7839663, 'name': 'priority', 'context': {'priority': 16}}, {'timestamp': 1729181750.785146, 'name': 'alloc'}, {'timestamp': 1729181750.7863054, 'name': 'start'}], 'jobspec': {'resources': [{'type': 'node', 'count': 1, 'with': [{'type': 'slot', 'count': 1, 'with': [{'type': 'core', 'count': 1}], 'label': 'task'}]}], 'tasks': [{'command': ['sleep', '10'], 'slot': 'task', 'count': {'per_slot': 1}}], 'attributes': {'system': {'duration': 0.0}, 'user': {'group': 'sleep'}}, 'version': 1}, 'R': {'version': 1, 'execution': {'R_lite': [{'rank': '1', 'children': {'core': '6'}}], 'nodelist': ['08c63b4a360d'], 'starttime': 1729181750, 'expiration': 4882781720}}}
{'id': 512543948800, 'events': [{'timestamp': 1729181750.6949837, 'name': 'submit', 'context': {'userid': 1000, 'urgency': 16, 'flags': 0, 'version': 1}}, {'timestamp': 1729181750.7062836, 'name': 'validate'}, {'timestamp': 1729181750.7169266, 'name': 'depend'}, {'timestamp': 1729181750.7169478, 'name': 'priority', 'context': {'priority': 16}}, {'timestamp': 1729181750.717982, 'name': 'alloc'}, {'timestamp': 1729181750.7212884, 'name': 'start'}], 'jobspec': {'resources': [{'type': 'node', 'count': 1, 'with': [{'type': 'slot', 'count': 1, 'with': [{'type': 'core', 'count': 1}], 'label': 'task'}]}], 'tasks': [{'command': ['sleep', '10'], 'slot': 'task', 'count': {'per_slot': 1}}], 'attributes': {'system': {'duration': 0.0}, 'user': {'group': 'sleep'}}, 'version': 1}, 'R': {'version': 1, 'execution': {'R_lite': [{'rank': '2', 'children': {'core': '7'}}], 'nodelist': ['08c63b4a360d'], 'starttime': 1729181750, 'expiration': 4882781720}}}
{'id': 514053898240, 'events': [{'timestamp': 1729181750.7850096, 'name': 'submit', 'context': {'userid': 1000, 'urgency': 16, 'flags': 0, 'version': 1}}, {'timestamp': 1729181750.7954807, 'name': 'validate'}, {'timestamp': 1729181750.8061984, 'name': 'depend'}, {'timestamp': 1729181750.806234, 'name': 'priority', 'context': {'priority': 16}}], 'jobspec': {'resources': [{'type': 'node', 'count': 1, 'with': [{'type': 'slot', 'count': 1, 'with': [{'type': 'core', 'count': 1}], 'label': 'task'}]}], 'tasks': [{'command': ['sleep', '10'], 'slot': 'task', 'count': {'per_slot': 1}}], 'attributes': {'system': {'duration': 0.0}, 'user': {'group': 'sleep'}}, 'version': 1}}
{'id': 512929824768, 'events': [{'timestamp': 1729181750.7181482, 'name': 'submit', 'context': {'userid': 1000, 'urgency': 16, 'flags': 0, 'version': 1}}, {'timestamp': 1729181750.7286258, 'name': 'validate'}, {'timestamp': 1729181750.7391565, 'name': 'depend'}, {'timestamp': 1729181750.7391846, 'name': 'priority', 'context': {'priority': 16}}, {'timestamp': 1729181750.7405195, 'name': 'alloc'}, {'timestamp': 1729181750.7415988, 'name': 'start'}], 'jobspec': {'resources': [{'type': 'node', 'count': 1, 'with': [{'type': 'slot', 'count': 1, 'with': [{'type': 'core', 'count': 1}], 'label': 'task'}]}], 'tasks': [{'command': ['sleep', '10'], 'slot': 'task', 'count': {'per_slot': 1}}], 'attributes': {'system': {'duration': 0.0}, 'user': {'group': 'sleep'}}, 'version': 1}, 'R': {'version': 1, 'execution': {'R_lite': [{'rank': '2', 'children': {'core': '6'}}], 'nodelist': ['08c63b4a360d'], 'starttime': 1729181750, 'expiration': 4882781720}}}
{'id': 513315700736, 'events': [{'timestamp': 1729181750.7404878, 'name': 'submit', 'context': {'userid': 1000, 'urgency': 16, 'flags': 0, 'version': 1}}, {'timestamp': 1729181750.7509809, 'name': 'validate'}, {'timestamp': 1729181750.7615387, 'name': 'depend'}, {'timestamp': 1729181750.761586, 'name': 'priority', 'context': {'priority': 16}}, {'timestamp': 1729181750.762535, 'name': 'alloc'}, {'timestamp': 1729181750.7638192, 'name': 'start'}], 'jobspec': {'resources': [{'type': 'node', 'count': 1, 'with': [{'type': 'slot', 'count': 1, 'with': [{'type': 'core', 'count': 1}], 'label': 'task'}]}], 'tasks': [{'command': ['sleep', '10'], 'slot': 'task', 'count': {'per_slot': 1}}], 'attributes': {'system': {'duration': 0.0}, 'user': {'group': 'sleep'}}, 'version': 1}, 'R': {'version': 1, 'execution': {'R_lite': [{'rank': '1', 'children': {'core': '7'}}], 'nodelist': ['08c63b4a360d'], 'starttime': 1729181750, 'expiration': 4882781720}}}
{'id': -1, 'events': []}
Sentinel is seen, starting event monitoring.
{'id': 514053898240, 'events': [{'timestamp': 1729181750.8073554, 'name': 'annotations', 'context': {'annotations': None}}]}
{'id': 514053898240, 'events': [{'timestamp': 1729181750.8073688, 'name': 'alloc'}], 'R': {'version': 1, 'execution': {'R_lite': [{'rank': '0', 'children': {'core': '7'}}], 'nodelist': ['08c63b4a360d'], 'starttime': 1729181750, 'expiration': 4882781720}}}
{'id': 514053898240, 'events': [{'timestamp': 1729181750.8085647, 'name': 'start'}]}
{'id': 512543948800, 'events': [{'timestamp': 1729181760.7343254, 'name': 'finish', 'context': {'status': 0}}]}
{'id': 512543948800, 'events': [{'timestamp': 1729181760.735187, 'name': 'release', 'context': {'ranks': 'all', 'final': True}}]}
{'id': 512543948800, 'events': [{'timestamp': 1729181760.7352166, 'name': 'free'}]}
{'id': 512543948800, 'events': [{'timestamp': 1729181760.735229, 'name': 'clean'}]}
{'id': 512929824768, 'events': [{'timestamp': 1729181760.7541575, 'name': 'finish', 'context': {'status': 0}}]}
{'id': 512929824768, 'events': [{'timestamp': 1729181760.755071, 'name': 'release', 'context': {'ranks': 'all', 'final': True}}]}
{'id': 512929824768, 'events': [{'timestamp': 1729181760.7551124, 'name': 'free'}]}
{'id': 512929824768, 'events': [{'timestamp': 1729181760.755127, 'name': 'clean'}]}
{'id': 513315700736, 'events': [{'timestamp': 1729181760.7783182, 'name': 'finish', 'context': {'status': 0}}]}
{'variance': {'sleep-pending': Var: 0.000002, 'sleep-duration': Var: 0.000001}, 'mean': {'sleep-pending': Mean: 0.024037, 'sleep-duration': Mean: 10.013365}, 'iqr': {'sleep-pending': IQR: 0.000104, 'sleep-duration': IQR: 0.00194}, 'max': {'sleep-pending': Max: 0.026305, 'sleep-duration': Max: 10.014499}, 'min': {'sleep-pending': Min: 0.023331, 'sleep-duration': Min: 10.012559}, 'mad': {'sleep-pending': MAD: 0.000011, 'sleep-duration': MAD: 0.000478}, 'count': {'sleep': {'finished': Count: 3., 'success': Count: 3.}}}
 => trigger count.sleep.success
   submit echo (name:echo),(command:echo hello world),(count:5),(nodes:1)
{'id': 513315700736, 'events': [{'timestamp': 1729181760.7791471, 'name': 'release', 'context': {'ranks': 'all', 'final': True}}]}
{'variance': {'sleep-pending': Var: 0.000002, 'sleep-duration': Var: 0.000001}, 'mean': {'sleep-pending': Mean: 0.024037, 'sleep-duration': Mean: 10.013365}, 'iqr': {'sleep-pending': IQR: 0.000104, 'sleep-duration': IQR: 0.00194}, 'max': {'sleep-pending': Max: 0.026305, 'sleep-duration': Max: 10.014499}, 'min': {'sleep-pending': Min: 0.023331, 'sleep-duration': Min: 10.012559}, 'mad': {'sleep-pending': MAD: 0.000011, 'sleep-duration': MAD: 0.000478}, 'count': {'sleep': {'finished': Count: 3., 'success': Count: 3.}}}
{'id': 513315700736, 'events': [{'timestamp': 1729181760.7791893, 'name': 'free'}]}
{'variance': {'sleep-pending': Var: 0.000002, 'sleep-duration': Var: 0.000001}, 'mean': {'sleep-pending': Mean: 0.024037, 'sleep-duration': Mean: 10.013365}, 'iqr': {'sleep-pending': IQR: 0.000104, 'sleep-duration': IQR: 0.00194}, 'max': {'sleep-pending': Max: 0.026305, 'sleep-duration': Max: 10.014499}, 'min': {'sleep-pending': Min: 0.023331, 'sleep-duration': Min: 10.012559}, 'mad': {'sleep-pending': MAD: 0.000011, 'sleep-duration': MAD: 0.000478}, 'count': {'sleep': {'finished': Count: 3., 'success': Count: 3.}}}
{'id': 513315700736, 'events': [{'timestamp': 1729181760.7792032, 'name': 'clean'}]}
{'variance': {'sleep-pending': Var: 0.000002, 'sleep-duration': Var: 0.000001}, 'mean': {'sleep-pending': Mean: 0.024037, 'sleep-duration': Mean: 10.013365}, 'iqr': {'sleep-pending': IQR: 0.000104, 'sleep-duration': IQR: 0.00194}, 'max': {'sleep-pending': Max: 0.026305, 'sleep-duration': Max: 10.014499}, 'min': {'sleep-pending': Min: 0.023331, 'sleep-duration': Min: 10.012559}, 'mad': {'sleep-pending': MAD: 0.000011, 'sleep-duration': MAD: 0.000478}, 'count': {'sleep': {'finished': Count: 3., 'success': Count: 3.}}}
{'id': 513684799488, 'events': [{'timestamp': 1729181760.799435, 'name': 'finish', 'context': {'status': 0}}]}
{'id': 513684799488, 'events': [{'timestamp': 1729181760.8005102, 'name': 'release', 'context': {'ranks': 'all', 'final': True}}]}
{'id': 513684799488, 'events': [{'timestamp': 1729181760.800557, 'name': 'free'}]}
{'id': 513684799488, 'events': [{'timestamp': 1729181760.8005707, 'name': 'clean'}]}
{'id': 514053898240, 'events': [{'timestamp': 1729181760.8197052, 'name': 'finish', 'context': {'status': 0}}]}
{'id': 514053898240, 'events': [{'timestamp': 1729181760.8207376, 'name': 'release', 'context': {'ranks': 'all', 'final': True}}]}
{'id': 514053898240, 'events': [{'timestamp': 1729181760.8207989, 'name': 'free'}]}
{'id': 514053898240, 'events': [{'timestamp': 1729181760.8208258, 'name': 'clean'}]}
{'id': 683252121600, 'events': [{'timestamp': 1729181760.8696713, 'name': 'submit', 'context': {'userid': 1000, 'urgency': 16, 'flags': 0, 'version': 1}}], 'jobspec': {'resources': [{'type': 'node', 'count': 1, 'with': [{'type': 'slot', 'count': 1, 'with': [{'type': 'core', 'count': 1}], 'label': 'task'}]}], 'tasks': [{'command': ['echo', 'hello', 'world'], 'slot': 'task', 'count': {'per_slot': 1}}], 'attributes': {'system': {'duration': 0.0}, 'user': {'group': 'echo'}}, 'version': 1}}
{'id': 683252121600, 'events': [{'timestamp': 1729181760.8811576, 'name': 'validate'}]}
{'id': 683252121600, 'events': [{'timestamp': 1729181760.8918009, 'name': 'depend'}]}
{'id': 683252121600, 'events': [{'timestamp': 1729181760.8918545, 'name': 'priority', 'context': {'priority': 16}}]}
{'id': 683252121600, 'events': [{'timestamp': 1729181760.8930376, 'name': 'annotations', 'context': {'annotations': None}}]}
{'id': 683252121600, 'events': [{'timestamp': 1729181760.8930573, 'name': 'alloc'}], 'R': {'version': 1, 'execution': {'R_lite': [{'rank': '0', 'children': {'core': '7'}}], 'nodelist': ['08c63b4a360d'], 'starttime': 1729181760, 'expiration': 4882781720}}}
{'id': 683252121600, 'events': [{'timestamp': 1729181760.8941934, 'name': 'start'}]}
{'id': 683637997568, 'events': [{'timestamp': 1729181760.8929186, 'name': 'submit', 'context': {'userid': 1000, 'urgency': 16, 'flags': 0, 'version': 1}}], 'jobspec': {'resources': [{'type': 'node', 'count': 1, 'with': [{'type': 'slot', 'count': 1, 'with': [{'type': 'core', 'count': 1}], 'label': 'task'}]}], 'tasks': [{'command': ['echo', 'hello', 'world'], 'slot': 'task', 'count': {'per_slot': 1}}], 'attributes': {'system': {'duration': 0.0}, 'user': {'group': 'echo'}}, 'version': 1}}
{'id': 683252121600, 'events': [{'timestamp': 1729181760.9039655, 'name': 'finish', 'context': {'status': 0}}]}
{'id': 683252121600, 'events': [{'timestamp': 1729181760.9044635, 'name': 'release', 'context': {'ranks': 'all', 'final': True}}]}
{'id': 683252121600, 'events': [{'timestamp': 1729181760.9044845, 'name': 'free'}]}
{'id': 683252121600, 'events': [{'timestamp': 1729181760.9044933, 'name': 'clean'}]}
{'id': 683637997568, 'events': [{'timestamp': 1729181760.9033427, 'name': 'validate'}]}
{'id': 683637997568, 'events': [{'timestamp': 1729181760.9143605, 'name': 'depend'}]}
{'id': 683637997568, 'events': [{'timestamp': 1729181760.9143932, 'name': 'priority', 'context': {'priority': 16}}]}
{'id': 683637997568, 'events': [{'timestamp': 1729181760.9153101, 'name': 'annotations', 'context': {'annotations': None}}]}
{'id': 683637997568, 'events': [{'timestamp': 1729181760.9153209, 'name': 'alloc'}], 'R': {'version': 1, 'execution': {'R_lite': [{'rank': '0', 'children': {'core': '7'}}], 'nodelist': ['08c63b4a360d'], 'starttime': 1729181760, 'expiration': 4882781720}}}
{'id': 683637997568, 'events': [{'timestamp': 1729181760.916482, 'name': 'start'}]}
{'id': 684023873536, 'events': [{'timestamp': 1729181760.9156003, 'name': 'submit', 'context': {'userid': 1000, 'urgency': 16, 'flags': 0, 'version': 1}}], 'jobspec': {'resources': [{'type': 'node', 'count': 1, 'with': [{'type': 'slot', 'count': 1, 'with': [{'type': 'core', 'count': 1}], 'label': 'task'}]}], 'tasks': [{'command': ['echo', 'hello', 'world'], 'slot': 'task', 'count': {'per_slot': 1}}], 'attributes': {'system': {'duration': 0.0}, 'user': {'group': 'echo'}}, 'version': 1}}
{'id': 683637997568, 'events': [{'timestamp': 1729181760.9266214, 'name': 'finish', 'context': {'status': 0}}]}
{'id': 683637997568, 'events': [{'timestamp': 1729181760.9271212, 'name': 'release', 'context': {'ranks': 'all', 'final': True}}]}
{'id': 683637997568, 'events': [{'timestamp': 1729181760.927144, 'name': 'free'}]}
{'id': 683637997568, 'events': [{'timestamp': 1729181760.9271522, 'name': 'clean'}]}
{'id': 684023873536, 'events': [{'timestamp': 1729181760.92615, 'name': 'validate'}]}
{'id': 684023873536, 'events': [{'timestamp': 1729181760.9372776, 'name': 'depend'}]}
{'id': 684023873536, 'events': [{'timestamp': 1729181760.9373105, 'name': 'priority', 'context': {'priority': 16}}]}
{'id': 684023873536, 'events': [{'timestamp': 1729181760.9384887, 'name': 'annotations', 'context': {'annotations': None}}]}
{'id': 684023873536, 'events': [{'timestamp': 1729181760.9385107, 'name': 'alloc'}], 'R': {'version': 1, 'execution': {'R_lite': [{'rank': '0', 'children': {'core': '7'}}], 'nodelist': ['08c63b4a360d'], 'starttime': 1729181760, 'expiration': 4882781720}}}
{'id': 684023873536, 'events': [{'timestamp': 1729181760.939761, 'name': 'start'}]}
{'id': 684409749504, 'events': [{'timestamp': 1729181760.9384136, 'name': 'submit', 'context': {'userid': 1000, 'urgency': 16, 'flags': 0, 'version': 1}}], 'jobspec': {'resources': [{'type': 'node', 'count': 1, 'with': [{'type': 'slot', 'count': 1, 'with': [{'type': 'core', 'count': 1}], 'label': 'task'}]}], 'tasks': [{'command': ['echo', 'hello', 'world'], 'slot': 'task', 'count': {'per_slot': 1}}], 'attributes': {'system': {'duration': 0.0}, 'user': {'group': 'echo'}}, 'version': 1}}
{'id': 684023873536, 'events': [{'timestamp': 1729181760.9494925, 'name': 'finish', 'context': {'status': 0}}]}
{'id': 684023873536, 'events': [{'timestamp': 1729181760.9499779, 'name': 'release', 'context': {'ranks': 'all', 'final': True}}]}
{'id': 684023873536, 'events': [{'timestamp': 1729181760.9500043, 'name': 'free'}]}
{'id': 684023873536, 'events': [{'timestamp': 1729181760.9500136, 'name': 'clean'}]}
{'id': 684409749504, 'events': [{'timestamp': 1729181760.9491577, 'name': 'validate'}]}
{'id': 684409749504, 'events': [{'timestamp': 1729181760.9600794, 'name': 'depend'}]}
{'id': 684409749504, 'events': [{'timestamp': 1729181760.9601243, 'name': 'priority', 'context': {'priority': 16}}]}
{'id': 684409749504, 'events': [{'timestamp': 1729181760.9613469, 'name': 'annotations', 'context': {'annotations': None}}]}
{'id': 684409749504, 'events': [{'timestamp': 1729181760.961367, 'name': 'alloc'}], 'R': {'version': 1, 'execution': {'R_lite': [{'rank': '0', 'children': {'core': '7'}}], 'nodelist': ['08c63b4a360d'], 'starttime': 1729181760, 'expiration': 4882781720}}}
{'id': 684409749504, 'events': [{'timestamp': 1729181760.962481, 'name': 'start'}]}
{'id': 684795625472, 'events': [{'timestamp': 1729181760.9613535, 'name': 'submit', 'context': {'userid': 1000, 'urgency': 16, 'flags': 0, 'version': 1}}], 'jobspec': {'resources': [{'type': 'node', 'count': 1, 'with': [{'type': 'slot', 'count': 1, 'with': [{'type': 'core', 'count': 1}], 'label': 'task'}]}], 'tasks': [{'command': ['echo', 'hello', 'world'], 'slot': 'task', 'count': {'per_slot': 1}}], 'attributes': {'system': {'duration': 0.0}, 'user': {'group': 'echo'}}, 'version': 1}}
{'id': 684409749504, 'events': [{'timestamp': 1729181760.9736989, 'name': 'finish', 'context': {'status': 0}}]}
{'id': 684409749504, 'events': [{'timestamp': 1729181760.9745057, 'name': 'release', 'context': {'ranks': 'all', 'final': True}}]}
{'id': 684409749504, 'events': [{'timestamp': 1729181760.9745595, 'name': 'free'}]}
{'id': 684409749504, 'events': [{'timestamp': 1729181760.9745681, 'name': 'clean'}]}
{'id': 684795625472, 'events': [{'timestamp': 1729181760.9718993, 'name': 'validate'}]}
{'id': 684795625472, 'events': [{'timestamp': 1729181760.9837554, 'name': 'depend'}]}
{'id': 684795625472, 'events': [{'timestamp': 1729181760.983788, 'name': 'priority', 'context': {'priority': 16}}]}
{'id': 684795625472, 'events': [{'timestamp': 1729181760.9848664, 'name': 'annotations', 'context': {'annotations': None}}]}
{'id': 684795625472, 'events': [{'timestamp': 1729181760.984877, 'name': 'alloc'}], 'R': {'version': 1, 'execution': {'R_lite': [{'rank': '0', 'children': {'core': '7'}}], 'nodelist': ['08c63b4a360d'], 'starttime': 1729181760, 'expiration': 4882781720}}}
{'id': 684795625472, 'events': [{'timestamp': 1729181760.986103, 'name': 'start'}]}
{'id': 684795625472, 'events': [{'timestamp': 1729181760.9960618, 'name': 'finish', 'context': {'status': 0}}]}
🌊 Streaming ML Model Summary sleep-duration: (variance:1.459105192225026e-06),(mean:10.01287293434143),(iqr:0.0005707740783691406),(max:10.014498949050903),(min:10.011140584945679),(mad:0.0004782676696777344)
🌊 Streaming ML Model Summary echo-duration: (variance:3.7348486898736154e-07),(mean:0.01016392707824707),(iqr:0.0003674030303955078),(max:0.011217832565307617),(min:0.009731531143188477),(mad:0.0)
🌊 Streaming ML Model Summary echo-pending: (variance:2.0732844063786618e-07),(mean:0.02421259880065918),(iqr:0.0004546642303466797),(max:0.0247495174407959),(min:0.023563385009765625),(mad:9.322166442871094e-05)
🌊 Streaming ML Model Summary sleep-pending: (variance:1.614884990885912e-06),(mean:0.02403717041015625),(iqr:0.00010442733764648438),(max:0.02630472183227539),(min:0.023331403732299805),(mad:1.0967254638671875e-05)
{'id': 684795625472, 'events': [{'timestamp': 1729181760.9969702, 'name': 'release', 'context': {'ranks': 'all', 'final': True}}]}
{'id': 684795625472, 'events': [{'timestamp': 1729181760.9970036, 'name': 'free'}]}
{'id': 684795625472, 'events': [{'timestamp': 1729181760.997014, 'name': 'clean'}]}
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

### Next steps

- Move (this) verbose readme into proper docs
- A collection of custom functions (e.g., parse LAMMPS output and get this FOM and act on it) can be provided as custom plugins
- Interactions with other APIs or resources that expose a Python API are possible and can also be custom plugins.
- Real world use case is AMS - running either surrogate or multi-physics model. whenever runs the physics model, saves the input/output pairs and uses them to retrain. "Under what conditions would AMS need to start training." We would also want to look at cases with conditional logic.

## License

HPCIC DevTools is distributed under the terms of the MIT license.
All new contributions must be made under this license.

See [LICENSE](https://github.com/converged-computing/cloud-select/blob/main/LICENSE),
[COPYRIGHT](https://github.com/converged-computing/cloud-select/blob/main/COPYRIGHT), and
[NOTICE](https://github.com/converged-computing/cloud-select/blob/main/NOTICE) for details.

SPDX-License-Identifier: (MIT)

LLNL-CODE- 842614
