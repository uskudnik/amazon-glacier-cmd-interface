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
import glob
import csv
import json

from prettytable import PrettyTable

from GlacierWrapper import GlacierWrapper

from functools import wraps
from glacierexception import *

def output_headers(headers, output):
    """
    Prints a list of headers - single item output.

    :param headers: the output to be printed as {'header1':'data1',...}
    :type headers: dict
    """
    rows = [(k, headers[k]) for k in headers.keys()]
    if output == 'print':
        table = PrettyTable(["Header", "Value"])
        for row in rows:
            if len(str(row[1])) < 100:
                table.add_row(row)
        
        print table
        
    if output == 'csv':
        csvwriter = csv.writer(sys.stdout, quoting=csv.QUOTE_ALL)
        for row in rows:
            csvwriter.writerow(row)
        
    if output == 'json':
        print json.dumps(headers)

def output_table(results, output, keys=None, sort_key=None):
    """
    Prettyprints results. Expects a list of identical dicts.
    Use the dict keys as headers unless keys is given; one line for each item.

    Expected format of data is a list of dicts:
    [{'key1':'data1.1', 'key2':'data1.2', ... },
     {'key1':'data1.2', 'key2':'data2.2', ... },
     ...]
    keys: dict of headers to be printed for each key:
    {'key1':'header1', 'key2':'header2',...}

    sort_key: the key to use for sorting the table.
    """

    if output == 'print':
        if len(results) == 0:
            print 'No output!'
            return

        headers = [keys[k] for k in keys.keys()] if keys else results[0].keys()
        table = PrettyTable(headers)
        for line in results:
            table.add_row([line[k] for k in (keys.keys() if keys else headers)])

        if sort_key:
            table.sortby = keys[sort_key] if keys else sort_key
            
        print table
        
    if output == 'csv':
        csvwriter = csv.writer(sys.stdout, quoting=csv.QUOTE_ALL)
        keys = results[0].keys()
        csvwriter.writerow(keys)
        for row in results:
            csvwriter.writerow([row[k] for k in keys])
            
    if output == 'json':
        print json.dumps(results)

def output_msg(msg, output, success=True):
    """
    In case of a single message output, e.g. nothing found.

    :param msg: a single message to output.
    :type msg: str
    :param success: whether the operation was a success or not.
    :type success: boolean
    """
    if output == 'print':
        print msg
        
    if output == 'csv':
        csvwriter = csv.writer(sys.stdout, quoting=csv.QUOTE_ALL)
        csvwriter.writerow(msg)
            
    if output == 'json':
        print json.dumps(msg)
        
    if not success:
        sys.exit(125)

def size_fmt(num, decimals = 1):
    """
    Formats file sizes in human readable format. Anything bigger than TB
    is returned is TB. Number of decimals is optional, defaults to 1.
    """
    fmt = "%%3.%sf %%s"% decimals
    for x in ['bytes','KB','MB','GB']:
        if num < 1024.0:
            return fmt % (num, x)
        
        num /= 1024.0
        
    return fmt % (num, 'TB')

def default_glacier_wrapper(args):
    """
    Convenience function to call an instance of GlacierWrapper
    with all required arguments.
    """
    return GlacierWrapper(args.aws_access_key,
                          args.aws_secret_key,
                          args.region,
                          bookkeeping=args.bookkeeping,
                          bookkeeping_domain_name=args.bookkeeping_domain_name,
                          sns=args.sns_enable,
                          logfile=args.logfile,
                          loglevel=args.loglevel,
                          logtostdout=args.logtostdout)

def handle_errors(fn):
    """
    Decorator for exception handling.
    """
    @wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except GlacierException as e:

            # We are only interested in the error message in case it is a
            # self-caused exception.
            e.write(indentation='||  ', stack=False, message=True)
            sys.exit(e.exitcode)

    return wrapper

@handle_errors
def lsvault(args):
    """
    Returns a list of vaults (if any).
    """
    glacier = default_glacier_wrapper(args)
    vault_list = glacier.lsvault()
    keys = {'VaultName': "Vault name",
            'VaultARN': "ARN",
            'CreationDate': "Created",
            'SizeInBytes': "Size"}
    output_table(vault_list, args.output, keys=keys)

