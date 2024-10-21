from ensemble.members.client import EnsembleClient
from ensemble.members.flux.queue import FluxQueue as MemberBase

# These are triggers supported for rules
rules = ["start", "metric"]


class FluxMiniClusterQueue(MemberBase):
    """
    The Flux Queue MiniCluster member type

    It uses the FluxQueue as a base. The main difference is that this
    member supports scale up and scale down for actions.
    """

    # TODO for ensemble operator - we need the ensemble name to identify it
    # perhaps generate randomly or similar?

    @property
    def client(self):
        """
        Ensure we have a connection to the service client.
        """
        # Do we have the ensemble client?
        # TODO allow to customize host, etc.
        if hasattr(self, "_client"):
            return self._client
        self._client = EnsembleClient()
        return self._client

    def grow(self, rule, record=None):
        """
        Request to the API to grow the MiniCluster
        """
        # For now use the ensemble type as the name
        # TODO this needs to be caught and decided upon - retry?
        response = self.client.action_request(self.name, "grow", {})
        print(response)

    def shrink(self, rule, record=None):
        """
        Request to the API to shrink the MiniCluster
        """
        response = self.client.action_request(self.name, "shrink", {})
        print(response)

    @property
    def name(self):
        """
        Name is used to identify the ensemble member type.
        """
        return "minicluster"
