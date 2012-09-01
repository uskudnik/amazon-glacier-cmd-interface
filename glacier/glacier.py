#!/usr/bin/env python
# encoding: utf-8
"""
glacier.py

MIT License

Copyright (C) 2012 and beyond by Urban Skudnik (urban.skudnik@gmail.com).

All rights reserved.

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE."""

import sys
import os
import select
import argparse
import re
import json
import datetime
import dateutil.parser
import pytz

import boto
import glaciercorecalls

MAX_VAULT_NAME_LENGTH = 255
VAULT_NAME_ALLOWED_CHARACTERS = "[a-zA-Z\.\-\_0-9]+"
READ_PART_SIZE= glaciercorecalls.GlacierWriter.DEFAULT_PART_SIZE

# Gets set in main
# TODO: Rewrite as args and not as global variables
BOOKKEEPING = None
BOOKKEEPING_DOMAIN_NAME = None
AWS_ACCESS_KEY = None
AWS_SECRET_KEY = None
DEFAULT_REGION = None

def check_vault_name(name):
    m = re.match(VAULT_NAME_ALLOWED_CHARACTERS, name)
    if len(name) > 255:
        raise Exception(u"Vault name can be at most 255 charecters long.")
    if len(name) == 0:
        raise Exception(u"Vault name has to be at least 1 character long.")
    if m.end() != len(name):
        raise Exception(u"Allowed characters are a–z, A–Z, 0–9, '_' (underscore),\
                          '-' (hyphen), and '.' (period)")
    return True

MAX_DESCRIPTION_LENGTH = 1024

def check_description(description):
    if len(description) > 1024:
        raise Exception(u"Description must be less or equal to 1024 characters.")

    for char in description:
        n = ord(char)
        if n < 32 or n > 126:
            raise Exception(u"The allowable characters are 7-bit ASCII without \
                              control codes, specifically ASCII values 32—126 \
                              decimal or 0x20—0x7E hexadecimal.")
    return True

def parse_response(response):
    if response.status == 403:
        print "403 Forbidden."
        print "\n"
        print "Reason:"
        print response.read()
        print response.msg
    print response.status, response.reason

def lsvault(args):
    region = args.region
    glacierconn = glaciercorecalls.GlacierConnection(args.aws_access_key, args.aws_secret_key, region=region)

    response = glacierconn.list_vaults()
    parse_response(response)
    jdata = json.loads(response.read())
    vault_list = jdata['VaultList']
    print "Vault name\tARN\tCreated\tSize"
    for vault in vault_list:
        print "%s\t%s\t%s\t%s" % (vault['VaultName'],
                                  vault['VaultARN'],
                                  vault['CreationDate'],
                                  vault['SizeInBytes'])

def mkvault(args):
    vault_name = args.vault
    region = args.region

    glacierconn = glaciercorecalls.GlacierConnection(args.aws_access_key, args.aws_secret_key, region=region)

    if check_vault_name(vault_name):
        response = glaciercorecalls.GlacierVault(glacierconn, vault_name).create_vault()
        parse_response(response)
        print response.getheader("Location")

def rmvault(args):
    vault_name = args.vault
    region = args.region

    glacierconn = glaciercorecalls.GlacierConnection(args.aws_access_key, args.aws_secret_key, region=region)

    if check_vault_name(vault_name):
        response = glaciercorecalls.GlacierVault(glacierconn, vault_name).delete_vault()
        parse_response(response)

def listjobs(args):
    vault_name = args.vault
    region = args.region

    glacierconn = glaciercorecalls.GlacierConnection(args.aws_access_key, args.aws_secret_key, region=region)

    gv = glaciercorecalls.GlacierVault(glacierconn, name=vault_name)
    response = gv.list_jobs()
    parse_response(response)
    print "Action\tArchive ID\tStatus\tInitiated\tVaultARN\tJob ID"
    for job in gv.job_list:
        print "%s\t%s\t%s\t%s\t%s\t%s" % (job['Action'],
                                          job['ArchiveId'],
                                          job['StatusCode'],
                                          job['CreationDate'],
                                          job['VaultARN'],
                                          job['JobId'])

