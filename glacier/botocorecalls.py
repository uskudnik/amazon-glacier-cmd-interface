#!/usr/bin/env python
# encoding: utf-8
"""
.. module:: botocorecalls
   :platform: Unix, Windows
   :synopsis: boto calls to access Amazon Glacier.
   
This depends on the boto library, use version 2.6.0 or newer.

     
     writer = GlacierWriter(glacierconn, GLACIER_VAULT)
     writer.write(block of data)
     writer.close()
     # Get the id of the newly created archive
     archive_id = writer.get_archive_id()from boto.connection import AWSAuthConnection
"""

import urllib
import hashlib
import math
import json
import sys
import time

import boto.glacier.layer1

##from boto.connection import AWSAuthConnection
from glacierexception import *

# Placeholder, effectively renaming the class.
class GlacierConnection(boto.glacier.layer1.Layer1):

    pass

    
class GlacierJob(object):
    def __init__(self, vault, params=None, job_id=None):
        self.vault = vault
        self.params = params
        self.job_id = job_id

    def initiate(self):
        headers = {
                    "x-amz-glacier-version": "2012-06-01",
                  }
        response = self.vault.make_request("POST", "/jobs", headers, json.dumps(self.params))
        if response.status != 202:
            resp = json.loads(response.read())
            raise ResponseException(
                "Initiating job expected response status 202 (got %s):\n%s"\
                    % (response.status, response.read()),
                cause=resp['message'],
                code=resp['code'])

##        response.read()
        self.job_id = response.getheader("x-amz-job-id")
        self.location = response.getheader("Location")

    def get_output(self, range_from=None, range_to=None):
        headers = {}
        if range_from is not None or range_to is not None:
            if range_from is None or range_to is None:
                raise InputException (
                    "If you specify one of range_from or range_to you must specify the other.")

            headers["Range"] = "bytes %d-%d" % (range_from, range_to)
        return self.vault.make_request("GET", "/jobs/%s/output" % (self.job_id,))

    def job_status(self):
        response = self.vault.make_request("GET", "/jobs/%s" % (self.job_id,))
        return self.vault.make_request("GET", "/jobs/%s" % (self.job_id,))

def chunk_hashes(data):
    """
    Break up the byte-string into 1MB chunks and return sha256 hashes
    for each.
    """
    chunk = 1024*1024
    chunk_count = int(math.ceil(len(data)/float(chunk)))
    return [hashlib.sha256(data[i*chunk:(i+1)*chunk]).digest() for i in range(chunk_count)]

def tree_hash(fo):
    """
    Given a hash of each 1MB chunk (from chunk_hashes) this will hash
    together adjacent hashes until it ends up with one big one. So a
    tree of hashes.
    """
    hashes = []
    hashes.extend(fo)
    while len(hashes) > 1:
        new_hashes = []
        while True:
            if len(hashes) > 1:
                first = hashes.pop(0)
                second = hashes.pop(0)
                new_hashes.append(hashlib.sha256(first + second).digest())
            elif len(hashes) == 1:
                only = hashes.pop(0)
                new_hashes.append(only)
            else:
                break
        hashes.extend(new_hashes)
    return hashes[0]

def bytes_to_hex(str):
    return ''.join( [ "%02x" % ord( x ) for x in str] ).strip()

class GlacierWriter(object):
    """
    Presents a file-like object for writing to a Amazon Glacier
    Archive. The data is written using the multi-part upload API.
    """
    DEFAULT_PART_SIZE = 128 # in MB
    
    def __init__(self, connection, vault_name,
                 description=None, part_size_in_bytes=DEFAULT_PART_SIZE*1024*1024,
                 uploadid=None, logger=None):

        self.part_size = part_size_in_bytes
        self.vault_name = vault_name
        self.connection = connection
##        self.location = None
        self.logger = logger

        if uploadid:
            self.uploadid = uploadid
        else:
            response = self.connection.initiate_multipart_upload(self.vault_name,
                                                                 self.part_size,
                                                                 description)
            self.uploadid = response['UploadId']

        self.uploaded_size = 0
        self.tree_hashes = []
        self.closed = False
##        self.upload_url = response.getheader("location")

    def write(self, data):
        
        if self.closed:
            raise CommunicationError(
                "Tried to write to a GlacierWriter that is already closed.")

        if len(data) > self.part_size:
            raise InputException (
                'Block of data provided must be equal to or smaller than the set block size.')
        
        part_tree_hash = tree_hash(chunk_hashes(data))
        self.tree_hashes.append(part_tree_hash)
        headers = {
                   "x-amz-glacier-version": "2012-06-01",
                    "Content-Range": "bytes %d-%d/*" % (self.uploaded_size,
                                                       (self.uploaded_size+len(data))-1),
                    "Content-Length": str(len(data)),
                    "Content-Type": "application/octet-stream",
                    "x-amz-sha256-tree-hash": bytes_to_hex(part_tree_hash),
                    "x-amz-content-sha256": hashlib.sha256(data).hexdigest()
                  }
        
        self.connection.upload_part(self.vault_name,
                                    self.uploadid,
                                    hashlib.sha256(data).hexdigest(),
                                    bytes_to_hex(part_tree_hash),
                                    (self.uploaded_size, self.uploaded_size+len(data)-1),
                                    data)

##        retries = 0
##        while True:
##            response = self.connection.make_request(
##                "PUT",
##                self.upload_url,
##                headers,
##                data)
##
##            # Success.
##            if response.status == 204:
##                break
##
##            # Time-out recieved: sleep for 5 minutes and try again.
##            # Do not try more than five times; after that it's over.
##            elif response.status == 408:
##                if retries >= 5:
##                    resp = json.loads(response.read())
##                    raise ResonseException(
##                        resp['message'],
##                        cause='Timeout',
##                        code=resp['code'])
##                        
##                if self.logger:
##                    logger.warning(resp['message'])
##                    logger.warning('sleeping 300 seconds (5 minutes) before retrying.')
##                    
##                retries += 1
##                time.sleep(300)
##
##            else:
##                raise ResponseException(
##                    "Multipart upload part expected response status 204 (got %s):\n%s"\
##                        % (response.status, response.read()),
##                    cause=resp['message'],
##                    code=resp['code'])

##        response.read()
        self.uploaded_size += len(data)

    def close(self):
        
        if self.closed:
            return
            
        # Complete the multiplart glacier upload
        response = self.connection.complete_multipart_upload(self.vault_name,
                                                             self.uploadid,
                                                             bytes_to_hex(tree_hash(self.tree_hashes)),
                                                             self.uploaded_size)
        self.archive_id = response['ArchiveId']
        self.location = response['Location']
        self.hash_sha256 = bytes_to_hex(tree_hash(self.tree_hashes))
        self.closed = True

    def get_archive_id(self):
        self.close()
        return self.archive_id

    def get_location(self):
        self.close()
        return self.location

    def get_hash(self):
        self.close()
        return self.hash_sha256
