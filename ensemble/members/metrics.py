from river import stats

model_inits = {
    "variance": stats.Var,
    "mean": stats.Mean,
    "iqr": stats.IQR,
    "max": stats.Max,
    "min": stats.Min,
    "mad": stats.MAD,
}


class QueueMetrics:
    """
    QueueMetrics store high level metrics
    about groups of jobs that finish or are in the
    queue. We use river.xyx stats functions:

    https://riverml.xyz/latest/api/stats/Mean
    """

    def __init__(self):
        self.models = {name: {} for name, _ in model_inits.items()}

        # Counters are separate
        self.models["count"] = {}

        # Cache for all group model keys
        self.keys = set()

    def summarize_all(self):
        """
        Summarize all models
        """
        for key in self.keys:
            self.summary(key)

    def summary(self, key):
        """
        Summarize currently known models under a key
        """
        print("🌊 Streaming ML Model Summary:")
        print(f"   name      : {key}")
        for model_name in model_inits:
            models = self.models[model_name]
            if key not in models:
                continue
            model = models[key]
            print(f"   {model_name.ljust(10)}: {model.get()}")

    def increment(self, group, key):
        """
        Increment the count of a metric.

        group: should refer to the job group
        key: should be the thing to increment (e.g., finished)
        """
        if group not in self.models["count"]:
            self.models["count"][group] = {}
        if key not in self.models["count"][group]:
            self.models["count"][group][key] = stats.Count()
        self.models["count"][group][key].update()

    def record_datum(self, key, value, model_name=None):
        """
        Record a datum for one or more models.

        If model_name is not set, add to add models.
        """
        self.keys.add(key)

        # This should be all models except for counts
        model_names = list(model_inits)
        if model_name is not None:
            model_names = [model_name]

        for model_name in model_names:
            if key not in self.models[model_name]:
                self.models[model_name][key] = model_inits[model_name]()
            self.models[model_name][key].update(value)
