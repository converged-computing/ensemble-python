import signal
import threading


class GracefulExit(Exception):
    """
    Ensure if we press control+C, it doesn't throw up.
    """

    pass


class QueueHeartbeat(threading.Thread):
    """
    The Queue Heartbeat triggers at a user specified interval, with the
    intention to be able to run events that might not be linked to jobs.
    """

    def __init__(self, interval_seconds, callback, **kwargs):
        super().__init__()
        self.stop_event = threading.Event()
        self.interval_seconds = interval_seconds
        self.callback = callback
        self.kwargs = kwargs

    def run(self):
        """
        Run the heartbeat function, and exit gracefully
        """
        while not self.stop_event.wait(self.interval_seconds):
            try:
                self.callback(**self.kwargs)
            except (KeyboardInterrupt, GracefulExit):
                break

    def stop(self):
        """
        Explicit stop of the thread, like that will happen :)
        """
        self.stop_event.set()


def signal_handler(signum, frame):
    """
    The signal handler follows an expected pattern, but
    just calls a graceful exit
    """
    raise GracefulExit()


# Signals for our heartbeat
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)