def describejob(args):
    job = args.jobid
    region = args.region
    glacierconn = glaciercorecalls.GlacierConnection(args.aws_access_key, args.aws_secret_key, region=region)

    gv = glaciercorecalls.GlacierVault(glacierconn, job_id)
    gj = glaciercorecalls.GlacierJob(gv, job_id=job)
    gj.job_status()
    print "Archive ID: %s\nJob ID: %s\nCreated: %s\nStatus: %s\n" % (gj.archive_id,
                                                                     job, gj.created,
                                                                     gj.status_code)

def putarchive(args):
    region = args.region
    vault = args.vault
    filename = args.filename
    description = args.description

    glacierconn = glaciercorecalls.GlacierConnection(args.aws_access_key, args.aws_secret_key, region=region)

    if BOOKKEEPING:
        sdb_conn = boto.connect_sdb(aws_access_key_id=args.aws_access_key,
                                    aws_secret_access_key=args.aws_secret_key)
        domain_name = BOOKKEEPING_DOMAIN_NAME
        try:
            domain = sdb_conn.get_domain(domain_name, validate=True)
        except boto.exception.SDBResponseError:
            domain = sdb_conn.create_domain(domain_name)

    if description:
        description = " ".join(description)
    else:
        description = filename

    if check_description(description):
        reader = None
        writer = glaciercorecalls.GlacierWriter(glacierconn, vault, description=description)

        #if we have data on stdin, use that
        if select.select([sys.stdin,],[],[],0.0)[0]:
            reader = sys.stdin
        else:
            reader = open(filename, "rb")

        #Read file in chunks so we don't fill whole memory
        for part in iter((lambda:reader.read(READ_PART_SIZE)), ''):
            writer.write(part)
        writer.close()

        archive_id = writer.get_archive_id()
        location = writer.get_location()
        sha256hash = writer.get_hash()
        if BOOKKEEPING:
            file_attrs = {
                'region':region,
                'vault':vault,
                'filename':filename,
                'archive_id': archive_id,
                'location':location,
                'description':description,
                'date':'%s' % datetime.datetime.utcnow().replace(tzinfo=pytz.utc),
                'hash':sha256hash
            }

            domain.put_attributes(filename, file_attrs)
        print "Created archive with ID: ", archive_id

def getarchive(args):
    region = args.region
    vault = args.vault
    archive = args.archive
    filename = args.filename

    glacierconn = glaciercorecalls.GlacierConnection(args.aws_access_key, args.aws_secret_key, region=region)
    gv = glaciercorecalls.GlacierVault(glacierconn, vault)
    
    jobs = gv.list_jobs()
    found = False
    for job in gv.job_list:
        if job['ArchiveId'] == archive:
            found = True
            # no need to start another archive retrieval
            if filename or not job['Completed']:
                print "ArchiveId: ", archive
            if job['Completed']:
                job2 = glaciercorecalls.GlacierJob(gv, job_id=job['JobId'])
                if filename:
                    ffile = open(filename, "w")
                    ffile.write(job2.get_output().read())
                    ffile.close()
                else:
                    print job2.get_output().read()
                return
    if not found:
        job = gv.retrieve_archive(archive)
        print "Started"

def download(args):
    region = args.region
    vault = args.vault
    filename = args.filename
    out_file = args.out_file

    if not filename:
        raise Exception(u"You have to pass in the file name or the search term \
                          of it's description to search through archive.")

    args.search_term = filename
    items = search(args, print_results=False)

    n_items = 0
    if not items:
        print "Sorry, didn't find anything."
        return False

    print "Region\tVault\tFilename\tArchive ID"
    for item in items:
        n_items += 1
        archive = item['archive_id']
        vault = item['vault']
        print "%s\t%s\t%s\t%s" % (item['region'],
                                  item['vault'],
                                  item['filename'],
                                  item['archive_id'])

    if n_items > 1:
        print "You need to uniquely identify file with either region, vault or \
               filename parameters. If that is not enough, use getarchive to \
               specify exactly which archive you want."
        return False

    glacierconn = glaciercorecalls.GlacierConnection(args.aws_access_key, args.aws_secret_key, region=region)
    gv = glaciercorecalls.GlacierVault(glacierconn, vault)

    jobs = gv.list_jobs()
    found = False
    for job in gv.job_list:
        if job['ArchiveId'] == archive:
            found = True
            # no need to start another archive retrieval
            if not job['Completed']:
                print "Waiting for Amazon Glacier to assamble the archive."
            if job['Completed']:
                job2 = glaciercorecalls.GlacierJob(gv, job_id=job['JobId'])
                if out_file:
                    ffile = open(out_file, "w")
                    ffile.write(job2.get_output().read())
                    ffile.close()
                else:
                    print job2.get_output().read()
            return True
    if not found:
        job = gv.retrieve_archive(archive)
        print "Started"