@handle_errors
def mkvault(args):
    """
    Create a new vault.
    """
    glacier = default_glacier_wrapper(args)
    response = glacier.mkvault(args.vault)
    output_headers(response, args.output)

@handle_errors
def rmvault(args):
    """
    Remove a vault.
    """
    glacier = default_glacier_wrapper(args)
    response = glacier.rmvault(args.vault)
    output_headers(response, args.output)

@handle_errors
def describevault(args):
    """
    Give the description of a vault.
    """
    glacier = default_glacier_wrapper(args)
    response = glacier.describevault(args.vault)
    headers = {'LastInventoryDate': "LastInventory",
               'NumberOfArchives': "Archives",
               'SizeInBytes': "Size",
               'VaultARN': "ARN",
               'CreationDate': "Created"}
    output_headers(response, args.output)

@handle_errors
def listmultiparts(args):
    """
    Give an overview of all multipart uploads that are not finished.
    """
    glacier = default_glacier_wrapper(args)
    response = glacier.listmultiparts(args.vault)
    if not response:
        output_msg('No active multipart uploads.', args.output, success=False)
    else:
        output_table(response, args.output)

@handle_errors
def abortmultipart(args):
    """
    Abort a multipart upload which is in progress.
    """
    glacier = default_glacier_wrapper(args)
    response = glacier.abortmultipart(args.vault, args.uploadId)
    output_headers(response, args.output)

@handle_errors
def listjobs(args):
    """
    List all the active jobs for a vault.
    """
    glacier = default_glacier_wrapper(args)
    job_list = glacier.list_jobs(args.vault)
    if job_list == []:
        output_msg('No jobs.', args.output, success=False)
        return

    headers = {'Action': "Action",
               'ArchiveId': "Archive ID",
               'StatusCode': "Status",
               'CreationDate': "Initiated",
               'VaultARN': "VaultARN",
               'JobId': "Job ID"}
    output_table(job_list, args.output, keys=headers)

@handle_errors
def describejob(args):
    """
    Give the description of a job.'
    """
    glacier = default_glacier_wrapper(args)
    job = glacier.describejob(args.vault, args.jobid)
    output_headers(job, args.output)

@handle_errors
def download(args):
    """
    Download an archive.
    """
    glacier = default_glacier_wrapper(args)
    response = glacier.download(args.vault, args.archive, args.partsize,
                                out_file_name=args.outfile, overwrite=args.overwrite)
    if args.outfile:
        output_msg(response, args.output, success=True)

@handle_errors
def upload(args):
    """
    Upload a file or a set of files to a Glacier vault.
    """

    # See if we got a bacula-style file set.
    # This is /path/to/vol001|vol002|vol003
    if args.bacula:
        if len(args.filename) > 1:
            raise InputException(
                'Bacula-style file name input can accept only one file name argument.')
        
        fileset = args.filename[0].split('|')
        if len(fileset) > 1:
            dirname = os.path.dirname(fileset[0])
            args.filename = [fileset[0]]
            args.filename += [os.path.join(dirname, fileset[i]) for i in range(1, len(fileset))]

    glacier = default_glacier_wrapper(args)
    args.filename = args.filename if args.filename else [None]
    for f in args.filename:
        if f:

            # In case the shell does not expand wildcards, if any, do this here.
            if f[0] == '~':
                f = os.path.expanduser(f)

            results = []
            globbed = glob.glob(f)
            if globbed:
                for g in globbed:
                    response = glacier.upload(args.vault, g, args.description, args.region, args.stdin,
                                              args.name, args.partsize, args.uploadid, args.resume)
                    result = {"Uploaded file": g,
                              "Created archive with ID": response[0],
                              "Archive SHA256 tree hash": response[1]}
                    
                    print "Uploaded file: %s."% g
                    print "Created archive with ID: %s"% response[0]
                    print "Archive SHA256 tree hash: %s."% response[1]
            else:
                raise InputException(
                    "File name given for upload can not be found: %s."% f,
                    code='CommandError')
        else:

            # No file name; using stdin.
            response = glacier.upload(args.vault, f, args.description, args.region, args.stdin,
                                      args.name, args.partsize, args.uploadid, args.resume)
            result = {"Created archive with ID": response[0],
                      "Archive SHA256 tree hash": response[1]}
            
        results.append(result)
        
    output_table(results, args.output) if len(results) > 1 else output_headers(results[0], args.output)

