#!/usr/bin/env python

# This is the ensemble client init, where we can start a client for a particular
# queue backend (like Flux)

import argparse
import sys

import ensemble


def get_parser():
    parser = argparse.ArgumentParser(
        description="Ensemble Python",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "--version",
        dest="version",
        help="show software version.",
        default=False,
        action="store_true",
    )

    description = "actions for Ensemble Python"
    subparsers = parser.add_subparsers(
        help="actions",
        title="actions",
        description=description,
        dest="command",
    )

    # print version and exit
    subparsers.add_parser("version", description="show software version")

    # Install a known recipe from the registry
    run = subparsers.add_parser(
        "run",
        description="run the ensemble",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    run.add_argument(
        "--executor",
        help="Executor to use (defaults to flux)",
        choices=["flux"],
        default="flux",
    )

    for command in [run]:
        command.add_argument(
            "config",
            help="Ensemble configuration file (required)",
        )

    return parser


def run_ensemble():
    parser = get_parser()

    def help(return_code=0):
        version = ensemble.__version__

        print("\nEnsemble Python v%s" % version)
        parser.print_help()
        sys.exit(return_code)

    # If the user didn't provide any arguments, show the full help
    if len(sys.argv) == 1:
        help()

    # If an error occurs while parsing the arguments, the interpreter will exit with value 2
    args, extra = parser.parse_known_args()

    # Show the version and exit
    if args.command == "version" or args.version:
        print(ensemble.__version__)
        sys.exit(0)

    # retrieve subparser (with help) from parser
    helper = None
    subparsers_actions = [
        action for action in parser._actions if isinstance(action, argparse._SubParsersAction)
    ]
    for subparsers_action in subparsers_actions:
        for choice, subparser in subparsers_action.choices.items():
            if choice == args.command:
                helper = subparser
                break

    # Does the user want a shell?
    if args.command == "run":
        from .run import main

    # Pass on to the correct parser
    return_code = 0
    try:
        main(args=args, parser=parser, extra=extra, subparser=helper)
        sys.exit(return_code)
    except UnboundLocalError:
        return_code = 1

    help(return_code)


if __name__ == "__main__":
    run_ensemble()
