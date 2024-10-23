import argparse
import json
import logging
import os
import sys
from concurrent import futures

import grpc
from kubernetes import client, config

import ensemble.defaults as defaults
import ensemble.metrics as m
import ensemble.utils as utils
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
    start.add_argument(
        "--host",
        help="Host to run application (defaults to localhost)",
        default="localhost",
    )
    start.add_argument(
        "--kubernetes",
        help="Indicate running inside Kubernetes (will look for config and namespace, etc)",
        action="store_true",
        default=False,
    )
    return parser


class EnsembleEndpoint(api.EnsembleOperatorServicer):
    """
    An EnsembleEndpoint runs a grpc service for an ensemble.
    """

    def RequestAction(self, request, context):
        """
        Request an action is performed according to an algorithm.

        This is (currently) just used for testing since outside of
        Kubernetes we don't yet have environments that can actually
        grow or shrink.
        """
        print(f"Member {request.member}")
        print(f"Name {request.name}")
        print(f"Action {request.action}")
        print(f"Payload {request.payload}")
        response = ensemble_service_pb2.Response()
        print(response)
        if request.action == "grow":
            print("Received request to grow")
        elif request.action == "shrink":
            print("Received request to shrink")
        else:
            print("Received unknown request")
        return response


class KubernetesEnsemble(api.EnsembleOperatorServicer):
    """
    A KubernetesEnsemble (endpoint) is expecting to be in a
    Kubernetes cluster.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.namespace = "default"
        self.setup()

    @property
    def client(self):
        config.load_incluster_config()
        return client.CoreV1Api()

    @property
    def custom_resource_client(self):
        config.load_incluster_config()
        return client.CustomObjectsApi()

    def setup(self):
        """
        Setup inside of the cluster, getting a namespace.
        """
        if os.path.exists(defaults.service_account_file):
            self.namespace = utils.read_file(defaults.service_account_file)
        print(f"    Discovered namespace {self.namespace}")

    def RequestAction(self, request, context):
        """
        Request an action is performed according to an algorithm.

        This is (currently) just used for testing since outside of
        Kubernetes we don't yet have environments that can actually
        grow or shrink.
        """
        print(f"Member {request.member}")
        print(f"Name {request.name}")
        print(f"Action {request.action}")
        print(f"Payload {request.payload}")

        # Assume first an erroneous response
        response = ensemble_service_pb2.Response()
        response.status = ensemble_service_pb2.Response.ResultType.ERROR

        # Payload has version and group, and must be loadable and have them!
        try:
            payload = json.loads(request.payload)
        except Exception as err:
            print(f"Invalid payload {payload}: {err}")
            return response

        try:
            minicluster = self.get_minicluster(request)
        except Exception as err:
            print(err)
            return response

        # Request to grow
        current_size = minicluster["spec"]["size"]
        if request.action == "grow":
            change_in_size = payload.get("grow") or 1
            if change_in_size <= 0:
                print(f"Invalid grow request {change_in_size}")
                return response
            prefix = "🍔 Received request to grow from"

        # Reset a counter, typically after an update event
        elif request.action == "shrink":
            change_in_size = payload.get("shrink") or 1

            # A shrink of 0 is still not allowed
            if change_in_size == 0:
                print(f"Invalid shrink request {change_in_size}")
                return response

            # We assume that someone might put a positive here
            if change_in_size > 0:
                change_in_size = change_in_size * -1
            prefix = "🥕 Received request to shrink from"

        # This can give a final dump / view of job info
        else:
            print(f"Received unknown request action {request.action}")
            return response

        # Calculate the updated size to grow or shrink
        updated_size = calculate_updated_size(minicluster, change_in_size)
        print(f"{prefix} {current_size} to {updated_size}")

        # Make the request to update the MiniCluster
        try:
            self.update_minicluster_size(minicluster, updated_size)
        except Exception as err:
            print(err)
            return response

        response.status = ensemble_service_pb2.Response.ResultType.SUCCESS
        print(response)
        return response

    def update_minicluster_size(self, minicluster, updated_size):
        """
        Update the minicluster size to a new desired size.
        Validation should already have been done here for the size.
        """
        try:
            k8s = self.custom_resource_client
        except Exception as err:
            raise ValueError(f"Cannot create an in cluster Kubernetes client: {err}")

        # Derive the group and version from apiVersion
        api_version = minicluster["apiVersion"]
        group, version = api_version.split("/", 1)

        # We create a patch to adjust the size
        patch = {"spec": {"size": updated_size}}
        try:
            k8s.patch_namespaced_custom_object(
                group=group,
                version=version,
                plural="miniclusters",
                name=minicluster["metadata"]["name"],
                namespace=minicluster["metadata"]["namespace"],
                body=patch,
            )
        except Exception as err:
            raise ValueError(f"Issue patching MiniCluster: {err}")

    def get_minicluster(self, request):
        """
        Given a payload from the ensemble member, retrieve the MiniCluster
        """
        # The payload has already been validated (to load) by the calling function
        payload = json.loads(request.payload)

        # Create the kubernetes client using an in cluster config
        try:
            k8s = self.custom_resource_client
        except Exception as err:
            raise ValueError(f"Cannot create an in cluster Kubernetes client: {err}")

        group = payload["group"]
        version = payload["version"]

        # Find the minicluster in the namespace (works via custom rbac and service account)
        try:
            miniclusters = k8s.list_namespaced_custom_object(
                group=group, version=version, plural=request.member, namespace=self.namespace
            )
        except Exception as err:
            raise ValueError(f"Cannot get MiniCluster: {err}")

        # We need to find index 0
        minicluster_name = request.name
        minicluster = None
        for mc in miniclusters.get("items", []):
            if mc["metadata"]["name"] == minicluster_name:
                minicluster = mc
                break

        # We didn't find a matching name.
        if minicluster is None:
            raise ValueError(f"MiniCluster with name {minicluster_name} was not found")
        return minicluster


def calculate_updated_size(minicluster, change_size):
    """
    Given a minicluster and request to grow or shrink,
    calculate the new size and ensure within the bounds.
    """
    # Do a check for limits. The operator will do this, but we might as
    # well avoid the ping to it if we can check here
    min_size = minicluster["spec"]["minSize"]
    max_size = minicluster["spec"]["maxSize"]
    current_size = minicluster["spec"]["size"]
    updated_size = current_size + change_size

    # Size checks
    if updated_size > max_size:
        print(
            f"Warning: requested size {updated_size} exceeds max of {max_size}. Updating to {max_size}"
        )
        updated_size = max_size

    # Don't go below min size allowed
    if updated_size < min_size:
        print(
            f"Warning: requested size {updated_size} is smaller than min size of {min_size}. Updating to {min_size}"
        )
        updated_size = min_size

    return updated_size


def serve(args):
    """
    serve the ensemble endpoint for the MiniCluster
    """
    global metrics
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=args.workers))

    endpoint = EnsembleEndpoint()
    if args.kubernetes:
        endpoint = KubernetesEnsemble()
    api.add_EnsembleOperatorServicer_to_server(endpoint, server)

    host = f"{args.host}:{args.port}"
    server.add_insecure_port(f"{host}")
    print(f"🥞️ Starting ensemble endpoint at {host}")

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
    serve(args)


if __name__ == "__main__":
    main()
