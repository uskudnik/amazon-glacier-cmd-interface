#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. module:: glacier.py
   :platform: Unix, Windows
   :synopsis: Command line interface for amazon glacier
"""

import sys
import os
import ConfigParser
import argparse
import re
import locale

def print_headers(headers):
    table = PrettyTable(["Header", "Value"])
    for header in headers:
        if len(str(header[1])) < 100:
            table.add_row(header)

    print table

def print_output(output, keys=None, sort_key=None):
    """
    Prettyprints output. Expects a list of identical dicts.
    Use the dict keys as headers; one line for each item.

    output: list of dicts, each dict {'header_key1':'data', 'header_key2':'data2' ... }
    keys: dict of header keys {'header1': 'header_key1', 'header2', 'header_key2'...}
    """

    if len(output) == 0:
        print 'No output!'
        return

    headers = [k for k in keys.keys()] if keys else output[0].keys()

    table = PrettyTable(headers)

    for line in output:
        if keys:
            table.add_row([line[keys[k]] for k in keys])
        else:
            table.add_row([line[k] for k in headers])

    if sort_key:
        table.sortby = sort_key
        
    print table
    

def default_glacier_wrapper(args):
    return GlacierWrapper(args.aws_access_key,
                          args.aws_secret_key,
                          args.region,
                          bookkeeping=args.bookkeeping,
                          bookkeeping_domain_name=args.bookkeeping_domain_name,
                          logfile=args.logfile,
                          loglevel=args.loglevel,
                          logtostdout=args.logtostdout)

def handle_errors(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except GlacierWrapper.GlacierWrapperException as e:

            # We are only interested in the error message as it is a
            # self-caused exception.
            e.write(indentation='||  ', stack=False, message=True)
            sys.exit(1)

    return wrapper

@handle_errors
def lsvault(args):
    glacier = default_glacier_wrapper(args)
    vault_list = glacier.lsvault()
    keys = {"Vault name": 'VaultName',
            "ARN": 'VaultARN',
            "Created": 'CreationDate',
            "Size": 'SizeInBytes'}
##    print_output(vault_list, keys=keys, sort_key="Vault name")
    print_output(vault_list, keys=keys)

@handle_errors
def mkvault(args):
    glacier = default_glacier_wrapper(args)

    response = glacier.mkvault(args.vault)
    print dict(response)["location"]
    print print_headers(response)

@handle_errors
def rmvault(args):
    glacier = default_glacier_wrapper(args)

    response = glacier.rmvault(args.vault)
    print print_headers(response)

@handle_errors
def describevault(args):
    glacier = default_glacier_wrapper(args)

    response = glacier.describevault(args.vault)

    keys = {"LastInventory": 'LastInventoryDate',
            "Archives": 'NumberOfArchives',
            "Size": 'SizeInBytes',
            "ARN": 'VaultARN',
            "Created": 'CreationDate'}
    print_output(response, keys=keys)

@handle_errors
def listmultiparts(args):
    glacier = default_glacier_wrapper(args)

    response = glacier.listmultiparts(args.vault)
    if not response:
        print 'No active multipart uploads.'

    else:
        headers = sorted(response[0].keys())
        print_output(response)

##    print "Marker: ", response['Marker']
##    if len(response['UploadsList']) > 0:
##        headers = sorted(response['UploadsList'][0].keys())
##        table = PrettyTable(headers)
##        for entry in response['UploadsList']:
##            table.add_row([locale.format('%d', entry[k], grouping=True) if k == 'PartSizeInBytes'
##                           else entry[k] for k in headers ])
##        print table

@handle_errors
def abortmultipart(args):
    glacier = default_glacier_wrapper(args)
    
    response = glacier.abortmultipart(args.vault, args.uploadId)
    print_headers(response)

@handle_errors
def listjobs(args):
    glacier = default_glacier_wrapper(args)

    job_list = glacier.listjobs(args.vault)

    if job_list == []:
        print 'No jobs.'
        return

    headers = {"Action": 'Action',
               "Archive ID": 'ArchiveId',
               "Status": 'StatusCode',
               "Initiated": 'CreationDate',
               "VaultARN": 'VaultARN',
               "Job ID": 'JobId'}
    print_output(job_list, keys=headers)


@handle_errors
def describejob(args):
    glacier = default_glacier_wrapper(args)
    gj = glacier.describejob(args.vault, args.jobid)
    print "Archive ID: %s\nJob ID: %s\nCreated: %s\nStatus: %s\n" % (gj['ArchiveId'],
                                                                     args.jobid, gj['CreationDate'],
                                                                     gj['StatusCode'])

@handle_errors
def download(args):
    glacier = default_glacier_wrapper(args)
    response = glacier.download(args.vault, args.archive, args.outfile, args.overwrite)
    if args.outfile:

        # Only print result when writing to file.
        print response


### Formats file sizes in human readable format. Anything bigger than TB
### is returned is TB. Number of decimals is optional, defaults to 1.
##def size_fmt(num, decimals = 1):
##    fmt = "%%3.%sf %%s"% decimals
##    for x in ['bytes','KB','MB','GB']:
##        if num < 1024.0:
##            return fmt % (num, x)
##        
##        num /= 1024.0
##        
##    return fmt % (num, 'TB')

@handle_errors
def upload(args):
    glacier = default_glacier_wrapper(args)
    response = glacier.upload(args.vault, args.filename, args.description, args.region, args.stdin,
                              args.partsize)
    print "Created archive with ID: ", response[0]
    print "Archive SHA256 tree hash: ", response[1]


@handle_errors
def getarchive(args):
    glacier = default_glacier_wrapper(args)
    response = glacier.getarchive(args.vault, args.archive)
    print_output(response)


@handle_errors
def rmarchive(args):
    glacier = default_glacier_wrapper(args)
    glacier.rmarchive(args.vault, args.archive)
    print "archive removed."
 

@handle_errors
def search(args, print_results=True):
    glacier = default_glacier_wrapper(args)
    response = glacier.search(vault=args.vault,
                              region=args.region,
                              search_term=args.searchterm,
                              file_name=args.filename,
                              print_results=True)
    print_output(response)



def inventory(args):

    glacier = default_glacier_wrapper(args)
    job, inventory = glacier.inventory(args.vault, args.refresh)

    if inventory:
        print "Inventory of vault: %s" % (inventory["VaultARN"],)
        print "Inventory Date: %s\n" % (inventory['InventoryDate'],)
        print "Content:"
        headers = {"Archive Description": 'ArchiveDescription',
                   "Uploaded": 'CreationDate',
                   "Size": 'Size',
                   "Archive ID": 'ArchiveId',
                   "SHA256 tree hash": 'SHA256TreeHash'}
        print_output(inventory['ArchiveList'], keys=headers)

    else:
        print "Inventory retrieval in progress."
        print "Job ID: %s."% job['JobId']
        print "Job started (time in UTC): %s."% job['CreationDate']

def main():
    program_description = u"""
    Command line interface for Amazon Glacier
    """

    # Config parser
    conf_parser = argparse.ArgumentParser(
                                formatter_class=argparse.ArgumentDefaultsHelpFormatter,
                                add_help=False)

    conf_parser.add_argument("-c", "--conf", default="~/.glacier-cmd",
        help="Name of the file to log messages to.", metavar="FILE")
    conf_parser.add_argument('--logtostdout', action='store_true',
        help='Send log messages to stdout instead of the config file.')

    args, remaining_argv = conf_parser.parse_known_args()

    # Here we parse config from files in home folder or in current folder
    # We use separate sections for aws and glacier specific configs
    aws = glacier = {}
    config = ConfigParser.SafeConfigParser()
    if config.read(['/etc/glacier-cmd.conf',
                    os.path.expanduser('~/.glacier-cmd'),
                    args.conf]):
        try:
            aws = dict(config.items("aws"))
        except ConfigParser.NoSectionError:
            pass
        try:
            glacier = dict(config.items("glacier"))
        except ConfigParser.NoSectionError:
            pass

    # Join config options with environments
    aws = dict(os.environ.items() + aws.items() )
    glacier = dict(os.environ.items() + glacier.items() )

    # Helper functions
    filt_s= lambda x: x.lower().replace("_","-")
    filt = lambda x,y="": dict(((y+"-" if y not in filt_s(k) else "") +
                             filt_s(k), v) for (k, v) in x.iteritems())
    a_required = lambda x: x not in filt(aws, "aws")
    required = lambda x: x not in filt(glacier)
    a_default = lambda x: filt(aws, "aws").get(x)
    default = lambda x: filt(glacier).get(x)

    # Main configuration parser
    parser = argparse.ArgumentParser(parents=[conf_parser],
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter,
                                     description=program_description)
    subparsers = parser.add_subparsers(title='Subcommands',
        help=u"For subcommand help, use: glacier-cmd <subcommand> -h")

    group = parser.add_argument_group('aws')
    help_msg_config = u"(Required if you have not created a \
                        ~/.glacier-cmd or /etc/glacier-cmd.conf config file)"
    group.add_argument('--aws-access-key',
                       required=a_required("aws-access-key"),
                       default=a_default("aws-access-key"),
                       help="Your aws access key " + help_msg_config)
    group.add_argument('--aws-secret-key',
                       required=a_required("aws-secret-key"),
                       default=a_default("aws-secret-key"),
                       help="Your aws secret key " + help_msg_config)
    group = parser.add_argument_group('glacier')
    group.add_argument('--region',
                       required=required("region"),
                       default=default("region"),
                       help="Region where you want to store \
                             your archives " + help_msg_config)
    group.add_argument('--bookkeeping',
                       required=False,
                       default=default("bookkeeping") and True,
                       action="store_true",
                       help="Should we keep book of all created archives.\
                             This requires a Amazon SimpleDB account and its \
                             bookkeeping domain name set")
    group.add_argument('--bookkeeping-domain-name',
                        required=False,
                        default=default("bookkeeping-domain-name"),
                        help="Amazon SimpleDB domain name for bookkeeping.")
    group.add_argument('--logfile',
                       required=False,
                       default=os.path.expanduser('~/.glacier-cmd.log'),
                       help='File to write log messages to.')
    group.add_argument('--loglevel',
                       required=False,
                       default=default('loglevel') if default('loglevel') else 'WARNING',
                       choices=["-1", "DEBUG", "0", "INFO", "1", "WARNING",
                                "2", "ERROR", "3", "CRITICAL"],
                       help="Set the lowest level of messages you want to log.")

    # glacier-cmd mkvault <vault>
    parser_mkvault = subparsers.add_parser("mkvault",
        help="Create a new vault.")
    parser_mkvault.add_argument('vault',
        help='The vault to be created.')
    parser_mkvault.set_defaults(func=mkvault)

    # glacier-cmd lsvault    
    parser_lsvault = subparsers.add_parser("lsvault",
        help="List available vaults.")
    parser_lsvault.set_defaults(func=lsvault)

    # glacier-cmd describevault <vault>
    parser_describevault = subparsers.add_parser('describevault',
        help='Describe a vault.')
    parser_describevault.add_argument('vault',
        help='The vault to be described.')
    parser_describevault.set_defaults(func=describevault)

    # glacier-cmd rmvault <vault>
    parser_rmvault = subparsers.add_parser('rmvault',
        help='Remove a vault.')
    parser_rmvault.add_argument('vault',
        help='The vault to be removed.')
    parser_rmvault.set_defaults(func=rmvault)

    # glacier-cmd upload <vault> <filename> [<description>] [--name <store file name>] [--partsize <part size>]
    # glacier-cmd upload <vault> [<description>] --stdin [--name <store file name>] [--partsize <part size>]
    parser_upload = subparsers.add_parser('upload',
        formatter_class=argparse.RawTextHelpFormatter,
        help='Upload an archive to Amazon Glacier.')
    parser_upload.add_argument('vault',
        help='The vault the archive is to be stored in.')
    parser_upload.add_argument('filename', nargs='?', default=None,
        help='''\
The name of the local file to be uploaded.
May be omitted if --stdin is used.''')
    parser_upload.add_argument('--stdin', action='store_true',
        help='''\
Read data from stdin, instead of local file. 
If enabled, <filename> is ignored and may be omitted.''')
    parser_upload.add_argument('--name', default=None,
        help='''\
Use the given name as the filename for bookkeeping 
purposes. To be used in conjunction with --stdin or 
when the file being uploaded is a temporary file.''')
    parser_upload.add_argument('--partsize', type=int, default=-1,
        help='''\
Part size to use for upload (in MB). Must
be a power of 2 in the range:
    1, 2, 4, 8, ..., 2,048, 4,096.
Values that are not a power of 2 will be
adjusted upwards to the next power of 2.

Amazon accepts up to 10,000 parts per upload.

Smaller parts result in more frequent progress
updates, and less bandwidth wasted if a part
needs to be re-transmitted. On the other hand,
smaller parts limit the size of the archive that
can be uploaded. Some examples:

partsize  MaxArchiveSize
    1        1*1024*1024*10000 ~= 9.7 GB
    4        4*1024*1024*10000 ~= 39 GB
   16       16*1024*1024*10000 ~= 156 GB
  128      128*1024*1024*10000 ~= 1.2 TB
 4096     4096*1024*1024*10000 ~= 39 TB

If not given, the smallest possible part size
will be used when uploading a file, and 128 MB
when uploading from stdin.''')
    parser_upload.add_argument('description', nargs='?', default=None,
        help='Description of the file to be uploaded. Use quotes \
              if your file contains spaces. (optional).')
    parser_upload.set_defaults(func=upload)

    # glacier-cmd listmultiparts <vault>
    parser_listmultiparts = subparsers.add_parser('listmultiparts',
        help='List all active multipart uploads.')
    parser_listmultiparts.add_argument('vault',
        help='The vault to check the active multipart uploads for.')
    parser_listmultiparts.set_defaults(func=listmultiparts)

    # glacier-cmd abortmultipart <vault> <uploadId>
    parser_abortmultipart = subparsers.add_parser('abortmultipart',
        help='Abort a multipart upload.')
    parser_abortmultipart.add_argument('vault',
        help='The vault the upload is for.')
    parser_abortmultipart.add_argument('uploadId',
        help='The id of the upload to be aborted, try listmultiparts.')
    parser_abortmultipart.set_defaults(func=abortmultipart)

    # glacier-cmd inventory <vault> [--refresh]
    parser_inventory = subparsers.add_parser('inventory',
        help='List inventory of a vault, if available. If not available, \
              creates inventory retrieval job if none running already.')
    parser_inventory.add_argument('vault',
        help='The vault to list the inventory of.')
    parser_inventory.add_argument('--refresh', action='store_true',
        help='Create an inventory retrieval job, even if inventory is \
              available or with another retrieval job running.')
    parser_inventory.set_defaults(func=inventory)

    # glacier-cmd getarchive <vault> <archive>
    parser_getarchive = subparsers.add_parser('getarchive',
        help='Requests to make an archive available for download.')
    parser_getarchive.add_argument('vault',
        help='The vault the archive is stored in.')
    parser_getarchive.add_argument('archive',
        help='The archive id.')
    parser_getarchive.set_defaults(func=getarchive)

    # glacier-cmd download <vault> <archive> [--outfile <file name>]
    parser_download = subparsers.add_parser('download',
        help='Download a file by archive id.')
    parser_download.add_argument('vault',
        help="Specify the vault in which archive is located.")
    parser_download.add_argument('archive',
        help='The archive to be downloaded.')
    parser_download.add_argument('--outfile',
        help='The name of the local file to store the archive. \
              If omitted, stdout will be used.')
    parser_download.add_argument('--overwrite', action='store_true',
        help='Overwrite an existing local file if one exists when \
              downloading an archive.')
    parser_download.set_defaults(func=download)

    # glacier-cmd rmarchive <vault> <archive>
    parser_rmarchive = subparsers.add_parser('rmarchive',
        help='Remove archive from Amazon Glacier.')
    parser_rmarchive.add_argument('vault',
        help='The vault the archive is stored in.')
    parser_rmarchive.add_argument('archive',
        help='The archive id of the archive to be removed.')
    parser_rmarchive.set_defaults(func=rmarchive)

    # glacier-cmd search [<vault>] [--filename <file name>] [--searchterm <search term>]
    parser_search = subparsers.add_parser('search',
        help='Search Amazon SimpleDB database for available archives \
              (requires bookkeeping to be enabled).')
    parser_search.add_argument('vault', nargs='?', default=None,
        help='The vault to search in. Searching all if omitted.')
    parser_search.add_argument('--filename', default=None,
        help='Search key for searching by (part of) file names.')
    parser_search.add_argument('--searchterm', default=None,
        help='Search key for searching (part of) description fields.')
    parser_search.set_defaults(func=search)

    # glacier-cmd listjobs <vault>
    parser_listjobs = subparsers.add_parser('listjobs',
        help='List active jobs in a vault.')
    parser_listjobs.add_argument('vault',
        help='The vault to list the jobs for.')
    parser_listjobs.set_defaults(func=listjobs)

    # glacier-cmd describejob <vault>
    parser_describejob = subparsers.add_parser('describejob',
        help='Describe a job.')
    parser_describejob.add_argument('vault',
        help='The vault the job is listed for.')
    parser_describejob.add_argument('jobid',
        help='The job ID of the job to be described.')
    parser_describejob.set_defaults(func=describejob)


    # TODO args.logtostdout becomes false when parsing the remaining_argv
    # so here we bridge this. A bad hack but it works.
    logtostdout = args.logtostdout

    # Process the remaining arguments.
    args = parser.parse_args(remaining_argv)

    args.logtostdout = logtostdout

    # Run the subcommand.
    args.func(args)

if __name__ == "__main__":
    sys.exit(main())
