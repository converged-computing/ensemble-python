import ensemble.members.auth as auth
from ensemble.protos import ensemble_service_pb2, ensemble_service_pb2_grpc


class EnsembleClient:
    """
    The EnsembleClient is used by members to communicate with the grpc service.

    The grpc service will receive requests to grow/shrink, etc (requests that fall outside
    of the scope of the ensemble and require changing the member) and issue some kind of event
    that can be listened to by an entity to do it (e.g., Kubernetes). Right now we support
    update requests (to scale up and down) and status requests (to check on state that
    some grpc endpoint sees).
    """

    def __init__(self, host="localhost:50051", use_ssl=False):
        self.host = host
        self.use_ssl = use_ssl

    def update_request(self, member, action, payload):
        """
        Send an update request to the grpc server.
        """
        # These are submit variables. A more substantial submit script would have argparse, etc.
        request = ensemble_service_pb2.UpdateRequest(member=member, action=action, payload=payload)

        with auth.grpc_channel(self.host, self.use_ssl) as channel:
            stub = ensemble_service_pb2_grpc.EnsembleOperatorStub(channel)
            response = stub.ReceiveJobs(request)

            # Case 1: SUCCESS
            if response.status == 1:
                print("Successful update.")
            else:
                print("Issue with requesting update")
        return response