@handle_errors
def getarchive(args):
    """
    Initiate an archive retrieval job.
    """
    glacier = default_glacier_wrapper(args)
    status, job, jobid = glacier.getarchive(args.vault, args.archive)
    output_headers(job, args.output)

@handle_errors
def rmarchive(args):
    """
    Remove an archive from a vault.
    """
    glacier = default_glacier_wrapper(args)
    glacier.rmarchive(args.vault, args.archive)
    output_msg("Archive removed.", args.output, success=True)

@handle_errors
def search(args):
    """
    Search the database for file name or description.
    """
    glacier = default_glacier_wrapper(args)
    response = glacier.search(vault=args.vault,
                              region=args.region,
                              search_term=args.searchterm,
                              file_name=args.filename)
    output_table(response, args.output)

@handle_errors
def inventory(args):
    """
    Fetch latest inventory (or start a retrieval job if not ready).
    """
    glacier = default_glacier_wrapper(args)
    output = args.output
    if sys.stdout.isatty() and output == 'print':
        print 'Checking inventory, please wait.\r',
        sys.stdout.flush()
        
    job, inventory = glacier.inventory(args.vault, args.refresh)
    if inventory:
        if sys.stdout.isatty() and output == 'print':
            print "Inventory of vault: %s" % (inventory["VaultARN"],)
            print "Inventory Date: %s\n" % (inventory['InventoryDate'],)
            print "Content:"
            
        headers = {'ArchiveDescription': 'Archive Description',
                   'CreationDate': 'Uploaded',
                   'Size': 'Size',
                   'ArchiveId': 'Archive ID',
                   'SHA256TreeHash': 'SHA256 tree hash'}
        output_table(inventory['ArchiveList'], args.output, keys=headers)
        if sys.stdout.isatty() and output == 'print':
            size = 0
            for item in inventory['ArchiveList']:
                size += int(item['Size'])

            print 'This vault contains %s items, total size %s.'% (len(inventory['ArchiveList']), size_fmt(size))

    else:
        result = {'Status':'Inventory retrieval in progress.',
                  'Job ID':job['JobId'],
                  'Job started (time in UTC)':job['CreationDate']}
        output_headers(result, args.output)

@handle_errors
def treehash(args):
    """
    Calculates the tree hash of the given file(s).
    """
    glacier = default_glacier_wrapper(args)
    hash_results = []
    for f in args.filename:
        if f:

            # In case the shell does not expand wildcards, if any, do this here.
            if f[0] == '~':
                f = os.path.expanduser(f)
                
            globbed = glob.glob(f)
            if globbed:
                for g in globbed:
                    hash_results.append(
                        {'File name': g,
                         'SHA256 tree hash': glacier.get_tree_hash(g)})
        else:
            raise InputException(
                'No file name given.',
                code='CommandError')

    output_table(hash_results, args.output)

def snssubscribe(args):
    """
    Subscribe to notifications by method specified by user.
    """
    protocol = args.protocol
    endpoint = args.endpoint
    vault_names = args.vault

    glacier = default_glacier_wrapper(args)
    response = glacier.sns_subscribe(vault_names, protocol, endpoint)
    output_table(response, args.output)

def snslist(args):
    """
    List subscriptions
    """
    protocol = args.protocol
    endpoint = args.endpoint
    vault = args.vault

    glacier = default_glacier_wrapper(args)
    response = glacier.sns_list(vault, protocol, endpoint)
    output_table(response, args.output)

