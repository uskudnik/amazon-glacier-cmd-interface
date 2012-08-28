#!/usr/bin/env python
# encoding: utf-8
"""
glaciercmd.py

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
import argparse
import re
import json
import datetime

import boto
import glacier

MAX_VAULT_NAME_LENGTH = 255
VAULT_NAME_ALLOWED_CHARACTERS = "[a-zA-Z\.\-\_0-9]+"
BOOKKEEPING = False
BOOKKEEPING_DOMAIN_NAME = "amazon-glacier"

def check_vault_name(name):
	m = re.match(VAULT_NAME_ALLOWED_CHARACTERS, name)
	if len(name) > 255:
		raise Exception(u"Vault name can be at most 255 charecters long.")
	if len(name) == 0:
		raise Exception(u"Vault name has to be at least 1 character long.")
	if m.end() != len(name):
		raise Exception(u"Allowed characters are a–z, A–Z, 0–9, '_' (underscore), '-' (hyphen), and '.' (period)")	
	return True

MAX_DESCRIPTION_LENGTH = 1024

def check_description(description):
	if len(description) > 1024:
		raise Exception(u"Description must be less or equal to 1024 characters.")
	
	for char in description:
		n = ord(char)
		if n < 32 or n > 126:
			raise Exception(u"The allowable characters are 7-bit ASCII without control codes, specifically ASCII values 32—126 decimal or 0x20—0x7E hexadecimal.")
	return True

def parse_response(response):
	if response.status == 403:
		print "403 Forbidden."
		print "\n"
		print "Reason:"
		print response.read()
		print response.msg
	print response.status, response.reason

try:
	import glacier_settings
	
	try:
		AWS_ACCESS_KEY = glacier_settings.AWS_ACCESS_KEY
		AWS_SECRET_KEY = glacier_settings.AWS_SECRET_KEY
		AWS_KEYS_FROM_CLI = False
	except AttributeError:
		AWS_KEYS_FROM_CLI = True
	
	try:
		DEFAULT_REGION = glacier_settings.REGION
	except AttributeError:
		DEFAULT_REGION = "us-east-1"
	
	try:
		BOOKKEEPING = glacier_settings.BOOKKEEPING
	except AttributeError:
		pass
		
except ImportError:
	AWS_KEYS_FROM_CLI = True
	DEFAULT_REGION = "us-east-1"

def lsvault(args):
	region = args.region
	glacierconn = glacier.GlacierConnection(AWS_ACCESS_KEY, AWS_SECRET_KEY, region=region)

	response = glacierconn.list_vaults()
	parse_response(response)
	jdata = json.loads(response.read())
	vault_list = jdata['VaultList']
	print "Vault name\tARN\tCreated\tSize"
	for vault in vault_list:
		print "%s\t%s\t%s\t%s" % (vault['VaultName'], vault['VaultARN'], vault['CreationDate'], vault['SizeInBytes'])

def mkvault(args):
	vault_name = args.vault
	region = args.region
	
	glacierconn = glacier.GlacierConnection(AWS_ACCESS_KEY, AWS_SECRET_KEY, region=region)
	
	if check_vault_name(vault_name):
		response = glacier.GlacierVault(glacierconn, vault_name).create_vault()
		parse_response(response)
		print response.getheader("Location")

def rmvault(args):
	vault_name = args.vault
	region = args.region
	
	glacierconn = glacier.GlacierConnection(AWS_ACCESS_KEY, AWS_SECRET_KEY, region=region)
	
	if check_vault_name(vault_name):
		response = glacier.GlacierVault(glacierconn, vault_name).delete_vault()
		parse_response(response)

def listjobs(args):
	vault_name = args.vault
	region = args.region
	
	glacierconn = glacier.GlacierConnection(AWS_ACCESS_KEY, AWS_SECRET_KEY, region=region)
	
	gv = glacier.GlacierVault(glacierconn, name=vault_name)
	response = gv.list_jobs()
	parse_response(response)
	print "Action\tArchive ID\tStatus\tInitiated\tVaultARN\tJob ID"
	for job in gv.job_list:
		print "%s\t%s\t%s\t%s\t%s\t%s" % (job['Action'], job['ArchiveId'], job['StatusCode'], job['CreationDate'], job['VaultARN'], job['JobId'])

def describejob(args):
	job = args.jobid
	region = args.region
	glacierconn = glacier.GlacierConnection(AWS_ACCESS_KEY, AWS_SECRET_KEY, region=region)
	
	gv = glacier.GlacierVault(glacierconn, job_id)
	gj = glacier.GlacierJob(gv, job_id=job)
	gj.job_status()
	print "Archive ID: %s\nJob ID: %s\nCreated: %s\nStatus: %s\n" % (gj.archive_id, job, gj.created, gj.status_code)

def putarchive(args):
	region = args.region
	vault = args.vault
	filename = args.filename
	description = args.description
	
	glacierconn = glacier.GlacierConnection(AWS_ACCESS_KEY, AWS_SECRET_KEY, region=region)
	
	if BOOKKEEPING:
		sdb_conn = boto.connect_sdb(aws_access_key_id=AWS_ACCESS_KEY, aws_secret_access_key=AWS_SECRET_KEY)	
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
		writer = glacier.GlacierWriter(glacierconn, vault, description=description)
		ffile = open(filename, "rb")
		writer.write(ffile.read())
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
				'date':'%s' % datetime.datetime.now(),
				'hash':sha256hash
			}
		
			domain.put_attributes(filename, file_attrs)
		print "Created archive with ID: ", archive_id

def getarchive(args):
	region = args.region
	vault = args.vault
	archive = args.archive
	filename = args.filename
	
	glacierconn = glacier.GlacierConnection(AWS_ACCESS_KEY, AWS_SECRET_KEY, region=region)
	gv = glacier.GlacierVault(glacierconn, vault)
	
	jobs = gv.list_jobs()
	found = False
	for job in gv.job_list:
		if job['ArchiveId'] == archive:
			found = True
			# no need to start another archive retrieval
			if filename or not job['Completed']:
				print "ArchiveId: ", archive
			if job['Completed']:
				job2 = glacier.GlacierJob(gv, job_id=job['JobId'])
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

def deletearchive(args):
	region = args.region
	vault = args.vault
	archive = args.archive
	
	if BOOKKEEPING:
		sdb_conn = boto.connect_sdb(aws_access_key_id=AWS_ACCESS_KEY, aws_secret_access_key=AWS_SECRET_KEY)
		domain_name = BOOKKEEPING_DOMAIN_NAME
		try:
			domain = sdb_conn.get_domain(domain_name, validate=True)
		except boto.exception.SDBResponseError:
			domain = sdb_conn.create_domain(domain_name)
	
	glacierconn = glacier.GlacierConnection(AWS_ACCESS_KEY, AWS_SECRET_KEY, region=region)
	gv = glacier.GlacierVault(glacierconn, vault)
	
	print gv.delete_archive(archive)
	
	# TODO: can't find a method for counting right now 
	query = 'select * from `%s` where archive_id="%s"' % (BOOKKEEPING_DOMAIN_NAME, archive_id)
	items = domain.select(query)
	item = items.next()
	domain.delete_item(item)

def search(args):
	region = args.region
	vault = args.vault
	search_term = args.search_term
	
	if BOOKKEEPING:
		sdb_conn = boto.connect_sdb(aws_access_key_id=AWS_ACCESS_KEY, aws_secret_access_key=AWS_SECRET_KEY)
		domain_name = BOOKKEEPING_DOMAIN_NAME
		try:
			domain = sdb_conn.get_domain(domain_name, validate=True)
		except boto.exception.SDBResponseError:
			domain = sdb_conn.create_domain(domain_name)
	else:
		raise Exception(u"You have to enable bookkeeping in your settings before you can perform search.")
	
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
	
	search_params += ["filename='%s'" % (search_term,)]
	search_params = " and ".join(search_params)
	
	query = 'select * from `%s` where %s' % (BOOKKEEPING_DOMAIN_NAME, search_params)
	items = domain.select(query)
	
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
		print "\t".join(item_attrs)

def inventory(args):
	region = args.region
	vault=args.vault
	
	glacierconn = glacier.GlacierConnection(AWS_ACCESS_KEY, AWS_SECRET_KEY, region=region)
	gv = glacier.GlacierVault(glacierconn, vault)
	try:
		gv.list_jobs()
		for job in gv.job_list:
			if job['Action'] == "InventoryRetrieval":
				if job['StatusCode'] == "Succeeded":
					job2 = glacier.GlacierJob(gv, job_id=job['JobId'])
					inventary = json.loads(job2.get_output().read())
					
					print "Inventory of vault %s" % (inventary["VaultARN"],)
					print "Inventory Date: %s\n" % (inventary['InventoryDate'],)
					print "Content:"
					print "Archive Description\tUploaded\tSize\tArchive ID"
					for archive in inventary['ArchiveList']:
						print "%s\t%s\t%s\t%s\t%s" % (archive['ArchiveDescription'], archive['CreationDate'], archive['Size'], archive['ArchiveId'], archive['SHA256TreeHash'])
					break
		
		job = gv.retrieve_inventar(format="JSON")
	except Exception, e:
		print "exception: ", e
		print json.loads(e[1])['message']

program_description = u"""Command line interface for Amazon Glacier\n
\n
Required libraries are glacier (which is included into repository) and boto - at the moment you still need to use development branch of boto (which you can get by running "pip install --upgrade git+https://github.com/boto/boto.git").

