import argparse
import json
import logging
import sys
from concurrent import futures

import grpc

import ensemble.defaults as defaults
import ensemble.members as members
import ensemble.metrics as m
from ensemble.protos import ensemble_service_pb2
from ensemble.protos import ensemble_service_pb2_grpc as api

# TODO what metrics do we want on the level of the grpc server?
# probably something eventually related to fair share between ensembles?


def get_parser():
    parser = argparse.ArgumentParser(
        description="Ensemble Operator API Endpoint",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    subparsers = parser.add_subparsers(
        help="actions",
        title="actions",
        description="actions",
        dest="command",
    )

    # Local shell with client loaded
    start = subparsers.add_parser(
        "start",
        description="Start the running server.",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    start.add_argument(
        "--workers",
        help=f"Number of workers (defaults to {defaults.workers})",
        default=defaults.workers,
        type=int,
    )
    start.add_argument(
        "--port",
        help=f"Port to run application (defaults to {defaults.port})",
        default=defaults.port,
        type=int,
    )
    return parser


class EnsembleEndpoint(api.EnsembleOperatorServicer):
    """
    An EnsembleEndpoint runs inside the cluster.
    """

    def RequestStatus(self, request, context):
        """
        Request information about queues and jobs.
        """
        print(request)
        print(context)

        # This will raise an error if the member type (e.g., minicluster) is not known
        member = members.get_member(request.member)
        print(member)

        # If the flux handle didn't work, this might error
        try:
            payload = json.loads(request.payload)
        except Exception as e:
            print(e)
            return ensemble_service_pb2.Response(
                status=ensemble_service_pb2.Response.ResultType.ERROR
            )
        return ensemble_service_pb2.Response(
            payload=json.dumps(payload),
            status=ensemble_service_pb2.Response.ResultType.SUCCESS,
        )

    def RequestAction(self, request, context):
        """
        Request an action is performed according to an algorithm.
        """
        print(f"Member {request.member}")
        print(f"Namespace {request.namespace}")
        print(f"Action {request.action}")
        print(f"Payload {request.payload}")

        # Assume first successful response
        # status = ensemble_service_pb2.Response.ResultType.SUCCESS
        response = ensemble_service_pb2.Response()

        # The member primarily is directed to take the action
        # member = members.get_member(request.member)
        # print(member)
        print(response)

        if request.action == "grow":
            print("REQUEST TO GROW")
            # response.status = ensemble_service_pb2.Response.ResultType.ERROR

        # Reset a counter, typically after an update event
        elif request.action == "shrink":
            print("REQUEST TO SHRINK")

        # This can give a final dump / view of job info
        else:
            print("UNKNOWN REQUEST")
        return response


def serve(port, workers):
    """
    serve the ensemble endpoint for the MiniCluster
    """
    global metrics
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=workers))
    api.add_EnsembleOperatorServicer_to_server(EnsembleEndpoint(), server)
    server.add_insecure_port(f"[::]:{port}")
    print(f"🥞️ Starting ensemble endpoint at :{port}")

    # Kick off metrics collections
    metrics = m.Metrics()
    server.start()
    server.wait_for_termination()


def main():
    """
    Light wrapper main to provide a parser with port/workers
    """
    parser = get_parser()

    # If the user didn't provide any arguments, show the full help
    if len(sys.argv) == 1:
        help()

    # If an error occurs while parsing the arguments, the interpreter will exit with value 2
    args, _ = parser.parse_known_args()
    logging.basicConfig()
    serve(args.port, args.workers)


if __name__ == "__main__":
    main()
