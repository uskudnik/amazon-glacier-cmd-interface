#!/usr/bin/env python
# encoding: utf-8

# Originally developed by Thomas Parslow http://almostobsolete.net
# Extended by Urban Skudnik urban.skudnik@gmail.com
#
# Just a work in progress and adapted to what I need right now.
# It does uploads (via a file-like object that you write to) and
# I've started on downloads. Needs the development version of Boto from Github.
#
# At the moment you have to use the latest Boto from github:
# pip install --upgrade git+https://github.com/boto/boto.git
#
# Example usage:
#
#     glacierconn = GlacierConnection(AWS_ACCESS_KEY, AWS_SECRET_ACCESS_KEY)
#     writer = GlacierWriter(glacierconn, GLACIER_VAULT)
#     writer.write(somedata)
#     writer.write(someotherdata)
#     writer.close()
#     # Get the id of the newly created archive
#     archive_id = writer.get_archive_id()from boto.connection import AWSAuthConnection

import urllib
import hashlib
import math
import json
import sys

from boto.connection import AWSAuthConnection

class GlacierConnection(AWSAuthConnection):

    def __init__(self, aws_access_key_id=None, aws_secret_access_key=None,
                 region="us-east-1",
                 is_secure=True, port=None, proxy=None, proxy_port=None,
                 proxy_user=None, proxy_pass=None,
                 host=None, debug=0, https_connection_factory=None,
                 path='/', provider='aws',  security_token=None,
                 suppress_consec_slashes=True):
        if host is None:
            host = 'glacier.%s.amazonaws.com' % (region,)
        AWSAuthConnection.__init__(self, host,
                aws_access_key_id, aws_secret_access_key,
                is_secure, port, proxy, proxy_port, proxy_user, proxy_pass,
                debug=debug, https_connection_factory=https_connection_factory,
                path=path, provider=provider, security_token=security_token,
                suppress_consec_slashes=suppress_consec_slashes)

    def _required_auth_capability(self):
        return ["hmac-v4"]

    def get_vault(self, name):
        return GlacierVault(self, name)

    def make_request(self, method, path, headers=None, data='', host=None,
                     auth_path=None, sender=None, override_num_retries=None,
                     params=None):
        headers = headers or {}
        headers.setdefault("x-amz-glacier-version","2012-06-01")
        return super(GlacierConnection, self).make_request(method, path, headers,
                                                           data, host, auth_path,
                                                           sender, override_num_retries,
                                                           params=params)

    def list_vaults(self, marker=None):
        if marker:
            return self.make_request(method="GET", path='/-/vaults', params={'marker': marker})
        else:
            return self.make_request(method="GET", path='/-/vaults')

##MAX_VAULT_NAME_LENGTH = 255
##VAULT_NAME_ALLOWED_CHARACTERS = "[a-zA-Z\.\-\_0-9]+"
##
##def check_vault_name(name):
##    import re
##    m = re.match(VAULT_NAME_ALLOWED_CHARACTERS, name)
##    if len(name) > 255:
##        raise Exception(u"Vault name can be at most 255 charecters long.")
##    if len(name) == 0:
##        raise Exception(u"Vault name has to be at least 1 character long.")
##    if m.end() != len(name):
##        raise Exception(u"Allowed characters are a–z, A–Z, 0–9, '_' (underscore),\
##                        '-' (hyphen), and '.' (period)")
##    return True

class GlacierVault(object):
    def __init__(self, connection, name):
        self.connection = connection
        self.name = name

    def retrieve_archive(self, archive, sns_topic=None, description=None):
        """
        Initiate a archive retrieval job to download the data from an
        archive.
        """
        params = {"Type": "archive-retrieval", "ArchiveId": archive}
        if sns_topic is not None:
            params["SNSTopic"] = sns_topic
        if description is not None:
            params["Description"] = description
        job = GlacierJob(self, params)
        job.initiate()
        return job

    def retrieve_inventory(self, format=None, sns_topic=None, description=None):
        """
        Initiate a inventory retrieval job to list the contents of the archive.
        """
        params = {"Type": "inventory-retrieval"}
        if sns_topic is not None:
            params["SNSTopic"] = sns_topic
        if description is not None:
            params["Description"] = description
        if format is not None:
            params['Format'] = format
        job = GlacierJob(self, params)
        job.initiate()
        return job

    def make_request(self, method, extra_path, headers=None, data="", params=None):
        if extra_path:
            uri = "/-/vaults/%s%s" % (self.name, extra_path,)
        else:
            uri = "/-/vaults/%s" % (self.name,)
        return self.connection.make_request(method, uri, headers, data)

    def get_job(self, job_id):
        return GlacierJob(self, job_id=job_id)

    def list_jobs(self):
        response = self.make_request("GET", "/jobs", None)