While you can pass in your AWS Access and Secret key (--aws-access-key and --aws-secret-key), it is recommended that you create glacier_settings.py file into which you put AWS_ACCESS_KEY and AWS_SECRET_KEY strings.

You can also put REGION into glacier_settings.py to specify the default region on which you will operate (default is us-east-1). When you want to operate on a non-default region you can pass in the --region settings to the commands.
"""

parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter, description=program_description)
subparsers = parser.add_subparsers()


help_msg_access_secret_key = u"Required if you haven't created glacier_settings.py file with AWS_ACCESS_KEY and AWS_SECRET_KEY in it. Command line keys will override keys set in glacier_settings.py."
parser.add_argument('--aws-access-key', required=AWS_KEYS_FROM_CLI, help=help_msg_access_secret_key)
parser.add_argument('--aws-secret-key', required=AWS_KEYS_FROM_CLI, help=help_msg_access_secret_key)
	
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

parser_download = subparsers.add_parser('download', help='Download an archive')
parser_download.add_argument('--region', default=DEFAULT_REGION)
parser_download.add_argument('vault')
parser_download.add_argument('archive')
parser_download.add_argument('filename', nargs='?')
parser_download.set_defaults(func=getarchive)

parser_rmarchive = subparsers.add_parser('rmarchive', help='Remove archive')
parser_rmarchive.add_argument('--region', default=DEFAULT_REGION)
parser_rmarchive.add_argument('vault')
parser_rmarchive.add_argument('archive')
parser_rmarchive.set_defaults(func=deletearchive)

parser_search = subparsers.add_parser('search', help='Search SimpleDB database (if it was created)')
parser_search.add_argument('--region')
parser_search.add_argument('--vault')
parser_search.add_argument('search_term')
parser_search.set_defaults(func=search)

parser_inventory = subparsers.add_parser('inventory', help='List inventory of a vault')
parser_inventory.add_argument('--region', default=DEFAULT_REGION)
parser_inventory.add_argument('vault')
parser_inventory.set_defaults(func=inventory)

args = parser.parse_args(sys.argv[1:])

if args.aws_access_key and args.aws_secret_key:
	AWS_ACCESS_KEY = args.aws_access_key
	AWS_SECRET_KEY = args.aws_secret_key

args.func(args)
