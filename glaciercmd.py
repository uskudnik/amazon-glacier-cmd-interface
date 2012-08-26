#!/usr/bin/env python
# encoding: utf-8
"""
glaciercmd.py

mkvault, rmvault, inventory, put, get, delete

Created by  on 2012-08-24.
Copyright (c) 2012 __MyCompanyName__. All rights reserved.
"""

import sys
import os
import argparse
import re
import json

import boto
import glacier

MAX_VAULT_NAME_LENGTH = 255
VAULT_NAME_ALLOWED_CHARACTERS = "[a-zA-Z\.\-\_0-9]+"

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
	AWS_ACCESS_KEY = glacier_settings.AWS_ACCESS_KEY
	AWS_SECRET_KEY = glacier_settings.AWS_SECRET_KEY
	AWS_KEYS_FROM_CLI = False
	
	try:
		default_region = glacier_settings.REGION
	except AttributeError:
		default_region = "us-east-1"
	
except ImportError:
	AWS_KEYS_FROM_CLI = True


def lsvault(args):
	region = args.region
	glacierconn = glacier.GlacierConnection(AWS_ACCESS_KEY, AWS_SECRET_KEY, region=default_region)

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
	
	glacierconn = glacier.GlacierConnection(AWS_ACCESS_KEY, AWS_SECRET_KEY, region=default_region)
	
	if check_vault_name(vault_name):
		response = glacier.GlacierVault(glacierconn, vault_name).create_vault()
		parse_response(response)
		print response.getheader("Location")

def rmvault(args):
	vault_name = args.vault
	region = args.region
	
	glacierconn = glacier.GlacierConnection(AWS_ACCESS_KEY, AWS_SECRET_KEY, region=default_region)
	
	if check_vault_name(vault_name):
		response = glacier.GlacierVault(glacierconn, vault_name).delete_vault()
		parse_response(response)

def listjobs(args):
	vault_name = args.vault
	region = args.region
	
	glacierconn = glacier.GlacierConnection(AWS_ACCESS_KEY, AWS_SECRET_KEY, region=default_region)
	
	gv = glacier.GlacierVault(glacierconn, name=vault_name)
	response = gv.list_jobs()
	parse_response(response)
	print "Action\tArchive ID\tStatus\tInitiated\tVaultARN\tJob ID"
	for job in gv.job_list:
		print "%s\t%s\t%s\t%s\t%s\t%s" % (job['Action'], job['ArchiveId'], job['StatusCode'], job['CreationDate'], job['VaultARN'], job['JobId'])

def describejob(args):
	job = args.jobid
	region = args.region
	glacierconn = glacier.GlacierConnection(AWS_ACCESS_KEY, AWS_SECRET_KEY, region=default_region)
	
	gv = glacier.GlacierVault(glacierconn, job_id)
	gj = glacier.GlacierJob(gv, job_id=job)
	gj.job_status()
	print "Archive ID: %s\nJob ID: %s\nCreated: %s\nStatus: %s\n" % (gj.archive_id, job, gj.created, gj.status_code)

def putarchive(args):
	region = args.region
	vault = args.vault
	filename = args.filename
	description = args.description
	
	glacierconn = glacier.GlacierConnection(AWS_ACCESS_KEY, AWS_SECRET_KEY, region=default_region)
	
	if description:
		description = " ".join(description)
	else:
		description = filename
	
	if check_description(description):
		writer = glacier.GlacierWriter(glacierconn, vault, description=description)
		ffile = open(filename, "rb")
		writer.write(ffile.read())
		writer.close()
		print "Created archive with ID: ", writer.get_archive_id()

