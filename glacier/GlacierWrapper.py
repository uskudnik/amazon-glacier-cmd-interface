# -*- coding: utf-8 -*-
"""
.. module:: GlacierWrapper
   :platform: Unix, Windows
   :synopsis: Wrapper for accessing Amazon Glacier, with Amazon SimpleDB support and other features.
"""

import json
import pytz
import re
import logging
import boto
import os.path
import time
import sys
import re
import traceback
import glaciercorecalls
import select
import hashlib

from functools import wraps
from dateutil.parser import parse as dtparse
from datetime import datetime
from pprint import pformat

from glaciercorecalls import GlacierConnection, GlacierWriter

from glacierexception import *

class log_class_call(object):
    """
    Decorator that logs class calls to specific functions.
    Set loglevel to DEBUG to see these logs.
    """

    def __init__(self, start, finish, getter=None):
        """
        Decorator constructor.

        :param start: Message logged when starting the class.
        :type start: str.
        :param finish: Message logged when finishing the class.
        :type finish: str.
        """
        
        self.start = start
        self.finish = finish
        self.getter = getter

    def __call__(self, fn):
        def wrapper(*args, **kwargs):
            that = args[0]
            that.logger.debug(self.start)
            ret = fn(*args, **kwargs)
            that.logger.debug(self.finish)
            if self.getter:
                that.logger.debug(pformat(self.getter(ret)))
            else:
                that.logger.debug(pformat(ret))

            return ret

        wrapper.func_name = fn.func_name
        if hasattr(fn, '__name__'):
            wrapper.__name__ = self.name = fn.__name__

        if hasattr(fn, '__doc__'):
            wrapper.__doc__ = fn.__doc__

        if hasattr(fn, '__module__'):
            wrapper.__module__ = fn.__module__

        return wrapper


