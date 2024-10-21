import ensemble.members as members


def main(args, parser, extra, subparser):
    # This will raise an error if the member type (e.g., minicluster) is not known
    member = members.get_member(args.executor)
    member.load(args.config, args.debug)
    member.start()
