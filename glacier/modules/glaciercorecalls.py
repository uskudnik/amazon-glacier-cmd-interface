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

from modules import constants

import boto.glacier.layer1

from glacierexception import *

# Placeholder, effectively renaming the class.
class GlacierConnection(boto.glacier.layer1.Layer1):

    pass


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

    def __init__(self, connection, vault_name,
                 description=None, part_size_in_bytes=constants.DEFAULT_PART_SIZE*1024*1024,
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
                "Tried to write to a GlacierWriter that is already closed.",
                code='InternalError')

        if len(data) > self.part_size:
            raise InputException (
                'Block of data provided must be equal to or smaller than the set block size.',
                code='InternalError')

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

        response = self.connection.upload_part(self.vault_name,
                                    self.uploadid,
                                    hashlib.sha256(data).hexdigest(),
                                    bytes_to_hex(part_tree_hash),
                                    (self.uploaded_size, self.uploaded_size+len(data)-1),
                                    data)
        response.read()

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