class GlacierWrapper(object):
    """
    Wrapper for accessing Amazon Glacier, with Amazon SimpleDB support
    and other features.
    """

    VAULT_NAME_ALLOWED_CHARACTERS = "[a-zA-Z\.\-\_0-9]+"
    ID_ALLOWED_CHARACTERS = "[a-zA-Z\-\_0-9]+"
    MAX_VAULT_NAME_LENGTH = 255
    MAX_VAULT_DESCRIPTION_LENGTH = 1024
    MAX_PARTS = 10000
    AVAILABLE_REGIONS = ('us-east-1', 'us-west-2', 'us-west-1',
                         'eu-west-1', 'ap-northeast-1')
    AVAILABLE_REGIONS_MESSAGE = """Invalid region. Available regions for Amazon Glacier are:
us-east-1 (US - Virginia)
us-west-1 (US - N. California)
us-west-2 (US - Oregon)
eu-west-1 (EU - Ireland)
ap-northeast-1 (Asia-Pacific - Tokyo)"""

    def setuplogging(self, logfile, loglevel, logtostdout):
        """
        Set up the logging facility. If no logging parameters are
        given, WARNING-level logging will be printed to stdout.
        If logtostdout is True, messages will be sent to stdout, even
        if a logfile is given.
        If a logfile is given but can not be written to, logs are sent to
        stderr instead.

        :param logfile: the fully qualified file name of where to log to.
        :type logfile: str
        :param loglevel: the level of logging.
        :type loglevel: str
        :param logtostdout: whether to sent log messages to stdout.
        :type logtostdout: boolean
        """
        levels = {'3': logging.CRITICAL,
                  'CRITICAL': logging.CRITICAL,
                  '2': logging.ERROR,
                  'ERROR': logging.ERROR,
                  '1': logging.WARNING,
                  'WARNING': logging.WARNING,
                  '0': logging.INFO,
                  'INFO': logging.INFO,
                  '-1': logging.DEBUG,
                  'DEBUG': logging.DEBUG}
        
        loglevel = 'WARNING' if not loglevel in levels.keys() else levels[loglevel]

        datefmt = '%b %d %H:%M:%S'
        logformat = '%(asctime)s %(levelname)-8s glacier-cmd %(message)s'

        if logtostdout:
            logging.basicConfig(level=loglevel,
                                stream=sys.stdout,
                                format=logformat,
                                datefmt=datefmt)
        elif logfile:
            try:
                open(logfile, 'a')
            except IOError:

                # Can't open the specified log file, log to stderr instead.
                logging.basicConfig(level=loglevel,
                                    stream=sys.stderr,
                                    format=logformat,
                                    datefmt=datefmt)
            else:
                logging.basicConfig(level=loglevel,
                                    filename=logfile,
                                    format=logformat,
                                    datefmt=datefmt)
        
        else:
            logging.basicConfig(level='WARNING',
                                stream=sys.stdout,
                                format=logformat,
                                datefmt=datefmt)


    def glacier_connect(func):
        """
        Decorator which handles the connection to Amazon Glacier.

        :param func: Function to wrap
        :type func: function

        :returns: wrapper function
        :rtype: function
        :raises: GlacierWrapper.ConnectionException
        """

        @wraps(func)
        @log_class_call("Connecting to Amazon Glacier.",
                        "Connection to Amazon Glacier successful.")
        def glacier_connect_wrap(*args, **kwargs):
            self = args[0]
            if not hasattr(self, "glacierconn") or \
                (hasattr(self, "glacierconn") and not self.glacierconn):
                try:
                    self.logger.debug("""Connecting to Amazon Glacier with \n   aws_access_key %s\n   aws_secret_key %s\n   region %s""",
                                      self.aws_access_key,
                                      self.aws_secret_key,
                                      self.region)
                    self.glacierconn = GlacierConnection(self.aws_access_key,
                                                         self.aws_secret_key,
                                                         region_name=self.region)
                except boto.exception.AWSConnectionError as e:
                    raise ConnectionException(
                        "Cannot connect to Amazon Glacier.",
                        cause=e.cause,
                        code="GlacierConnectionError")

            return func(*args, **kwargs)
        return glacier_connect_wrap

    def sdb_connect(func):
        """
        Decorator which connects to Amazon SimpleDB.

        :param func: Function to wrap
        :type func: function

        :returns: wrapper function
        :rtype: function
        :raises: GlacierWrapper.ConnectionException
        """

        @wraps(func)
        @log_class_call("Connecting to Amazon SimpleDB.",
                        "Connection to Amazon SimpleDB successful.")
        def sdb_connect_wrap(*args, **kwargs):
            self = args[0]
            if not self.bookkeeping:
                return func(*args, **kwargs)

            # TODO: give SimpleDB its own class? Or move the few calls
            # we need to glaciercorecalls?
            
            if not hasattr(self, 'sdb_conn'):
                try:
                    self.logger.debug("""\
Connecting to Amazon SimpleDB domain %s with
    naws_access_key %s
    naws_secret_key %s""",
                                      self.bookkeeping_domain_name,
                                      self.aws_access_key,
                                      self.aws_secret_key)
                    self.sdb_conn = boto.connect_sdb(aws_access_key_id=self.aws_access_key,
                                                     aws_secret_access_key=self.aws_secret_key)
                    domain_name = self.bookkeeping_domain_name
                    self.sdb_domain = self.sdb_conn.get_domain(domain_name, validate=True)
                except (boto.exception.AWSConnectionError, boto.exception.SDBResponseError) as e:
                    raise ConnectionException(
                        "Cannot connect to Amazon SimpleDB.",
                        cause=e,
                        code="SdbConnectionError")
                
            return func(*args, **kwargs)

        return sdb_connect_wrap

    @log_class_call('Checking whether vault name is valid.',
                     'Vault name is valid.')
    def _check_vault_name(self, name):
        """
        Checks whether we have a valid vault name.

        :param name: Vault name
        :type name: str

        :returns: True if valid, raises exception otherwise.
        :rtype: boolean
        :raises: GlacierWrapper.InputException
        """

        if len(name) > self.MAX_VAULT_NAME_LENGTH:
            raise InputException(
                u"Vault name can be at most %s characters long."% self.MAX_VAULT_NAME_LENGTH,
                cause='Vault name more than %s characters long.'% self.MAX_VAULT_NAME_LENGTH,
                code="VaultNameError")
        
        if len(name) == 0:
            raise InputException(
                u"Vault name has to be at least 1 character long.",
                cause='Vault name has to be at least 1 character long.',
                code="VaultNameError")

        m = re.match(self.VAULT_NAME_ALLOWED_CHARACTERS, name)
        if m.end() != len(name):
            raise InputException(
                u"""Allowed characters are a-z, A-Z, 0-9, '_' (underscore), '-' (hyphen), and '.' (period)""",
                cause='Illegal characters in the vault name.',
                code="VaultNameError")

        return True

    @log_class_call('Checking whether vault description is valid.',
                    'Vault description is valid.')
    def _check_vault_description(self, description):
        """
        Checks whether a vault description is valid (at least one character,
        not too long, no illegal characters).

        :param description: Vault description
        :type description: str

        :returns: True if valid, raises exception otherwise.
        :rtype: boolean
        :raises: GlacierWrapper.InputException
        """
        if len(description) > self.MAX_VAULT_DESCRIPTION_LENGTH:
            raise InputException(
                u"Description must be no more than %s characters."% self.MAX_VAULT_DESCRIPTION_LENGTH,
                cause='Vault description contains more than %s characters.'% self.MAX_VAULT_DESCRIPTION_LENGTH,
                code="VaultDescriptionError")

        for char in description:
            n = ord(char)
            if n < 32 or n > 126:
                raise InputException(
                    u"""The allowed characters are 7-bit ASCII without \
control codes, specifically ASCII values 32-126 decimal \
or 0x20-0x7E hexadecimal.""",
                    cause="Invalid characters in the vault name.",
                    code="VaultDescriptionError")
            
        return True

    @log_class_call('Checking whether id is valid.',
                     'Id is valid.')
    def _check_id(self, amazon_id, id_type):
        """
        Checks if an id (jobID, uploadID, archiveID) is valid.
        A jobID or uploadID is 92 characters long, an archiveID is
        138 characters long.
        Valid characters are a-z, A-Z, 0-9, '-' and '_'.

        :param amazon_id: id to be validated
        :type amazon_id: str
        :param id_type: the case-sensity type of id (JobId, UploadId, ArchiveId).
        :type id_type: str

        :returns: True if valid, raises exception otherwise.
        :rtype: boolean
        :raises: GlacierWrapper.InputException
        """

        length = {'JobId': 92,
                  'UploadId': 92,
                  'ArchiveId': 138}
        self.logger.debug('Checking a %s.'% id_type)
        if len(amazon_id) <> length[id_type]:
            raise InputException(
                'A %s must be %s characters long. This ID is %s characters.'% (id_type, length[id_type], len(amazon_id)),
                cause='Incorrect length of the %s string.'% id_type,
                code="IdError")
        
        m = re.match(self.ID_ALLOWED_CHARACTERS, amazon_id)
        if m.end() != len(amazon_id):
            raise InputException(
                u"""This %s contains invalid characters. \
Allowed characters are a-z, A-Z, 0-9, '_' (underscore) and '-' (hyphen)"""% id_type,
                cause='Illegal characters in the %s string.'% id_type,
                code="IdError")

        return True

    @log_class_call('Validating region.',
                    'Region is valid.')
    def _check_region(self, region):
        """
        Checks whether the region given is valid.

        :param region: the region to be validated.
        :type region: str

        :returns: True if valid, raises exception otherwise.
        :rtype: boolean
        :raises: GlacierWrapper.InputException
        """
        if not region in self.AVAILABLE_REGIONS:
            raise InputException(
                self.AVAILABLE_REGIONS_MESSAGE,
                cause='Invalid region code: %s.'% region,
                code='RegionError')
        
        return True

    def _next_power_of_2(self, v):
        """
        Returns the next power of 2, or the argument if it's
        already a power of 2.

        :param v: the value to be tested.
        :type v: int

        :returns: the next power of 2.
        :rtype: int
        """
        if v == 0:
            return 1
        
        v -= 1
        v |= v >> 1
        v |= v >> 2
        v |= v >> 4
        v |= v >> 8
        v |= v >> 16
        return v + 1

    def _progress(self, msg):
        """
        A progress indicator. Prints the progress message if stdout
        is connected to a tty (i.e. run from the command prompt).

        :param msg: the progress message to be printed.
        :type msg: str
        """
        if sys.stdout.isatty():
            print msg,
            sys.stdout.flush()

    def _size_fmt(self, num, decimals=1):
        """
        Formats byte sizes in human readable format. Anything bigger
        than TB is returned as TB.
        Number of decimals is optional, defaults to 1.

        :param num: the size in bytes.
        :type num: int
        :param decimals: the number of decimals to return.
        :type decimals: int

        :returns: the formatted number.
        :rtype: str
        """

        fmt = "%%3.%sf %%s"% decimals
        for x in ['bytes','KB','MB','GB']:
            if num < 1024.0:
                return fmt % (num, x)
            
            num /= 1024.0
            
        return fmt % (num, 'TB')

    def _decode_error_message(self, e):
        try:
            e = json.loads(e)['message']
        except:
            e = None

        return e

    @glacier_connect
    @log_class_call("Listing vaults.",
                    "Listing vaults complete.")
    def lsvault(self, limit=None):
        """
        Lists available vaults.
        
        :returns : List of vault descriptions.
        :rtype: list ::
        
        [{u'CreationDate': u'2012-09-20T14:29:14.710Z',
          u'LastInventoryDate': u'2012-10-01T02:10:12.497Z',
          u'NumberOfArchives': 15,
          u'SizeInBytes': 33932739443L,
          u'VaultARN': u'arn:aws:glacier:us-east-1:012345678901:vaults/your_vault_name',
          u'VaultName': u'your_vault_name'},
         ...
         ]

        :raises: GlacierWrapper.CommunicationException, GlacierWrapper.ResponseException
        """
        marker = None
        vault_list = []
        while True:
            try:
                response = self.glacierconn.list_vaults(marker=marker)
            except boto.glacier.exceptions.UnexpectedHTTPResponseError as e:
                raise ResponseException(
                    'Failed to recieve vault list.',
                    cause=self._decode_error_message(e.body),
                    code=e.code)

            vault_list += response.copy()['VaultList']
            marker = response.copy()['Marker']
            if limit and len(vault_list) >= limit:
                vault_list = vault_list[:limit]
                break

            if not marker:
                break
        
        return vault_list

    @glacier_connect
    @log_class_call("Creating vault.",
                    "Vault creation completed.")
    def mkvault(self, vault_name):
        """
        Creates a new vault.

        :param vault_name: Name of vault to be created.
        :type vault_name: str

        :returns: Response data.
        :rtype: boto.glacier.response.GlacierResponse        
         
        :raises: GlacierWrapper.CommunicationException
        """

        self._check_vault_name(vault_name)
        try:
            response = self.glacierconn.create_vault(vault_name)
        except boto.glacier.exceptions.UnexpectedHTTPResponseError as e:
            raise ResponseException(
                'Failed to create vault with name %s.'% vault_name,
                cause=self._decode_error_message(e.body),
                code=e.code)

        return response.copy()

    @glacier_connect
    @log_class_call("Removing vault.",
                    "Vault removal complete.")
    def rmvault(self, vault_name):
        """
        Removes a vault. Vault must be empty before it can be removed.

        :param vault_name: Name of vault to be removed.
        :type vault_name: str

        :returns: Response data. Raises exception on failure.
        :rtype: list ::
        
        [('x-amzn-requestid', 'Example_rkQ-xzxHfrI-997hphbfdcIbL74IhDf_Example'),
        ('date', 'Mon, 01 Oct 2012 13:54:06 GMT')]

        :raises: GlacierWrapper.CommunicationException
        """

        self._check_vault_name(vault_name)
        try:
            response = self.glacierconn.delete_vault(vault_name)
        except boto.glacier.exceptions.UnexpectedHTTPResponseError as e:
            raise ResponseException(
                'Failed to remove vault with name %s.'% vault_name,
                cause=self._decode_error_message(e.body),
                code=e.code)
        
        return response.copy()


    @glacier_connect
    @log_class_call("Requesting vault description.",
                    "Vault description received.")
    def describevault(self, vault_name):
        """
        Describes vault inventory and other details.

        :param vault_name: Name of vault.
        :type vault_name: str

        :returns: vault description.
        :rtype: dict ::
        
        {u'CreationDate': u'2012-10-01T13:24:55.791Z',
         u'LastInventoryDate': None,
         u'NumberOfArchives': 0,
         u'SizeInBytes': 0,
         u'VaultARN': u'arn:aws:glacier:us-east-1:012345678901:vaults/your_vault_name',
         u'VaultName': u'your_vault_name'}
         
        :raises: GlacierWrapper.CommunicationException
        """

        self._check_vault_name(vault_name)
        try:
            response = self.glacierconn.describe_vault(vault_name)
        except boto.glacier.exceptions.UnexpectedHTTPResponseError as e:
            raise ResponseException(
                'Failed to get description of vault with name %s.'% vault_name,
                cause=self._decode_error_message(e.body),
                code=e.code)
        
        return response.copy()

    @glacier_connect
    @log_class_call("Requesting jobs list.",
                    "Active jobs list received.")
    def list_jobs(self, vault_name, completed=None,
                  status_code=None, limit=None):
        """
        Provides a list of current Glacier jobs with status and other
        job details.
        If no jobs active it returns an empty list.

        :param vault_name: Name of vault.
        :type vault_name: str

        :returns: job list
        :rtype: list ::

        [{u'Action': u'InventoryRetrieval',
          u'ArchiveId': None,
          u'ArchiveSizeInBytes': None,
          u'Completed': False,
          u'CompletionDate': None,
          u'CreationDate': u'2012-10-01T14:54:51.919Z',
          u'InventorySizeInBytes': None,
          u'JobDescription': None,
          u'JobId': u'Example_rctvAMVd3tgAbCuQkD2vjNQ6aw9ifwACvhjhIeKtNnZqeSIuMYRo3JUKsK_0M-VNYvb0-eEreSUp_Example',
          u'SHA256TreeHash': None,
          u'SNSTopic': None,
          u'StatusCode': u'InProgress',
          u'StatusMessage': None,
          u'VaultARN': u'arn:aws:glacier:us-east-1:012345678901:vaults/your_vault_name'},
          {...}]
          
        :raises: GlacierWrapper.ResponseException
        """
        self._check_vault_name(vault_name)
        marker = None
        job_list = []
        while True:
            try:
                response = self.glacierconn.list_jobs(vault_name, completed=completed,
                                                      status_code=status_code, marker=marker)
            except boto.glacier.exceptions.UnexpectedHTTPResponseError as e:
                raise ResponseException(
                    'Failed to recieve the jobs list for vault %s.'% vault_name,
                    cause=self._decode_error_message(e.body),
                    code=e.code)
            job_list += response.copy()['JobList']
            marker = response.copy()['Marker']
            if limit and len(job_list) >= limit:
                job_list = job_list[:limit]
                break

            if not marker:
                break

        return job_list

    @glacier_connect
    @log_class_call("Requesting job description.",
                    "Job description received.")
    def describejob(self, vault_name, job_id):
        """
        Gives detailed description of a job.

        :param vault_name: Name of vault.
        :type vault_name: str
        :param job_id: id of job to be described.
        :type job_id: str

        :returns: List of job properties.
        :rtype: dict ::
        
        {u'Action': u'InventoryRetrieval',
         u'ArchiveId': None,
         u'ArchiveSizeInBytes': None,
         u'Completed': False,
         u'CompletionDate': None,
         u'CreationDate': u'2012-10-01T14:54:51.919Z',
         u'InventorySizeInBytes': None,
         u'JobDescription': None,
         u'JobId': u'Example_d3tgAbCuQ9vPRqRJkD2vjNQ6wBgga7Xaw9ifwACvhjhIeKtNnZqeSIuMYRo3JUKsK_0M-VNYvb0-_Example',
         u'SHA256TreeHash': None,
         u'SNSTopic': None,
         u'StatusCode': u'InProgress',
         u'StatusMessage': None,
         u'VaultARN': u'arn:aws:glacier:us-east-1:012345678901:vaults/your_vault_name'}
        
        :raises: GlacierWrapper.CommunicationException
        """

        self._check_vault_name(vault_name)
        self._check_id (job_id, 'JobId')
        try:
            response = self.glacierconn.describe_job(vault_name, job_id)
        except boto.glacier.exceptions.UnexpectedHTTPResponseError as e:
            raise ResponseException(
                'Failed to get description of job with job id %s.'% job_id,
                cause=self._decode_error_message(e.body),
                code=e.code)
        
        return response.copy()
    
    @glacier_connect
    @log_class_call("Aborting multipart upload.",
                    "Multipart upload successfully aborted.")
    def abortmultipart(self, vault_name, upload_id):
        """
        Aborts an incomplete multipart upload, causing any uploaded data to be
        removed from Amazon Glacier.

        :param vault_name: Name of the vault.
        :type vault_name: str
        :param upload_id: the UploadId of the multipart upload to be aborted.
        :type upload_id: str

        :returns: server response.
        :rtype: list ::

        [('x-amzn-requestid', 'Example_ZJwjlLbvg8Dg_lnYUnC8bjV6cvlTBTO_Example'),
         ('date', 'Mon, 01 Oct 2012 16:08:23 GMT')]

        :raises: GlacierWrapper.CommunicationException
        """
        
        self._check_vault_name(vault_name)
        self._check_id(upload_id, "UploadId")
        try:
            response = self.glacierconn.abort_multipart_upload(vault_name, upload_id)
        except boto.glacier.exceptions.UnexpectedHTTPResponseError as e:
            raise ResponseException(
                'Failed to abort multipart upload with id %s.'% upload_id,
                cause=self._decode_error_message(e.body),
                code=e.code)
        
        return response.copy()
     
    @glacier_connect
    @log_class_call("Listing multipart uploads.",
                    "Multipart uploads list received successfully.")
    def listmultiparts(self, vault_name, limit=None):
        """
        Provids a list of all currently active multipart uploads.

        :param vault_name: Name of the vault.
        :type vault_name: str

        :return: list of uploads, or None.
        :rtype: list :: 

        [{u'ArchiveDescription': u'myfile.tgz',
          u'CreationDate': u'2012-09-30T15:21:35.890Z',
          u'MultipartUploadId': u'Example_oiuhncYLvBRZLzYgVw7MO_OO4l6i78va8N83R9xLNqrFaa8Vyz4W_JsaXhLNicCCbi_OdsHD8dHK_Example',
          u'PartSizeInBytes': 134217728,
          u'VaultARN': u'arn:aws:glacier:us-east-1:012345678901:vaults/your_vault_name'},
         {...}]

        :raises: GlacierWrapper.CommunicationException
        """
        self._check_vault_name(vault_name)
        marker = None
        uploads = []
        while True:
            try:
                response = self.glacierconn.list_multipart_uploads(vault_name, marker=marker)
            except boto.glacier.exceptions.UnexpectedHTTPResponseError as e:
                raise ResponseException(
                    'Failed to get a list of multipart uploads for vault %s.'% vault_name,
                    cause=self._decode_error_message(e.body),
                    code=e.code)

            uploads += response.copy()['UploadsList']
            marker = response.copy()['Marker']
            if limit and len(uploads) >= limit:
                uploads = uploads[:limit]
                break
            
            if not marker:
                break
            
        return uploads

    @glacier_connect
    @sdb_connect
    @log_class_call("Uploading archive.",
                    "Upload of archive finished.")
    def upload(self, vault_name, file_name, description, region,
               stdin, alternative_name, part_size, uploadid, resume):
        """
        Uploads a file to Amazon Glacier.
        
        :param vault_name: Name of the vault.
        :type vault_name: str
        :param file_name: Name of the file to upload.
        :type file_name: str
        :param description: Description of the upload.
        :type description: str
        :param region: region where to upload to.
        :type region: str
        :param stdin: whether to use stdin to read data from.
        :type stdin: boolan
        :param part_size: the size (in MB) of the blocks to upload.
        :type part_size: int

        :raises:
        """

        # Do some sanity checking on the user values.
        self._check_vault_name(vault_name)
        self._check_region(region)
        if not description:
            description = file_name if file_name else 'No description.'

        if description:
            self._check_vault_description(description)
            
        if uploadid:
            self._check_id(uploadid, 'UploadId')

        if resume and stdin:
            raise InputException(
                'You must provide the UploadId to resume upload of streams from stdin.\nUse glacier-cmd listmultiparts <vault> to find the UploadId.')

        # If file_list is given, try to use this file(s).
        # Otherwise try to read data from stdin.
        total_size = 0
        reader = None
        if not stdin:
            if not file_name:
                raise InputException(
                    "No file name given for upload.")
            
            try:
                reader = open(file_name, 'rb')
            except IOError as e:
                raise InputException(
                    "Could not access file: %s."% file_name,
                    cause=e)
                
        elif select.select([sys.stdin,],[],[],0.0)[0]:
            reader = sys.stdin
            total_size = 0
        else:
            raise InputException(
                "There is nothing to upload.")

        # Log the kind of upload we're going to do.
        if uploadid:
            self.logger.info('Attempting resumption of upload of %s to %s.'% (file_list[0] if file_list else 'data from stdin', vault_name))
        elif resume:
            self.logger.info('Attempting resumption of upload of %s to %s.'% (file_list, vault_name))
        else:
            self.logger.info('Starting upload of %s to %s.\nDescription: %s'% (file_name if file_name else 'data from stdin', vault_name, description))

        # If user did not specify part_size, compute the optimal (i.e. lowest
        # value to stay within the self.MAX_PARTS (10,000) block limit).
        if part_size < 0:
            if total_size > 0:
                part_size = self._next_power_of_2(total_size / (1024*1024*self.MAX_PARTS))
            else:
                part_size = GlacierWriter.DEFAULT_PART_SIZE
        else:
            ps = self._next_power_of_2(part_size)
            if not ps == part_size:
                self.logger.warning('Part size in MB must be a power of 2, \
e.g. 1, 2, 4, 8 MB; automatically increased part size from %s to %s.'% (part_size, ps))

            part_size = ps

        # Check whether user specified value is big enough, and adjust if needed.
        if total_size > part_size*1024*1024*self.MAX_PARTS:
            part_size = self._next_power_of_2(total_size / (1024*1024*self.MAX_PARTS))
            self.logger.warning("Part size given is too small; \
using %s MB parts to upload."% part_size)

        part_size_in_bytes = part_size * 1024 * 1024
        
        # If we have an UploadId, check whether it is linked to a current
        # job. If so, check whether uploaded data matches the input data and
        # try to resume uploading.
        upload = None
        if uploadid:
            uploads = self.listmultiparts(vault_name)
            for upload in uploads:
                if uploadid == upload['MultipartUploadId']:
                    self.logger.debug('Found a matching upload id. Continuing upload resumption attempt.')
                    self.logger.debug(upload)
                    part_size_in_bytes = upload['PartSizeInBytes']
                    break
            else:
                raise InputException(
                    'Can not resume upload of this data as no existing job with this uploadid could be found.')

        # Initialise the writer task.
        writer = GlacierWriter(self.glacierconn, vault_name, description=description,
                               part_size_in_bytes=part_size_in_bytes, uploadid=uploadid, logger=self.logger)

        if upload:
            marker = None
            while True:

                # Fetch a list of already uploaded parts and their SHA hashes.
                try:
                    response = self.glacierconn.list_parts(vault_name, uploadid, marker=marker)
                except boto.glacier.exceptions.UnexpectedHTTPResponseError as e:
                    raise ResponseException(
                        'Failed to get a list already uploaded parts for interrupted upload %s.'% uploadid,
                        cause=self._decode_error_message(e.body),
                        code=e.code)
                
                list_parts_response = response.copy()
                current_position = 0

                # Process the parts list.
                # For each part of data, take the matching data range from
                # the local file, and compare hashes.
                # If recieving data over stdin, the parts must be sequential
                # and the first must start at 0. For file, we can use the seek()
                # function to handle non-sequential parts.
                for part in list_parts_response['Parts']:
                    start, stop = (int(p) for p in part['RangeInBytes'].split('-'))
                    if not start == current_position:
                        if stdin:
                            raise InputException(
                                'Cannot verify non-sequential upload data from stdin.')
                        reader.seek(start)

                    # Try to read the chunk of data, and take the hash if we
                    # have received anything.
                    # If no data or hash mismatch, stop checking raise an
                    # exception.
                    data = reader.read(stop-start)
                    if data:
                        data_hash = glaciercorecalls.tree_hash(glaciercorecalls.chunk_hashes(data))
                        if glaciercorecalls.bytes_to_hex(data_hash) == part['SHA256TreeHash']:
                            self.logger.debug('Part %s hash matches.')
                            writer.tree_hashes.append(data_hash)
                        else:
                            raise InputException(
                                'Received data does not match uploaded data; please check your uploadid and try again.',
                                cause='SHA256 hash mismatch.')
                        
                    else:
                        raise InputException(
                            'Received data does not match uploaded data; please check your uploadid and try again.',
                            cause='No or not enough data to match.')

                # If a marker is present, this means there are more pages
                # of parts available. If no marker, we have the last page.
                marker = list_parts_response['Marker']
                writer.uploaded_size = stop
                if not marker:
                    break

                if total_size > 0:
                    msg = '\rChecked %s of %s (%s%%).' \
                          % (self._size_fmt(writer.uploaded_size),
                             self._size_fmt(total_size),
                             int(100 * writer.uploaded_size/total_size))
                else:
                    msg = '\rChecked %s.' \
                          % (self._size_fmt(writer.uploaded_size))
                    
                self._progress(msg)

            # Finished checking; log this and print the final status update
            # before resuming the upload.
            self.logger.info('Already uploaded: %s. Continuing from there.'% self._size_fmt(stop))
            if total_size > 0:
                msg = '\rChecked %s of %s (%s%%). Check done; resuming upload.' \
                      % (self._size_fmt(writer.uploaded_size),
                         self._size_fmt(total_size),
                         int(100 * writer.uploaded_size/total_size))
            else:
                msg = '\rChecked %s. Check done; resuming upload.' \
                      % (self._size_fmt(writer.uploaded_size))

            self._progress(msg)
                
        # Read file in parts so we don't fill the whole memory.
        start_time = current_time = previous_time = time.time()
        start_bytes = writer.uploaded_size
        for part in iter((lambda:reader.read(part_size_in_bytes)), ''):
            writer.write(part)
            current_time = time.time()
            overall_rate = int((writer.uploaded_size-start_bytes)/(current_time - start_time))
            if total_size > 0:
                
                # Calculate transfer rates in bytes per second.
                current_rate = int(part_size_in_bytes/(current_time - previous_time))

                # Estimate finish time, based on overall transfer rate.
                if overall_rate > 0:
                    time_left = (total_size - writer.uploaded_size)/overall_rate
                    eta = time.strftime("%H:%M:%S", time.localtime(current_time + time_left))
                else:
                    time_left = "Unknown"
                    eta = "Unknown"

                msg = '\rWrote %s of %s (%s%%). Rate %s/s, average %s/s, eta %s.' \
                      % (self._size_fmt(writer.uploaded_size),
                         self._size_fmt(total_size),
                         int(100 * writer.uploaded_size/total_size),
                         self._size_fmt(current_rate, 2),
                         self._size_fmt(overall_rate, 2),
                         eta)

            else:
                msg = '\rWrote %s. Rate %s/s.' \
                      % (self._size_fmt(writer.uploaded_size),
                         self._size_fmt(overall_rate, 2))

            self._progress(msg)
            previous_time = current_time
            self.logger.debug(msg)

        writer.close()
        current_time = time.time()
        overall_rate = int(writer.uploaded_size/(current_time - start_time))
        msg = '\rWrote %s. Rate %s/s.\n' % (self._size_fmt(writer.uploaded_size),
                                            self._size_fmt(overall_rate, 2))
        self._progress(msg)
        self.logger.info(msg)

        archive_id = writer.get_archive_id()
        sha256hash = writer.get_hash()
        location = writer.get_location()

        if self.bookkeeping:
            self.logger.info('Writing upload information into the bookkeeping database.')

            # Use the alternative name as given by --name <name> if we have it.
            file_name = alternative_name if alternative_name else file_name

            # If still no name this is an stdin job, so set name accordingly.
            file_name = file_name if file_name else 'Data from stdin.'
            file_attrs = {
                'region': region,
                'vault': vault_name,
                'filename': file_name,
                'archive_id': archive_id,
                'location': location,
                'description': description,
                'date':'%s' % datetime.utcnow().replace(tzinfo=pytz.utc),
                'hash': sha256hash
            }

