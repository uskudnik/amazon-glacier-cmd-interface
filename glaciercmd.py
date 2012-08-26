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

try:
	import glacier_settings
	AWS_ACCESS_KEY = glacier_settings.AWS_ACCESS_KEY
	AWS_SECRET_KEY = glacier_settings.AWS_SECRET_KEY
	AWS_KEYS_FROM_CLI = False
except ImportError:
	AWS_KEYS_FROM_CLI = True

parser = argparse.ArgumentParser(description=u'Command line access to Amazon glacier')
parser.add_argument('--aws-access-key', required=AWS_KEYS_FROM_CLI)
parser.add_argument('--aws-secret-key', required=AWS_KEYS_FROM_CLI)

parser.add_argument('lsvault', nargs='*')
parser.add_argument('mkvault', nargs='+')
parser.add_argument('--remove-vault', nargs='*')

parser.add_argument('--vault', nargs=1)
parser.add_argument('--list-jobs', action='store_true')
parser.add_argument('--describe-job', nargs='*')

parser.add_argument('--put-archive', nargs='+')
parser.add_argument('--get-archive', nargs=1)	
parser.add_argument('--delete-archive', nargs=1)
parser.add_argument('--get-inventar', action='store_true')

parser.add_argument('--region', nargs=1)

args = parser.parse_args(sys.argv[1:])

if AWS_KEYS_FROM_CLI:
	AWS_ACCESS_KEY = args.aws_access_key
	AWS_SECRET_KEY = args.aws_secret_key

if args.region:
	region = args.region[0]
else:
	try:
		region = glacier_settings.REGION
	except AttributeError:
		region = "us-east-1"

glacierconn = glacier.GlacierConnection(AWS_ACCESS_KEY, AWS_SECRET_KEY, region=region)

def parse_response(response):
	if response.status == 403:
		print "403 Forbidden."
		print "\n"
		print "Reason:"
		print response.read()
		print response.msg
	print response.status, response.reason

if args.mkvault:
	mkv = args.mkvault
	print mkv
	if len(mkv) > 1:
		region = mkv[0]
		vault_name = mkv[1]
		glacierconn = glacier.GlacierConnection(AWS_ACCESS_KEY, AWS_SECRET_KEY, region=region)
	else:
		vault_name = mkv[0]
	
	if check_vault_name(vault_name):
		response = glacier.GlacierVault(glacierconn, vault_name).create_vault()
		parse_response(response)
		print response.getheader("Location")
			
if args.remove_vault:
	vaults = args.remove_vault
	for vault_name in vaults:
		if check_vault_name(vault_name):
			response = glacier.GlacierVault(glacierconn, vault_name).delete_vault()
			parse_response(response)

if args.lsvault:
	lsv = args.lsvault
	
	if len(lsv) > 1:
		region = lsv[1]
		glacierconn = glacier.GlacierConnection(AWS_ACCESS_KEY, AWS_SECRET_KEY, region=region)
	
	response = glacierconn.list_vaults()
	parse_response(response)
	jdata = json.loads(response.read())
	vault_list = jdata['VaultList']
	print "Vault name\tARN\tCreated\tSize"
	for vault in vault_list:
		print "%s\t%s\t%s\t%s" % (vault['VaultName'], vault['VaultARN'], vault['CreationDate'], vault['SizeInBytes'])

if args.list_jobs or args.describe_job or args.put_archive or args.get_archive or args.delete_archive or args.get_inventar:
	if not args.vault:
		raise Exception("If you execute put, get or delete operations, you need to specify which vault you are operating on.")

if args.list_jobs:
	gv = glacier.GlacierVault(glacierconn, args.vault[0])
	response = gv.list_jobs()
	parse_response(response)
	print "Action\tArchive ID\tStatus\tInitiated\tVaultARN\tJob ID"
	for job in gv.job_list:
		print "%s\t%s\t%s\t%s\t%s\t%s" % (job['Action'], job['ArchiveId'], job['StatusCode'], job['CreationDate'], job['VaultARN'], job['JobId'])

if args.describe_job:
	jobs = args.describe_job
	for job in jobs:
		gv = glacier.GlacierVault(glacierconn, args.vault[0])
		gj = glacier.GlacierJob(gv, job_id=job)
		gj.job_status()
		print "Archive ID: %s\nJob ID: %s\nCreated: %s\nStatus: %s\n" % (gj.archive_id, job, gj.created, gj.status_code)

if args.put_archive:
	put_archive = args.put_archive
	ffile = put_archive[0]
	if len(put_archive) > 1:
		description = " ".join(put_archive[1:])
	else:
		description = ffile
	
	if check_description(description):
		writer = glacier.GlacierWriter(glacierconn, args.vault[0], description=description)
		ffile = open(ffile, "rb")
		writer.write(ffile.read())
		writer.close()
		print "Created archive with ID: ", writer.get_archive_id()

if args.get_archive:
	archive = args.get_archive[0]
	gv = glacier.GlacierVault(glacierconn, args.vault[0])
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

if args.get_inventar:
	gv = glacier.GlacierVault(glacierconn, args.vault[0])
	try:
		job = gv.retrieve_inventar()
		gv.list_jobs()
		for job in gv.job_list:
			if job['Action'] == "InventoryRetrieval":
				if job['Completed']:
					job = glacier.GlacierJob(gv, job['JobId'])
					print "Output: ", job.get_output()
				else:
					print "Status: ", job['StatusCode']
			else:
				job = gv.retrieve_inventar(format="JSON")
	except Exception, e:
		print json.loads(e[1])['message']
		
if args.delete_archive:
	archive = args.delete_archive[0]
	gv = glacier.GlacierVault(glacierconn, args.vault[0])
	print gv.delete_archive(archive)