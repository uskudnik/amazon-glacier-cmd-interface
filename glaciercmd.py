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


parser = argparse.ArgumentParser(description=u'Command line access to Amazon glacier')
parser.add_argument('--aws-access-key', required=True)
parser.add_argument('--aws-secret-key', required=True)

parser.add_argument('--list_vaults')
parser.add_argument('--create-vault', nargs='*')
parser.add_argument('--remove-vault', nargs='*')

parser.add_argument('--vault', nargs=1)
parser.add_argument('--put-archive', nargs='*')
parser.add_argument('--get-archive', nargs='*')	
parser.add_argument('--delete-archive', nargs='*')
parser.add_argument('--get-inventar', nargs='*')

args = parser.parse_args(sys.argv[1:])

glacierconn = glacier.GlacierConnection(args.aws_access_key, args.aws_secret_key)

if args.create_vault:
	vaults = args.create_vault
	for vault_name in vaults:
		if check_vault_name(vault_name):
			glacier.GlacierVault(vault_name).create()

if args.remove_vault:
	vaults = args.remove_vault
	for vault_name in vaults:
		if check_vault_name(vault_name):
			glacier.GlacierVault(vault_name).delete()

if args.list_vaults:
	print glacier.list_vaults()

if args.put_archive or args.get_archive or args.delete_archive or args.get_inventar:
	if not args.vault:
		raise Exception("If you execute put, get or delete operations, you need to specify which vault you are operating on.")

if args.put_archive:
	files = args.put
	writer = glacier.GlacierWriter(glacierconn, args.vault)
	for ffile in files:
		ffile = open(ffile, "r")
		writer.write(ffile)
	writer.close()
	print "Created archive with ID: ", writer.get_archive_id()

if args.get_archive:
	archives = args.get_archive
	for archive in archives:
		gv = glacier.GlacierVault(glacierconn, args.vault)
		print gv.retrieve_archive(archive)
		
if args.get_inventar:
	inventars = args.get_inventar
	for inventar in inventars:
		gv = glacier.GlacierVault(glacierconn, args.vault)
		print gv.retrieve_inventar()
		
if args.delete_archive:
	archives = args.delete_archive
	for archive in archives:
		gv = glacier.GlacierVault(glacierconn, args.vault)
		print gv.delete_archive(archive)