##            if file_name:
##                file_attrs['filename'] = file_name
##            elif stdin:
##                file_attrs['filename'] = 'data from stdin'

            self.sdb_domain.put_attributes(file_attrs['filename'], file_attrs)

        return (archive_id, sha256hash)


    @glacier_connect
    @log_class_call("Processing archive retrieval job.",
                    "Archive retrieval job response received.")
    def getarchive(self, vault_name, archive_id):
        """
        Requests Amazon Glacier to make archive available for download.
        Returns a tuple (action, job status, job id, search results)

        If retrieval job is not yet initiated:
                initiate a job,
                return tuple ("initiated", job status, None, results)
                
        If retrieval job is already initiated:
                return tuple ("running", job status, None, results).
                
        If the file is ready for download:
                return tuple ("ready", job status, GlacierJob, results).

        :param vault: Vault name from where we want to retrieve the archive.
        :type vault: str
        :param archive: ArchiveID of archive to be retrieved.
        :type archive: str

        :returns: Tuple of (status, job, JobId)
                  TODO: Return example
        :rtype: (str, dict, str)
        """

        results = None
        self._check_vault_name(vault_name)
        self._check_id(archive_id, 'ArchiveId')
        
        # Check whether we have a retrieval job for the archive.
        job_list = self.list_jobs(vault_name)
        for job in job_list:
            if job['ArchiveId'] == archive_id:
                if job['Completed']:
                    return ('ready', job, job['JobId'])

                return ('running', job, None)
            
        # No job found related to this archive, start a new job.
        job_data = {'ArchiveId': archive_id,
                    'Type': archive-retrieval}
        try:
            response = self.glacierconn.initiate_job(vault_name, job_data)
        except boto.glacier.exceptions.UnexpectedHTTPResponseError as e:
            raise ResponseException(
                'Failed to initiate an archive retrieval job for archive %s in vault %s.'% (archive_id, vault_name),
                cause=self._decode_error_message(e.body),
                code=e.code)
        
        job = response.copy()
        return ('initiated', job, None)

    @glacier_connect
    @sdb_connect
    @log_class_call("Download an archive.",
                    "Download archive done.")
    def download(self, vault_name, archive_id, out_file=None, overwrite=False):
        """
        Download a file from Glacier, and store it in out_file.
        If no out_file is given, the file will be dumped on stdout.
        """

        # Sanity checking on the input.
        self._check_vault_name(vault_name)
        self._check_id(archive_id, 'ArchiveId')

        # Check whether the requested file is available from Amazon Glacier.
        job_list = self.list_jobs(vault_name)
        for job in job_list:
            if job['ArchiveId'] == archive_id:
                if not job['Completed']:
                    raise CommunicationException(
                        "Archive retrieval request not completed yet. Please try again later.")
                self.logger.debug('Archive retrieval completed; archive is available for download now.')
                break
            
        else:
            raise InputException(
                "Requested archive not available. Please make sure \
your archive ID is correct, and start a retrieval job using \
'getarchive' if necessary.")

        # Check whether we can access the file the archive has to be written to.
        if out_file:
            if os.path.isfile(out_file) and not overwrite:
                raise InputException(
                    "File exists already, aborting. Use the overwrite flag to overwrite existing file.",
                    code="FileError")
            try:
                out = open(out_file, 'w')
                out.close()
            except IOError as e:
                raise InputException(
                    "Cannot access the ouput file.",
                    cause=e)

        if out_file:
            self.logger.debug('Starting download of archive to file %s.'% out_file)
            ffile = open(out_file, "w")
            try:
                ffile.write(self.glacierconn.get_output(vault_name, job['JobId']))
            except boto.glacier.exceptions.UnexpectedHTTPResponseError as e:
                raise ResponseException(
                    'Failed to download archive %s.'% archive_id,
                    cause=self._decode_error_message(e.body),
                    code=e.code)
            
            ffile.close()
            self.logger.debug('Download of archive finished.')

            #TODO: tree-hash check.
            return 'File download successful.'
        
        else:
            self.logger.debug('Downloading archive and sending output to stdout.')
            try:
                print self.glacierconn.get_output(vault_name, job['JobId']),
            except boto.glacier.exceptions.UnexpectedHTTPResponseError as e:
                raise ResponseException(
                    'Failed to download archive %s.'% archive_id,
                    cause=self._decode_error_message(e.body),
                    code=e.code)

    @glacier_connect
    @sdb_connect
    @log_class_call("Searching for archive.",
                    "Search done.")
    def search(self, vault=None, region=None, file_name=None, search_term=None, print_results=False):

        # Sanity checking.
        if not self.bookkeeping:
            raise Exception(
                u"You must enable bookkeeping to be able to do searches.")

        if vault:
            self._check_vault_name(vault)
            
        if region:
            self._check_region(region)