def deletearchive(args):
    region = args.region
    vault = args.vault
    archive = args.archive

    if BOOKKEEPING:
        sdb_conn = boto.connect_sdb(aws_access_key_id=args.aws_access_key,
                                    aws_secret_access_key=args.aws_secret_key)
        domain_name = BOOKKEEPING_DOMAIN_NAME
        try:
            domain = sdb_conn.get_domain(domain_name, validate=True)
        except boto.exception.SDBResponseError:
            domain = sdb_conn.create_domain(domain_name)

    glacierconn = glaciercorecalls.GlacierConnection(args.aws_access_key, args.aws_secret_key, region=region)
    gv = glaciercorecalls.GlacierVault(glacierconn, vault)

    print gv.delete_archive(archive)

    # TODO: can't find a method for counting right now
    query = 'select * from `%s` where archive_id="%s"' % (BOOKKEEPING_DOMAIN_NAME, archive)
    items = domain.select(query)
    item = items.next()
    domain.delete_item(item)

def search(args, print_results=True):
    region = args.region
    vault = args.vault
    search_term = args.search_term

    if BOOKKEEPING:
        sdb_conn = boto.connect_sdb(aws_access_key_id=args.aws_access_key,
                                    aws_secret_access_key=args.aws_secret_key)
        domain_name = BOOKKEEPING_DOMAIN_NAME
        try:
            domain = sdb_conn.get_domain(domain_name, validate=True)
        except boto.exception.SDBResponseError:
            domain = sdb_conn.create_domain(domain_name)
    else:
        raise Exception(u"You have to enable bookkeeping in your settings \
                          before you can perform search.")

    search_params = []
    table_title = ""
    if region:
        search_params += ["region='%s'" % (region,)]
    else:
        table_title += "Region\t"

    if vault:
        search_params += ["vault='%s'" % (vault,)]
    else:
        table_title += "Vault\t"

    table_title += "Filename\tArchive ID"

    search_params += ["(filename like '"+ search_term+"%' or description like '"+search_term+"%')" ]
    search_params = " and ".join(search_params)

    query = 'select * from `%s` where %s' % (BOOKKEEPING_DOMAIN_NAME, search_params)
    items = domain.select(query)

    if print_results:
        print table_title

    for item in items:
        # print item, item.keys()
        item_attrs = []
        if not region:
            item_attrs += [item[u'region']]
        if not vault:
            item_attrs += [item[u'vault']]
        item_attrs += [item[u'filename']]
        item_attrs += [item[u'archive_id']]
        if print_results:
            print "\t".join(item_attrs)

    if not print_results:
        return items

def render_inventory(inventory):
    print "Inventory of vault %s" % (inventory["VaultARN"],)
    print "Inventory Date: %s\n" % (inventory['InventoryDate'],)
    print "Content:"
    print "Archive Description\tUploaded\tSize\tArchive ID\tSHA256 hash"
    for archive in inventory['ArchiveList']:
        print "%s\t%s\t%s\t%s\t%s" % (archive['ArchiveDescription'],
                                      archive['CreationDate'],
                                      archive['Size'],
                                      archive['ArchiveId'],
                                      archive['SHA256TreeHash'])

