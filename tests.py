#!/usr/bin/env python
# encoding: utf-8
import os
import unittest
import argparse
import subprocess

import glacier.glacier as glacier
import glacier as topglacier

glacier.BOOKKEEPING = True

class TestGlacier(unittest.TestCase):
    def setUp(self):

        self.access_key = os.environ.get("AWS_ACCESS_KEY_ID")
        self.secret_key = os.environ.get("AWS_ACCESS_SECRET_KEY")
        self.args = argparse.Namespace(
                                    aws_access_key=self.access_key, 
                                    aws_secret_key=self.secret_key,
                                    region='us-east-1',
                                    vault="test_vault",
                                    filename="loremipsum.txt")
    
    def tearDown(self):
        response = glacier.rmvault(self.args, print_results=False)
        self.assertIn("Vault removed.", response)
        if os.access(self.args.filename, os.F_OK):
            os.remove(self.args.filename)
    
    def mkvault(self):
        response = glacier.mkvault(self.args, print_results=False)
        return response
    
    def test_mkvault(self):
        response = self.mkvault()
        self.assertIn("/vaults/test_vault", response)
        
        lsv = self.lsvault()
        self.assertIn("test_vault", lsv)
    
    def lsvault(self):
        response = glacier.lsvault(self.args, print_results=False)
        return response
    
    def test_lsvault(self):
        response = self.lsvault()
        self.assertIn("Vault name", response)
        
    def mkfile(self):
        self.args.description = None
        ffile = open(self.args.filename, "w")
        ffile.write("lorem ipsum")
        ffile.close()
        
    def upload(self):
        return glacier.putarchive(self.args, print_results=False)
    
    def test_upload(self):
        self.mkfile()
        self.mkvault()
        
        archive_id = self.upload()
        self.assertRegexpMatches(archive_id, "[\w-]+")
    
    def test_search(self):
        self.mkfile()
        self.mkvault()
        self.upload()
        
        
        self.args.search_term = "lorem"
        items = glacier.search(self.args, print_results=False)
        response = " ".join(["%s %s" % (item['filename'], item['description']) for item in items])
        self.assertIn("lorem", response)
    
    def test_start_invtentory_retrieval(self):
        self.mkfile()
        self.mkvault()
        self.args.force = None
        archive_id = self.upload()
        
        response = glacier.inventory(self.args)
        self.assertRaises(Exception, response)
    
    def test_getarchive(self):
        self.mkfile()
        self.mkvault()
        archive_id = self.upload()
        self.args.archive = archive_id
        
        response = glacier.getarchive(self.args)
        self.assertIn("Started", response)
        
        response = glacier.listjobs(self.args, print_results=False)
        self.assertIn(archive_id, response)
        self.assertIn("ArchiveRetrieval", response)
    
if __name__ == "__main__":
    unittest.main()