##        assert response.status == 200,\
##                "List jobs response expected status 200, got status %s: %r"\
##                    % (response.status, json.loads(response.read())['message'])
##        jdata = json.loads(response.read())
##        self.job_list = jdata['JobList']
        return response

    def create_vault(self):
        return self.make_request("PUT", extra_path=None)

    def delete_vault(self):
        return self.make_request("DELETE", extra_path=None)

    def describe_vault(self):
        return self.make_request("GET", extra_path=None)

    def list_multipart_uploads(self, marker=None):
        if marker:
            return self.make_request("GET", extra_path="/multipart-uploads", params={'marker': marker})
        else:
            return self.make_request("GET", extra_path="/multipart-uploads")

    def list_parts(self, multipart_id, marker=None):
        if marker:
            return self.make_request("GET", extra_path="/multipart-uploads/%s" % (multipart_id, ), params={'marker': marker})
        else:
            return self.make_request("GET", extra_path="/multipart-uploads/%s" % (multipart_id, ))

    def delete_archive(self, archive_id):
        return self.make_request("DELETE", extra_path="/archives/%s" % (archive_id, ))

    def abort_multipart(self, multipart_id):
        return self.make_request("DELETE", extra_path="/multipart-uploads/%s" % (multipart_id, ))


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
            msg = "Start job expected 202 back (got %s)" % (response.status, )
            raise Exception(msg, response.read())
        response.read()

        self.job_id = response.getheader("x-amz-job-id")
        self.location = response.getheader("Location")

    def get_output(self, range_from=None, range_to=None):
        headers = {}
        if range_from is not None or range_to is not None:
            assert range_from is not None and range_to is not None, \
                        """If you specify one of range_from or range_to you must specify the other"""

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
    
    def __init__(self, connection, vault, region=None, description=None, part_size=DEFAULT_PART_SIZE):
        self.part_size = part_size * 1024 * 1024
        self.vault = vault
        self.connection = connection
        self.location = None

        self.uploaded_size = 0
        self.tree_hashes = []
        self.closed = False

        headers = {
                    "x-amz-glacier-version": "2012-06-01",
                    "x-amz-part-size": str(self.part_size),
                    "x-amz-archive-description": description
                  }
        response = self.connection.make_request(
            "POST",
            "/-/vaults/%s/multipart-uploads" % (self.vault,),
            headers,
            "")
        assert response.status == 201,\
                "Multipart-start should respond with a 201 (got %s).\n%r"\
                    % (response.status, response.read())
        response.read()
        self.upload_url = response.getheader("location")

    def write(self, data):
        
        assert not self.closed,\
               "Tried to write to a GlacierWriter that is already closed."

        if len(data) > self.part_size:
            raise CommunicationException (
                'Block of data provided must be equal to or smaller than the set block size.',
                cause='Data block too large')
        
        # Create a request and sign it
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

        response = self.connection.make_request(
            "PUT",
            self.upload_url,
            headers,
            data)

        assert response.status == 204,\
                "Multipart upload part should respond with a 204! (got %s): %r"\
                    % (response.status, response.read())

        response.read()
        self.uploaded_size += len(data)

    def close(self):
        if self.closed:
            return
            
        # Complete the multiplart glacier upload
        headers = {
                    "x-amz-glacier-version": "2012-06-01",
                    "x-amz-sha256-tree-hash": bytes_to_hex(tree_hash(self.tree_hashes)),
                    "x-amz-archive-size": str(self.uploaded_size)
                  }
        response = self.connection.make_request(
            "POST",
            self.upload_url,
            headers,
            "")

        assert response.status == 201,\
                "Multipart-complete should respond with a 201 (got %s).\n%r"\
                    % (response.status, response.read())
        response.read()
        self.archive_id = response.getheader("x-amz-archive-id")
        self.location = response.getheader("Location")
        self.hash_sha256 = response.getheader("x-amz-sha256-tree-hash")
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