def inventory(args):
    region = args.region
    vault = args.vault
    force = args.force

    glacierconn = glaciercorecalls.GlacierConnection(args.aws_access_key, args.aws_secret_key, region=region)
    gv = glaciercorecalls.GlacierVault(glacierconn, vault)
    if force:
        job = gv.retrieve_inventory(format="JSON")
        return True
    try:
        gv.list_jobs()
        inventory_retrievals_done = []
        for job in gv.job_list:
            if job['Action'] == "InventoryRetrieval" and job['StatusCode'] == "Succeeded":
                d = dateutil.parser.parse(job['CompletionDate']).replace(tzinfo=pytz.utc)
                job['inventory_date'] = d
                inventory_retrievals_done += [job]

        if len(inventory_retrievals_done):
            sorted(inventory_retrievals_done, key=lambda i: i['inventory_date'], reverse=True)
            job = inventory_retrievals_done[0]
            job = glaciercorecalls.GlacierJob(gv, job_id=job['JobId'])
            inventory = json.loads(job.get_output().read())

            if BOOKKEEPING:
                sdb_conn = boto.connect_sdb(aws_access_key_id=args.aws_access_key,
                                            aws_secret_access_key=args.aws_secret_key)
                try:
                    domain = sdb_conn.get_domain(domain_name, validate=True)
                except boto.exception.SDBResponseError:
                    domain = sdb_conn.create_domain(domain_name)

                d = dateutil.parser.parse(inventory['InventoryDate']).replace(tzinfo=pytz.utc)
                item = domain.put_attributes("%s" % (d,), inventory)

            if ((datetime.datetime.utcnow().replace(tzinfo=pytz.utc) - d).days > 1):
                gv.retrieve_inventory(format="JSON")

            render_inventory(inventory)
        else:
            job = gv.retrieve_inventory(format="JSON")
    except Exception, e:
        print "exception: ", e
        print json.loads(e[1])['message']