def getarchive(args):
	region = args.region
	vault = args.vault
	archive = args.archive
	
	glacierconn = glacier.GlacierConnection(AWS_ACCESS_KEY, AWS_SECRET_KEY, region=default_region)
	gv = glacier.GlacierVault(glacierconn, vault)
	
	jobs = gv.list_jobs()
	for job in gv.job_list:
		if job['ArchiveId'] == archive:
			# no need to start another archive retrieval
			print "ArchiveId: ", archive
			if job['Completed']:
				job2 = glacier.GlacierJob(gv, job_id=job['JobId'])
				print "Output: ", job2.get_output().read()
			else:
				print "Status: ", job['StatusCode']
		else:
			job = gv.retrieve_archive(archive)

def deletearchive(args):
	region = args.region
	vault = args.vault
	archive = args.archive
	
	glacierconn = glacier.GlacierConnection(AWS_ACCESS_KEY, AWS_SECRET_KEY, region=default_region)
	gv = glacier.GlacierVault(glacierconn, vault)
	print gv.delete_archive(archive)

def inventar(args):
	region = args.region
	vault=args.vault
	
	glacierconn = glacier.GlacierConnection(AWS_ACCESS_KEY, AWS_SECRET_KEY, region=default_region)
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
						print "%s\t%s\t%s\t%s" % (archive['ArchiveDescription'], archive['CreationDate'], archive['Size'], archive['ArchiveId'])
					break
		
		job = gv.retrieve_inventar(format="JSON")
	except Exception, e:
		print "exception: ", e
		print json.loads(e[1])['message']

parser = argparse.ArgumentParser(description=u'Command line access to Amazon glacier')
subparsers = parser.add_subparsers()

parser.add_argument('--aws-access-key', required=AWS_KEYS_FROM_CLI)
parser.add_argument('--aws-secret-key', required=AWS_KEYS_FROM_CLI)
	
parser_lsvault = subparsers.add_parser("lsvault", help="List vaults")
parser_lsvault.add_argument('--region', default='us-east-1')
parser_lsvault.set_defaults(func=lsvault)

parser_mkvault = subparsers.add_parser("mkvault", help="Make vault")
parser_mkvault.add_argument('vault')
parser_mkvault.add_argument('--region', default='us-east-1')
parser_mkvault.set_defaults(func=mkvault)

parser_rmvault = subparsers.add_parser('rmvault', help='Remove vault')
parser_rmvault.add_argument('--region', default=default_region)
parser_rmvault.add_argument('vault')
parser_rmvault.set_defaults(func=rmvault)

parser_listjobs = subparsers.add_parser('listjobs', help='List jobs')
parser_listjobs.add_argument('--region', default=default_region)
parser_listjobs.add_argument('vault')
parser_listjobs.set_defaults(func=listjobs)

parser_describejob = subparsers.add_parser('describejob', help='Describe job')
parser_describejob.add_argument('--region', default=default_region)
parser_describejob.add_argument('vault')
parser_describejob.set_defaults(func=describejob)

parser_upload = subparsers.add_parser('upload', help='Upload file')
parser_upload.add_argument('--region', default=default_region)
parser_upload.add_argument('vault')
parser_upload.add_argument('filename')
parser_upload.add_argument('description', nargs='*')
parser_upload.set_defaults(func=putarchive)

parser_download = subparsers.add_parser('download', help='Download file')
parser_download.add_argument('--region', default=default_region)
parser_download.add_argument('vault')
parser_download.add_argument('archive')
parser_download.set_defaults(func=getarchive)

parser_rmarchive = subparsers.add_parser('rmarchive', help='Remove archive')
parser_rmarchive.add_argument('--region', default=default_region)
parser_rmarchive.add_argument('vault')
parser_rmarchive.add_argument('archive')
parser_rmarchive.set_defaults(func=deletearchive)

parser_inventar = subparsers.add_parser('inventar', help='List inventar of a vault')
parser_inventar.add_argument('--region', default=default_region)
parser_inventar.add_argument('vault')
parser_inventar.set_defaults(func=inventar)

args = parser.parse_args(sys.argv[1:])
args.func(args)

if AWS_KEYS_FROM_CLI:
	AWS_ACCESS_KEY = args.aws_access_key
	AWS_SECRET_KEY = args.aws_secret_key