def snsunsubscribe(args):
    """
    Unsubscribe from notifications for specified protocol, endpoint and vault
    """
    protocol = args.protocol
    endpoint = args.endpoint
    vault = args.vault

    glacier = default_glacier_wrapper(args)
    response = glacier.sns_unsubscribe(vault, protocol, endpoint)
    output_table(response, args.output)    

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
        try:
            sns = dict(config.items("SNS"))
        except ConfigParser.NoSectionError:
            pass

    # Join config options with environments
    aws = dict(os.environ.items() + aws.items() )
    glacier = dict(os.environ.items() + glacier.items() )
    sns = dict(os.environ.items() + sns.items() )

    # Helper functions
    filt_s= lambda x: x.lower().replace("_","-")
    filt = lambda x,y="": dict(((y+"-" if y not in filt_s(k) else "") +
                             filt_s(k), v) for (k, v) in x.iteritems())
    a_required = lambda x: x not in filt(aws, "aws")
    required = lambda x: x not in filt(glacier)
    a_default = lambda x: filt(aws, "aws").get(x)
    default = lambda x: filt(glacier).get(x)

    default_sns = lambda x: filt(sns).get(x)

    # Main configuration parser
    parser = argparse.ArgumentParser(parents=[conf_parser],
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter,
                                     description=program_description)
    subparsers = parser.add_subparsers(title='Subcommands',
        help=u"For subcommand help, use: glacier-cmd <subcommand> -h")

    # Amazon Web Services settings
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

    # Short notification service settings
    group = parser.add_argument_group('SNS')
    group.add_argument('--sns-enable',
                       required=False,
                       action="store_true",
                       default=default_sns("notifications"))

    # Glacier settings
    group = parser.add_argument_group('glacier')
    group.add_argument('--region',
                       required=required("region"),
                       default=default("region"),
                       help="Region where you want to store \
                             your archives " + help_msg_config)
    bookkeeping = default("bookkeeping") and True
    group.add_argument('--bookkeeping',
                       required=False,
                       default=bookkeeping,
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
    group.add_argument('--output',
                       required=False,
                       default=default('output') if default('output') else 'print',
                       choices=['print', 'csv', 'json'],
                       help='Set how to return results: print to the screen, or as csv resp. json string.')

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

    # glacier-cmd upload <vault> <filename> [--description <description>] [--name <store file name>] [--partsize <part size>]
    # glacier-cmd upload <vault> --stdin [--description <description>] [--name <store file name>] [--partsize <part size>]
    parser_upload = subparsers.add_parser('upload',
        formatter_class=argparse.RawTextHelpFormatter,
        help='Upload an archive to Amazon Glacier.')
    parser_upload.add_argument('vault',
        help='The vault the archive is to be stored in.')
    group = parser_upload.add_mutually_exclusive_group(required=True)
    group.add_argument('filename', nargs='*', default=None,
        help='''\
The name(s) of the local file(s) to be uploaded. Wildcards
are accepted. Can not be used if --stdin is used.''')
    group.add_argument('--stdin', action='store_true',
        help='''\
Read data from stdin, instead of local file. 
Can not be used if <filename> is given.''')
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
    parser_upload.add_argument('--description', default=None,
        help='''\
Description of the file to be uploaded. Use quotes
if your file name contains spaces. (optional).''')
    parser_upload.add_argument('--uploadid', default=None,
        help='''\
The uploadId of a multipart upload that is not
finished yet. If given, glacier-cmd will attempt
to resume this upload using the given file, or by
re-reading the data from stdin.''')
    parser_upload.add_argument('--resume', action='store_true',
        help='''\
Attempt to resume an interrupted multi-part upload.
Does not work in combination with --stdin, and
requires bookkeeping to be enabled.
(not implemented yet)''')
    parser_upload.add_argument('--bacula', action='store_true',
        help='''\
The (single!) file name will be parsed using Bacula's
style of providing multiple names on the command line.
E.g.: /path/to/backup/vol001|vol002|vol003''')
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
        formatter_class=argparse.RawTextHelpFormatter,
        help='Download a file by archive id.')
    parser_download.add_argument('vault',
        help="Specify the vault in which archive is located.")
    parser_download.add_argument('archive',
        help='The archive to be downloaded.')
    parser_download.add_argument('--outfile',
        help='''\
The name of the local file to store the archive.
If omitted, stdout will be used.''')
    parser_download.add_argument('--overwrite', action='store_true',
        help='''
Overwrite an existing local file if one exists when
downloading an archive.''')
    parser_download.add_argument('--partsize', type=int, default=-1,
        help='''\
Part size to use for download (in MB). Must
be a power of 2 in the range:
    1, 2, 4, 8, ..., 2,048, 4,096.
Values that are not a power of 2 will be
adjusted upwards to the next power of 2.

Amazon accepts up to 10,000 parts per download.

Smaller parts result in more frequent progress
updates, and less bandwidth wasted if a part
needs to be re-transmitted. On the other hand,
smaller parts limit the size of the archive that
can be downloaded and result in slower overall
performance. Some examples:

partsize  MaxArchiveSize
    1        1*1024*1024*10000 ~= 9.7 GB
    4        4*1024*1024*10000 ~= 39 GB
   16       16*1024*1024*10000 ~= 156 GB
  128      128*1024*1024*10000 ~= 1.2 TB
 4096     4096*1024*1024*10000 ~= 39 TB

If not given, the smallest possible part size
will be used depending on the size of the job
at hand.''')
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

    # glacier-cmd hash <filename>
    parser_describejob = subparsers.add_parser('treehash',
        help='Calculate the tree-hash (Amazon style sha256-hash) of a file.')
    parser_describejob.add_argument('filename', nargs='*',
        help='The filename to calculate the treehash of.')
    parser_describejob.set_defaults(func=treehash)

    # SNS related commands are located in their own subparser 
    parser_sns = subparsers.add_parser('sns', 
        help="Subcommands related to SNS")
    sns_subparsers = parser_sns.add_subparsers(title="Subcommands related to SNS")

    # glacier-cmd sns subscribe protocol endpoint [<vault> [vault ...]]
    sns_parser_subscribe = sns_subparsers.add_parser('subscribe')
    sns_parser_subscribe.add_argument("protocol",
        help="Protocol to use for SNS notifications. Options: HTTP(S), email or SMS.")
    sns_parser_subscribe.add_argument("endpoint",
        help="Either valid HTTP(S) address, email address or phone number.")
    sns_parser_subscribe.add_argument("vault", nargs="*",
        help="By default you subscribe to notifications from all vaults, \
        specify if you would like to limit to one or more.")
    sns_parser_subscribe.set_defaults(func=snssubscribe)

    # glacier-cmd sns list [--protocol <protocol>] [--endpoint <endpoint>] [--vault <vault>]
    sns_parser_list = sns_subparsers.add_parser('list')
    sns_parser_list.add_argument("--protocol",
        help="Show only subscriptions on a specified protocol.")
    sns_parser_list.add_argument("--endpoint",
        help="Show only subscriptions to a specified endpoint.")
    sns_parser_list.add_argument("--vault",
        help="Show only subscriptions for a specified vault.")
    sns_parser_list.set_defaults(func=snslist)

    # glacier-cmd sns unsubscribe vault [--protocol <protocol>] [--endpoint <endpoint>]
    sns_parser_unsubscribe = sns_subparsers.add_parser('unsubscribe')
    sns_parser_unsubscribe.add_argument("--protocol")
    sns_parser_unsubscribe.add_argument("--endpoint")
    sns_parser_unsubscribe.add_argument("vault")
    sns_parser_unsubscribe.set_defaults(func=snsunsubscribe)
    
    # glacier-cmd enableauto
    # parser_server = subparsers.add_parser('startserver')
    # parser_server.add_argument("--port")
    # parser_server.set_defaults(func=startserver)


    # TODO args.logtostdout becomes false when parsing the remaining_argv
    # so here we bridge this. An ugly hack but it works.
    logtostdout = args.logtostdout

    # Process the remaining arguments.
    args = parser.parse_args(remaining_argv)
    
    args.logtostdout = logtostdout

    # Run the subcommand.
    args.func(args)

if __name__ == "__main__":
    sys.exit(main())
