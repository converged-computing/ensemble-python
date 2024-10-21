from ensemble.members.flux.queue import FluxQueue as MemberBase

# These are triggers supported for rules
rules = ["start", "metric"]


class FluxMiniClusterQueue(MemberBase):
    """
    The Flux Queue MiniCluster member type

    It uses the FluxQueue as a base. The main difference is that this
    member supports scale up and scale down for actions.
    """

    def grow(self, rule, record=None):
        """
        Request to the API to grow the MiniCluster
        """
        print("GROW Vanessa implement me")
        import IPython

        IPython.embed()

    def shrink(self, rule, record=None):
        """
        Request to the API to shrink the MiniCluster
        """
        print("SHRINK Vanessa implement me")
        import IPython

        IPython.embed()

    @property
    def name(self):
        return "MiniCluster"
