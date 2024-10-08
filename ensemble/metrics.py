import datetime


class Metrics:
    """
    Global metrics for the server
    """

    def __init__(self):
        self.start_time = datetime.datetime.now(datetime.timezone.utc)
        self.last_updated = self.start_time

    def tick(self):
        """
        Tick updates the last updated time
        """
        self.last_updated = datetime.datetime.now(datetime.timezone.utc)

    @property
    def elapsed(self):
        """
        Calculate the elapsed time in seconds
        """
        return (self.last_updated - self.start_time).seconds

    def to_dict(self):
        """
        Return times as json
        """
        return {
            "start_time": str(self.start_time),
            "last_updated": str(self.last_updated),
            "elapsed": str(self.elapsed),
        }
