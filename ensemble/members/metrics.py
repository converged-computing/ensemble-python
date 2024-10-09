from river import stats

model_inits = {
    "variance": stats.Var,
    "mean": stats.Mean,
    "iqr": stats.IQR,
    "max": stats.Max,
    "min": stats.Min,
    "mad": stats.MAD,
    "count": stats.Count,
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

    def summary(self, key):
        """
        Summarize currently known models under a key
        """
        print(f"🌊 Streaming ML Model Summary:")
        print(f"   name      : {key}")
        for model_name, models in self.models.items():
            if key not in models:
                continue
            model = models[key]
            print(f"   {model_name.ljust(10)}: {model.get()}")

    def record_datum(self, key, value, model_name=None):
        """
        Record a datum for one or more models.

        If model_name is not set, add to add models.
        """
        model_names = list(self.models)
        if model_name is not None:
            model_names = [model_name]

        for model_name in model_names:
            if key not in self.models[model_name]:
                self.models[model_name][key] = model_inits[model_name]()
            self.models[model_name][key].update(value)
