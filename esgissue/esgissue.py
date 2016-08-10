#!/usr/bin/env python
"""
   :platform: Unix
   :synopsis: Manages ESGF issues on BitBucket repository.

"""

# Module imports
from uuid import uuid4
import argparse
from utils import MultilineFormatter, init_logging, get_file_path, get_ws_call, _get_datasets, _get_issue
from datetime import datetime
import os
import sys
import simplejson
import requests
from issue_handler import LocalIssue
# Program version
__version__ = 'v{0} {1}'.format('0.1', datetime(year=2016, month=04, day=11).strftime("%Y-%d-%m"))

# Rabbit MQ unsent messages directory
__UNSENT_MESSAGES_DIR__ = "{0}/unsent_rabbit_messages".format(os.path.dirname(os.path.abspath(__file__)))


def get_args():
    """
    Returns parsed command-line arguments. See ``esgissue -h`` for full description.

    :returns: The corresponding ``argparse`` Namespace

    """
    __TEMPLATE_HELP__ = """Required path of the issue JSON template."""
    __DSETS_HELP__ = """Required path of the affected dataset IDs list."""
    main = argparse.ArgumentParser(
        prog='esgissue',
        description="""The publication workflow on the ESGF nodes requires to deal with errata issues.
                    The background of the version changes has to be published alongside the data: what was updated,
                    retracted or removed, and why. Consequently, the publication of a new version of a dataset has to
                    be motivated by an issue.|n|n

                    "esgissue" allows the referenced data providers to easily create, document, update, close or remove
                    a validated issue. "esgissue" relies on the GitHub API v3 to deal with private repositories.|n|n

                    The issue registration always appears prior to the publication process and should be mandatory
                    for additional version, version removal or retraction.|n|n

                    "esgissue" works with both JSON and TXT files. This allows the data provider in charge of ESGF
                    issues to manage one or several JSON templates gathering the issues locally.|n|n

                    See full documentation on http://esgissue.readthedocs.org/""",
        formatter_class=MultilineFormatter,
        add_help=False,
        epilog="""Developed by:|n
                  Levavasseur, G. (UPMC/IPSL - glipsl@ipsl.jussieu.fr)|n
                  Bennasser, A. (UPMC/IPSL - abennasser@ipsl.jussieu.fr""")
    main._optionals.title = "Optional arguments"
    main._positionals.title = "Positional arguments"
    main.add_argument(
        '-h', '--help',
        action='help',
        help="""Show this help message and exit.""")
    main.add_argument(
        '-V',
        action='version',
        version='%(prog)s ({0})'.format(__version__),
        help="""Program version.""")
    subparsers = main.add_subparsers(
        title='Issue actions',
        dest='command',
        metavar='',
        help='')

    #######################################
    # Parent parser with common arguments #
    #######################################
    parent = argparse.ArgumentParser(add_help=False)
    # parent.add_argument(
    #     '-i',
    #     metavar='/esg/config/esgcet/.',
    #     type=str,
    #     default='/esg/config/esgcet/.',
    #     help="""Initialization/configuration directory containing "esg.ini"|n
    #         and "esg.<project>.ini" files. If not specified, the usual|n
    #         datanode directory is used.""")
    # parent.add_argument(
    #     '--log',
    #     metavar='$PWD',
    #     type=str,
    #     const=os.getcwd(),
    #     nargs='?',
    #     help="""Logfile directory. If not, standard output is used.""")
    parent.add_argument(
        '-v',
        action='store_true',
        default=False,
        help="""Verbose mode.""")
    parent.add_argument(
        '-h', '--help',
        action='help',
        help="""Show this help message and exit.""")

    ###################################
    # Subparser for "esgissue create" #
    ###################################
    create = subparsers.add_parser(
        'create',
        prog='esgissue create',
        description=""""esgissue create" registers one or several issues on a defined GitHub repository. The data
                    provider submits one or several JSON files gathering all issues information with a list of all
                    affected dataset IDs (see http://esgissue.readthedocs.org/configuration.html to get a template).|n|n

                    This action returns to the corresponding local JSON template:|n
                    - the corresponding issue number,|n
                    - the ESGF issue ID (as UUID),|n
                    - the creation date,|n
                    - the last updated date (same as the creation date).|n|n

                    The issue registration sets:|n
                    - the issue status to "New",|n
                    - the data provider GitHub login as the issue responsible,|n
                    - the issue format using a fixed HTML schema.|n|n

                    SEE http://esgissue.readthedocs.org/usage.html TO FOLLOW ALL REQUIREMENTS TO REGISTER AN ISSUE.|n|n

                    See "esgissue -h" for global help.""",
        formatter_class=MultilineFormatter,
        help="""Creates ESGF issues from a JSON template to the GitHub repository.|n
                See "esgissue create -h" for full help.""",
        add_help=False,
        parents=[parent])
    create._optionals.title = "Arguments"
    create._positionals.title = "Positional arguments"
    create.add_argument(
        '--issue',
        nargs='?',
        required=True,
        metavar='PATH/issue.json',
        type=str,
        help=__TEMPLATE_HELP__)
    create.add_argument(
        '--dsets',
        nargs='?',
        required=True,
        metavar='PATH/dsets.list',
        type=argparse.FileType('r'),
        help=__DSETS_HELP__)

    ###################################
    # Subparser for "esgissue update" #
    ###################################
    update = subparsers.add_parser(
        'update',
        prog='esgissue update',
        description=""""esgissue update" updates one or several issues on a defined GitHub repository. The data
                    provider submits one or several JSON files gathering all issues information with a list of all
                    affected dataset IDs (see http://esgissue.readthedocs.org/configuration.html to get a template).|n|n

                    This action returns the last updated date to the corresponding local JSON template.|n|n

                    SEE http://esgissue.readthedocs.org/usage.html TO FOLLOW ALL REQUIREMENTS TO UPDATE AN ISSUE.|n|n

                    See "esgissue -h" for global help.""",
        formatter_class=MultilineFormatter,
        help="""Updates ESGF issues from a JSON template to the GitHub repository.|n
                See "esgissue update -h" for full help.""",
        add_help=False,
        parents=[parent])
    update._optionals.title = "Optional arguments"
    update._positionals.title = "Positional arguments"
    update.add_argument(
        '--issue',
        nargs='?',
        required=True,
        metavar='PATH/issue.json',
        type=str,
        help=__TEMPLATE_HELP__)
    update.add_argument(
        '--dsets',
        nargs='?',
        required=True,
        metavar='PATH/dsets.list',
        type=argparse.FileType('r'),
        help=__DSETS_HELP__)

    ##################################
    # Subparser for "esgissue close" #
    ##################################
    close = subparsers.add_parser(
        'close',
        prog='esgissue close',
        description=""""esgissue close" closes one or several issues on a defined GitHub repository. The data
                    provider submits one or several JSON files gathering all issues information with a list of all
                    affected dataset IDs (see http://esgissue.readthedocs.org/configuration.html to get a template).|n|n

                    This action returns the date of closure to the corresponding local JSON template (as the same of
                    the last updated date).|n|n

                    SEE http://esgissue.readthedocs.org/usage.html TO FOLLOW ALL REQUIREMENTS TO CLOSE AN ISSUE.|n|n

                    See "esgissue -h" for global help.""",
        formatter_class=MultilineFormatter,
        help="""Closes ESGF issues on the GitHub repository.|n
                See "esgissue close -h" for full help.""",
        add_help=False,
        parents=[parent])
    close._optionals.title = "Optional arguments"
    close._positionals.title = "Positional arguments"
    close.add_argument(
        '--issue',
        nargs='?',
        required=True,
        metavar='PATH/issue.json',
        type=str,
        help=__TEMPLATE_HELP__)
    close.add_argument(
        '--dsets',
        nargs='?',
        required=True,
        metavar='PATH/dsets.list',
        type=argparse.FileType('r'),
        help=__DSETS_HELP__)

    #####################################
    # Subparser for "esgissue retrieve" #
    #####################################
    retrieve = subparsers.add_parser(
        'retrieve',
        prog='esgissue retrieve',
        description=""""esgissue retrieve" retrieves one or several issues from a defined GitHub repository. The data
                    provider submits one or several issue number he wants to retrieve and optional paths to write
                    them.|n|n

                    This action rebuilds:|n
                    - the corresponding issue template as a JSON file,|n
                    - the attached affected datasets list as a TEXT file.|n|n

                    SEE http://esgissue.readthedocs.org/usage.html TO FOLLOW ALL REQUIREMENTS TO RETRIEVE AN ISSUE.|n|n

                    See "esgissue -h" for global help.""",
        formatter_class=MultilineFormatter,
        help="""Retrieves ESGF issues from the GitHub repository to a JSON template.|n
                See "esgissue retrieve -h" for full help.""",
        add_help=False,
        parents=[parent])
    retrieve._optionals.title = "Optional arguments"
    retrieve._positionals.title = "Positional arguments"
    retrieve.add_argument(
        '--id',
        metavar='ID',
        type=str,
        nargs='+',
        default=None,
        help='One or several issue number(s) or ESGF id(s) to retrieve.|n Default is to retrieve all GitHub issues.')
    retrieve.add_argument(
        '--issues',
        nargs='?',
        metavar='$PWD/issues',
        default='{0}/issues'.format(os.getcwd()),
        type=str,
        help="""Output directory for the retrieved JSON templates.""")
    retrieve.add_argument(
        '--dsets',
        nargs='?',
        metavar='$PWD/dsets',
        default='{0}/dsets'.format(os.getcwd()),
        type=str,
        help="""Output directory for the retrieved lists of affected dataset IDs.""")

    return main.parse_args()


