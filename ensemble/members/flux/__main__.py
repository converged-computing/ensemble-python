def main():
    """
    Small main function to run class directly.

    When run interactively like this, we don't have an algorithm here,
    but we start a handle, and then watch the queue and keep track of basic
    metrics. Functions are available (if desired) to orchestrate or control
    what is going on. For example:

    - getting metrics: about jobs being run
    - submit jobs: to the running queue
    - cancel jobs: to the running queue
    - stream events: to stream events to view.
    -
    """
    # Just import locally so if we aren't using flux, we do
    # not try to import it!
    from ensemble.members.flux.queue import FluxQueue

    q = FluxQueue()
    assert q
    print("Interact with the Flux Queue with the variable 'q'")
    import IPython

    IPython.embed()


if __name__ == "__main__":
    main()