def main():
    glacier_settings=None
    try:
        import glacier_settings
    except ImportError:
        pass

    AWS_ACCESS_KEY = getattr(glacier_settings, "AWS_ACCESS_KEY", None) \
                        or os.environ.get("AWS_ACCESS_KEY_ID")
    AWS_SECRET_KEY = getattr(glacier_settings, "AWS_SECRET_KEY", None) \
                        or os.environ.get("AWS_SECRET_ACCESS_KEY")
    DEFAULT_REGION = getattr(glacier_settings, "REGION", None) \
                        or os.environ.get("GLACIER_DEFAULT_REGION") \
                        or "us-east-1"
    BOOKKEEPING = getattr(glacier_settings, "BOOKKEEPING", None) \
                        or os.environ.get("GLACIER_BOOKKEEPING") \
                        or False
    BOOKKEEPING_DOMAIN_NAME = getattr(glacier_settings, "BOOKKEEPING_DOMAIN_NAME", None) \
                        or os.environ.get("GLACIER_BOOKKEEPING_DOMAIN_NAME") \
                        or "amazon-glacier"

    program_description = u"""
	Command line interface for Amazon Glacier
	-----------------------------------------

	Required libraries are glaciercorecalls (temporarily, while we wait for glacier 
	support to land in boto's develop branch) and boto - at the moment you still 
	need to use development branch of boto (which you can get by
	 running `pip install --upgrade git+https://github.com/boto/boto.git`).

	To install simply execute:

	    >>> python setup.py install

	To run:

	    >>> glacier

	There are a couple of options on how to pass in the credentials. One is to set 
	`AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` as environmental variables 
	(if you're using `boto` already, this is the usual method of configuration).

	While you can pass in your AWS Access and Secret key (`--aws-access-key` and `--aws-secret-key`), 
	it is recommended that you create `glacier_settings.py` file into which you put
	`AWS_ACCESS_KEY` and `AWS_SECRET_KEY` strings. You can also set these settings
	by exporting environemnt variables using `export AWS_ACCESS_KEY_ID=key` and
	`export AWS_SECRET_ACCESS_KEY=key`.

	You can also put `REGION` into `glacier_settings.py` to specify the default region 
	on which you will operate (default is `us-east-1`). When you want to operate on 
	a non-default region you can pass in the `--region` settings to the commands.
	You can also specify this setting by exporting `export GLACIER_DEFAULT_REGION=region`.

	It is recommended that you enable `BOOKKEEPING` in `glacier_settings.py` to allow
	for saving cache information into Amazon SimpleDB database. Again you can also
	export `GLACIER_BOOKKEEPING` and `GLACIER_BOOKKEEPING_DOMAIN_NAME` as environemnt
	variables.

	You have two options to retrieve an archive - first one is `download`, 
	second one is `getarchive`.

	If you use `download`, you will have to uniquely identify the file either by 
	its file name, its description, or limit the search by region and vault. 
	If that is not enough you should use `getarchive` and specify the archive ID of
	the archive you want to retrieve.
    """

    parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter,
                                    description=program_description)
    subparsers = parser.add_subparsers()

    help_msg_access_secret_key = u"Required if you haven't created glacier_settings.py \
                                file with AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY in it. \
                                Command line keys will override keys set in glacier_settings.py."
    parser.add_argument('--aws-access-key', required=not AWS_ACCESS_KEY,
                        default=AWS_ACCESS_KEY, help=help_msg_access_secret_key)
    parser.add_argument('--aws-secret-key', required=not AWS_SECRET_KEY,
                        default=AWS_SECRET_KEY, help=help_msg_access_secret_key)
    parser_lsvault = subparsers.add_parser("lsvault", help="List vaults")
    parser_lsvault.add_argument('--region', default=DEFAULT_REGION)
    parser_lsvault.set_defaults(func=lsvault)

    parser_mkvault = subparsers.add_parser("mkvault", help="Create a new vault")
    parser_mkvault.add_argument('vault')
    parser_mkvault.add_argument('--region', default=DEFAULT_REGION)
    parser_mkvault.set_defaults(func=mkvault)

    parser_rmvault = subparsers.add_parser('rmvault', help='Remove vault')
    parser_rmvault.add_argument('--region', default=DEFAULT_REGION)
    parser_rmvault.add_argument('vault')
    parser_rmvault.set_defaults(func=rmvault)

    parser_listjobs = subparsers.add_parser('listjobs', help='List jobs')
    parser_listjobs.add_argument('--region', default=DEFAULT_REGION)
    parser_listjobs.add_argument('vault')
    parser_listjobs.set_defaults(func=listjobs)

    parser_describejob = subparsers.add_parser('describejob', help='Describe job')
    parser_describejob.add_argument('--region', default=DEFAULT_REGION)
    parser_describejob.add_argument('vault')
    parser_describejob.add_argument('jobid')
    parser_describejob.set_defaults(func=describejob)

    parser_upload = subparsers.add_parser('upload', help='Upload an archive')
    parser_upload.add_argument('--region', default=DEFAULT_REGION)
    parser_upload.add_argument('vault')
    parser_upload.add_argument('filename')
    parser_upload.add_argument('description', nargs='*')
    parser_upload.set_defaults(func=putarchive)

    parser_getarchive = subparsers.add_parser('getarchive',
                help='Get a file by explicitly setting archive id.')
    parser_getarchive.add_argument('--region', default=DEFAULT_REGION)
    parser_getarchive.add_argument('vault')
    parser_getarchive.add_argument('archive')
    parser_getarchive.add_argument('filename', nargs='?')
    parser_getarchive.set_defaults(func=getarchive)

    if BOOKKEEPING:
        parser_download = subparsers.add_parser('download',
                help='Download a file by searching through SimpleDB cache for it.')
        parser_download.add_argument('--region', default=DEFAULT_REGION)
        parser_download.add_argument('--vault',
                help="Specify the vault in which archive is located.")
        parser_download.add_argument('--out-file')
        parser_download.add_argument('filename', nargs='?')
        parser_download.set_defaults(func=download)

    parser_rmarchive = subparsers.add_parser('rmarchive', help='Remove archive')
    parser_rmarchive.add_argument('--region', default=DEFAULT_REGION)
    parser_rmarchive.add_argument('vault')
    parser_rmarchive.add_argument('archive')
    parser_rmarchive.set_defaults(func=deletearchive)

    parser_search = subparsers.add_parser('search',
                help='Search SimpleDB database (if it was created)')
    parser_search.add_argument('--region')
    parser_search.add_argument('--vault')
    parser_search.add_argument('search_term')
    parser_search.set_defaults(func=search)

    parser_inventory = subparsers.add_parser('inventory',
                help='List inventory of a vault')
    parser_inventory.add_argument('--region', default=DEFAULT_REGION)
    parser_inventory.add_argument('--force')
    parser_inventory.add_argument('vault')
    parser_inventory.set_defaults(func=inventory)

    args = parser.parse_args(sys.argv[1:])

    if args.aws_access_key and args.aws_secret_key:
        args.aws_access_key = AWS_ACCESS_KEY
        args.aws_secret_key = AWS_SECRET_KEY

    args.func(args)

if __name__ == "__main__":
    main()