def process_command(command, issue_file, dataset_file, issue_path, dataset_path):
    payload = issue_file
    if dataset_file is not None:
        dsets = _get_datasets(dataset_file)
    else:
        dsets = None
    if command == 'create':
        payload['id'] = str(uuid4())
        payload['workflow'] = unicode('new')
    local_issue = LocalIssue(payload, dsets, issue_path, dataset_path, command)
    local_issue.validate(command)
    if command == 'create':
        local_issue.create()
    elif command == 'update':
        local_issue.update()
    elif command == 'close':
        local_issue.close()


def run():
    """
    Main process that\:
     * Parse command-line arguments,
     * Parse configuration file,
     * Initiates logger,
     * Check GitHub permissions,
     * Check Handle Service connection,
     * Run the issue action.

    """
    # Get command-line arguments
    args = get_args()
    # init logging
    # if args.v and args.log is not None:
    #     init_logging(args.log, level='DEBUG')
    # elif args.log is not None:
    #     init_logging(args.log)
    # else:
    #     init_logging(None)
    init_logging(None)
    # Run command

    if args.command != 'retrieve':
        issue_file = _get_issue(args.issue)
        dataset_file = _get_datasets(args.dsets)
        process_command(args.command, issue_file, dataset_file, args.issue, args.dsets)

    elif args.command == 'retrieve':
        if args.id is not None:
            list_of_ids = args.id
            # In the case the user is requesting more than one issue
            for directory in [args.issues, args.dsets]:
                # Added the '.' test to avoid creating directories that are intended to be files.
                if not os.path.exists(directory) and '.' not in directory:
                    os.makedirs(directory)
                # This tests whether a list of ids is provided with a directory where to dump the retrieved
                # issues and related datasets.
                if len(list_of_ids) > 1 and not os.path.isdir(directory):
                    print('You have provided multiple ids but a single file as destination, aborting.')
                    sys.exit(1)
            # Looping over list of ids provided
            for n in list_of_ids:
                local_issue = LocalIssue(None, None, None, None, args.command)
                local_issue.retrieve(n, args.issues, args.dsets)
        else:
            # TODO provide possibility to flush database contents from a dedicated webservice?
            pass


# Main entry point for stand-alone call.
if __name__ == "__main__":
    run()
