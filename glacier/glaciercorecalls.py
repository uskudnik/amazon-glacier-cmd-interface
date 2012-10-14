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
import mmap

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

def upload_part_process(q, conn, aws_access_key, aws_secret_key, region,
                        file_name, vault_name, description,
                        part_size_in_bytes, uploadid, logger):
    """
    Starts the upload process of a chunk of data.
    """
    f = open(file_name, 'rb')
    try:
        logger.debug("""\
Connecting to Amazon Glacier for worker process with
    aws_access_key %s
    aws_secret_key %s
    region %s""",
                     aws_access_key,
                     aws_secret_key,
                     region)
        glacierconn = GlacierConnection(aws_access_key,
                                        aws_secret_key,
                                        region_name=region)
    except boto.exception.AWSConnectionError as e:
        raise ConnectionException(
            "Cannot connect to Amazon Glacier.",
            cause=e.cause,
            code="GlacierConnectionError")
    writer = GlacierWriter(glacierconn, vault_name, description=description,
                           part_size_in_bytes=part_size_in_bytes,
                           uploadid=uploadid, logger=logger)
    while True:
        item = q.get()
        if item is None: # detect sentinel
            q.task_done()
            break

        start, stop, part_nr = item
        part = mmap.mmap(fileno=f.fileno(),
                         length=stop-start,
                         offset=start,
                         access=mmap.ACCESS_READ)
        logger.debug('Got to work on range %s-%s'% (start, stop))
        writer.write(part, start=start)
        conn.send( (writer.part_tree_hash,
                    part_nr,
                    stop-start) )
        q.task_done()
    
    conn.close()
    
class GlacierWriter(object):
    """
    Presents a file-like object for writing to a Amazon Glacier
    Archive. The data is written using the multi-part upload API.
    """
    DEFAULT_PART_SIZE = 128 # in MB, power of 2.
    
    def __init__(self, connection, vault_name,
                 description=None, part_size_in_bytes=DEFAULT_PART_SIZE*1024*1024,
                 uploadid=None, logger=None):

        self.part_size = part_size_in_bytes
        self.vault_name = vault_name
        self.connection = connection
        self.location = None
        self.logger = logger

        if uploadid:
            self.uploadid = uploadid
        else:
            response = self.connection.initiate_multipart_upload(self.vault_name,
                                                                 self.part_size,
                                                                 description)
            self.uploadid = response['UploadId']
            response.read()

        self.uploaded_size = 0
        self.tree_hashes = []
        self.closed = False

    def write(self, data, start=None):
        if self.closed:
            raise CommunicationError(
                "Tried to write to a GlacierWriter that is already closed.",
                code='InternalError')

        if len(data) > self.part_size:
            raise InputException (
                'Block of data provided must be equal to or smaller than the set block size.',
                code='InternalError')
        
        self.part_tree_hash = tree_hash(chunk_hashes(data))
        self.tree_hashes.append(self.part_tree_hash)
        start = start if start else self.uploaded_size
        stop = start+len(data)-1
        if self.logger:
            self.logger.debug('Starting upload of part %s-%s.'% (start, stop))
        
        # Catch time-outs: if time-out received, wait a bit and
        # try again.
        # Uses exponential wait: 2 sec, 8 sec, 32 sec, 128 sec, 256 sec.
        # If still failure after five times retrying, give up and raise
        # an exception.
        retries = 0
        delay = 2
        while True:
            try:
                response = self.connection.upload_part(self.vault_name,
                                                       self.uploadid,
                                                       hashlib.sha256(data).hexdigest(),
                                                       bytes_to_hex(self.part_tree_hash),
                                                       (start, stop),
                                                       data)
                break
            
            except boto.glacier.exceptions.UnexpectedHTTPResponseError as e:
                if e.code != 408:
                    raise ResponseException(
                        "Error while uploading data to Amazon Glacier.",
                        cause=e,
                        code=e.code)
                
                if retries >= 5:
                    raise ResonseException(
                        "Timeout while uploading data to Amazon Glacier. Retried five times; giving up.",
                        cause=e,
                        code=e.code)
                        
                if self.logger:
                    logger.warning(e.message)
                    logger.warning('sleeping %s seconds before retrying.'% delay)
                    
                time.sleep(delay)
                retries += 1
                delay = delay * 4

        response.read()
        self.uploaded_size += len(data)
        if self.logger:
            self.logger.debug('Finished uploading part %s-%s.'% (start, stop))

    def close(self):
        
        if self.closed:
            return
            
        # Complete the multiplart glacier upload
        try:
            response = self.connection.complete_multipart_upload(self.vault_name,
                                                                 self.uploadid,
                                                                 bytes_to_hex(tree_hash(self.tree_hashes)),
                                                                 self.uploaded_size)
        except boto.glacier.exceptions.UnexpectedHTTPResponseError as e:
            raise ResponseException(
                "Error while closing a multipart upload to Amazon Glacier.",
                cause=e,
                code=e.code)
            
        response.read()
        self.archive_id = response['ArchiveId']
        self.location = response['Location']
        self.hash_sha256 = bytes_to_hex(tree_hash(self.tree_hashes))
        self.closed = True
        if self.logger:
            self.logger.debug('Closed multipart upload.')

    def get_archive_id(self):
        self.close()
        return self.archive_id

    def get_location(self):
        self.close()
        return self.location

    def get_hash(self):
        self.close()
        return self.hash_sha256
