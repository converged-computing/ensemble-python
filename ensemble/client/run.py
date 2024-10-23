import ensemble.members as members


def main(args, parser, extra, subparser):
    # Assemble options
    options = {"name": args.name, "port": args.port, "host": args.host}

    # This will raise an error if the member type (e.g., minicluster) is not known
    member = members.get_member(args.executor, options=options)

    member.load(args.config, args.debug)
    member.start()
