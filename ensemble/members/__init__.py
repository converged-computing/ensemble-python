def get_member(name, options=None):
    """
    Get a named member type
    """
    options = options or {}
    name = name.lower()
    if name == "flux":
        from ensemble.members.flux.queue import FluxQueue

        return FluxQueue(**options)
    raise ValueError(f"Member type {name} is not known")
