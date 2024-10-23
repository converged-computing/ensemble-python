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

    def __init__(self, **kwargs):
        """
        Create a new flux MiniCluster

        Since we need to communicate back to the grpc service, we require a name
        and namespace. This should be provided via the name kwargs, which is parsed
        into both. E.g,, --name default/ensemble. If a namespace is not provided,
        default is assumed.
        """
        super().__init__(**kwargs)
        self.set_identifier()

    def set_identifier(self):
        """
        Get the name/namespace of the MiniCluster
        """
        if "name" not in self.options or not self.options["name"]:
            raise ValueError("A --name (namespace/name) is required for a minicluster")
        name = self.options["name"]
        namespace = "default"
        if "/" in name:
            namespace, name = name.split("/")
        self.options["name"] = name
        self.options["namespace"] = namespace

    @property
    def host(self):
        """
        Host can be customized with options, and defaults to localhost:50051
        """
        host = self.options.get("host") or "localhost"
        port = self.options.get("port") or 50051
        return f"{host}:{port}"

    @property
    def client(self):
        """
        Ensure we have a connection to the service client.
        """
        if hasattr(self, "_client"):
            return self._client
        self._client = EnsembleClient(host=self.host)
        return self._client

    @property
    def payload(self):
        """
        Return the default payload
        """
        return {"version": "v1alpha2", "group": "flux-framework.org"}

    def grow(self, rule, record=None):
        """
        Request to the API to grow the MiniCluster
        """
        name = self.options["name"]
        payload = self.payload

        # Add the grow value to the payload
        payload["grow"] = rule.action.value()

        # Member "minicluster" should be plural here
        response = self.client.action_request(
            member=f"{self.name}s", name=name, action="grow", payload=payload
        )
        print(response)

    def shrink(self, rule, record=None):
        """
        Request to the API to shrink the MiniCluster
        """
        name = self.options["name"]

        # Add the grow value to the payload
        payload = self.payload
        payload["shrink"] = rule.action.value()

        response = self.client.action_request(
            member=f"{self.name}s", name=name, action="shrink", payload=payload
        )
        print(response)

    @property
    def name(self):
        """
        Name is used to identify the ensemble member type.
        """
        return "minicluster"