##        if file_name and ('"' in file_name or "'" in file_name):
##            raise InputException(
##                'Quotes like \' and \" are not allowed in search terms.',
##                cause='Invalid search term %s: contains quotes.'% file_name)
##                
##
##        if search_term and ('"' in search_term or "'" in search_term):
##            raise InputException(
##                'Quotes like \' and \" are not allowed in search terms.',
##                cause='Invalid search term %s: contains quotes.'% search_term)

        self.logger.debug('Search terms: vault %s, region %s, file name %s, search term %s'%
                          (vault, region, file_name, search_term))
        search_params = []
        if region:
            search_params += ["region='%s'" % (region,)]

        if vault:
            search_params += ["vault='%s'" % (vault,)]

        if file_name:
            search_params += ["filename like '%"+file_name.replace("'", "''")+"%'"]
            
        if search_term:
            search_params += ["description like '%"+search_term.replace("'", "''")+"%'"]

        if search_params:
            search_params = " and ".join(search_params)
            query = 'select * from `%s` where %s' % (self.bookkeeping_domain_name, search_params)
        else:
            query = 'select * from `%s`' % self.bookkeeping_domain_name

        self.logger.debug('Query: "%s"'% query)
        result = self.sdb_domain.select(query)
        items = []
        try:
            for item in result:
                self.logger.debug('Next search result:\n%s'% item)
                items.append(item)
        except boto.exception.SDBResponseError as e:
            raise ResponseException(
                    'SimpleDB did not like your query with parameters %s.'% search_params,
                    cause=self._decode_error_message(e.body),
                    code=e.code)

        return items

    @glacier_connect
    @sdb_connect
    @log_class_call("Deleting archive.", "Archive deleted.")
    def rmarchive(self, vault_name, archive_id):
        """
        Remove an archive from an Amazon Glacier vault.

        :param vault: the vault name.
        :type vault: str
        :param archive: the archive ID
        :type archive: str

        :raises: GlacierWrapper.CommunicationException, GlacierWrapper.ResponseException
        """
        self._check_vault_name(vault_name)
        self._check_id(archive_id, 'ArchiveId')
        try:
            self.glacierconn.delete_archive(vault_name, archive_id)
        except boto.glacier.exceptions.UnexpectedHTTPResponseError as e:
            raise ResponseException(
                'Failed to remove archive %s from vault %s.'% (archive_id, vault_name),
                cause=self._decode_error_message(e.body),
                code=e.code)

        if self.bookkeeping:
            try:
                # TODO: can't find a method for counting right now
                # TODO: proper message for when archive name is simply not
                #       in the bookkeeping db (e.g. originally uploaded
                #       with other tool).
                #       (wvmarle: is this necessary? Archive is gone, who cares
                #       whether it was in the db to begin with.)
                query = ('select * from `%s` where archive_id="%s"' %
                            (self.bookkeeping_domain_name, archive_id))
                items = self.sdb_domain.select(query)
            except boto.exception.SDBResponseError as e:
                raise CommunicationException(
                    "Cannot get archive info from Amazon SimpleDB.",
                    code="SdbReadError",
                    cause=e)
            
            try:
                for item in items:
                    self.sdb_domain.delete_item(item)
            except boto.exception.SDBResponseError as e:
                raise CommunicationException(
                    "Cannot delete item from Amazon SimpleDB.",
                    code="SdbWriteError",
                    cause=e)

    @glacier_connect
    @sdb_connect
    @log_class_call("Requesting inventory overview.",
                    "Inventory response received.")
    def inventory(self, vault_name, refresh):
        """
        Retrieves inventory and returns retrieval job, or if it's already retrieved
        returns overview of the inventoy. If force=True it will force start a new
        inventory taking job.

        :param vault_name: Vault name
        :type vault_name: str
        :param refresh: Force new inventory retrieval.
        :type refresh: boolean

        :returns: Tuple of retrieval job and inventory data (as list) if available.
        :rtype: (list, list) ::
        
        ({u'CompletionDate': None,
          u'VaultARN':
          u'arn:aws:glacier:us-east-1:012345678901:vaults/your_vault_name',
          u'SNSTopic': None,
          u'SHA256TreeHash': None,
          u'Completed': False,
          u'InventorySizeInBytes': None,
          u'JobId': u'Example_d3tgAbCuQ9vPRqRJkD2vjNQ6wBgga7Xaw9ifwACvhjhIeKtNnZqeSIuMYRo3JUKsK_0M-VNYvb0-_Example',
          u'ArchiveId': None,
          u'JobDescription': None,
          u'StatusCode': u'InProgress',
          u'Action': u'InventoryRetrieval',
          u'CreationDate': u'2012-10-01T14:54:51.919Z',
          u'StatusMessage': None,
          u'ArchiveSizeInBytes': None},
         None)

        :raises: GlacierWrapper.CommunicationException, GlacierWrapper.ResponseException
        """

        self._check_vault_name(vault_name)
        inventory = None
        inventory_job = None
        if not refresh:

            # List active jobs and check whether any inventory retrieval
            # has been completed, and whether any is in progress. We want
            # to find the latest finished job, or that failing the latest
            # in progress job.
            job_list = self.list_jobs(vault_name)
            inventory_done = False
            for job in job_list:
                if job['Action'] == "InventoryRetrieval":

                    # As soon as a finished inventory job is found, we're done.
                    if job['Completed']:
                        self.logger.debug('Found finished inventory job %s.'% job)
                        d = dtparse(job['CompletionDate']).replace(tzinfo=pytz.utc)
                        job['inventory_date'] = d
                        inventory_done = True
                        inventory_job = job
                        break
                    
                    self.logger.debug('Found running inventory job %s.'% job)
                    inventory_job = job
                        
            # If inventory retrieval is complete, process it.
            if inventory_done:
                self.logger.debug('Fetching results of finished inventory retrieval.')
                response = self.glacierconn.get_job_output(vault_name, inventory_job['JobId'])
                inventory = response.copy()
                
                # if bookkeeping is enabled update cache
                if self.bookkeeping:
                    self.logger.debug('Updating the bookkeeping with the latest inventory.')
                    d = dtparse(inventory['InventoryDate']).replace(tzinfo=pytz.utc)
                    try:
                        self.sdb_domain.put_attributes("%s" % (d,), inventory)
                    except boto.exception.SDBResponseError as e:
                        raise CommunicationException(
                            "Cannot update inventory cache, Amazon SimpleDB is not happy.",
                            cause=e,
                            code="SdbWriteError")

        # If refresh == True or no current inventory jobs either finished or
        # in progress, we have to start a new job. Then request the job details
        # through describejob to return.
        if refresh or not inventory_job:
            self.logger.debug('No inventory jobs finished or running; starting a new job.')
            job_data = {'Type': 'inventory-retrieval'}
            try:
                new_job = self.glacierconn.initiate_job(vault_name, job_data)
            except boto.glacier.exceptions.UnexpectedHTTPResponseError as e:
                raise ResponseException(
                    'Failed to create a new inventory retrieval job for vault %s.'% vault_name,
                    cause=self._decode_error_message(e.body),
                    code=e.code)
            
            inventory_job = self.describejob(vault_name, new_job['JobId'])

        return (inventory_job, inventory)

    def get_tree_hash(self, file_name):
        """
        Calculate the tree hash of a file.

        :param file_name: the file name to calculate a hash of.
        :type file_name: str

        :returns: the tree hash of the file.
        :rtype: str
        """
        try:
            reader = open(file_name, 'rb')
        except IOError as e:
            raise InputException(
                "Could not access the file given.",
                cause=e)

        hashes = [hashlib.sha256(part).digest() for part in iter((lambda:reader.read(1024*1024)), '')]
        return glaciercorecalls.bytes_to_hex(glaciercorecalls.tree_hash(hashes))

        
    

    def __init__(self, aws_access_key, aws_secret_key, region,
                 bookkeeping=False, bookkeeping_domain_name=None,
                 logfile=None, loglevel='WARNING', logtostdout=True):
        """
        Constructor, sets up important variables and so for GlacierWrapper.
        
        :param aws_access_key: your AWS access key.
        :type aws_access_key: str
        :param aws_secret_key: your AWS secret key.
        :type aws_secret_key: str
        :param region: name of your default region.
        :type region: str
        :param bookkeeping: whether to enable bookkeeping.
        :type bookkeeping: boolean
        :param bookkeeping_domain_name: your Amazon SimpleDB domain name where the bookkeeping information will be stored.
        :type bookkeeping_domain_name: str
        :param logfile: complete file name of where to log messages.
        :type logfile: str
        :param loglevel: the desired loglevel.
        :type loglevel: str
        :param logtostdout: whether to log messages to stdout instead of to file.
        :type logtostdout: boolean
        """

        self.aws_access_key = aws_access_key
        self.aws_secret_key = aws_secret_key
        self.bookkeeping = bookkeeping
        self.bookkeeping_domain_name = bookkeeping_domain_name
        self.region = region

        self.setuplogging(logfile, loglevel, logtostdout)
        self.logger = logging.getLogger(self.__class__.__name__)

        self._check_region(region)

        self.logger.debug("""\
Creating GlacierWrapper instance with
    aws_access_key=%s,
    aws_secret_key=%s,
    bookkeeping=%r,
    bookkeeping_domain_name=%s,
    region=%s,
    logfile %s,
    loglevel %s,
    logging to stdout %s.""",
                          aws_access_key, aws_secret_key, bookkeeping,
                          bookkeeping_domain_name, region, logfile,
                          loglevel, logtostdout)
