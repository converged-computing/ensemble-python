def get_member(name, options=None):
    """
    Get a named member type
    """
    options = options or {}
    name = name.lower()
    if name == "flux":
        from ensemble.members.flux.queue import FluxQueue

        return FluxQueue(**options)
    if name == "minicluster":
        from ensemble.members.flux.minicluster import FluxMiniClusterQueue

        return FluxMiniClusterQueue(**options)
    raise ValueError(f"Member type {name} is not known")
