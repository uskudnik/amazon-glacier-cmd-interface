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

from functools import wraps
from dateutil.parser import parse as dtparse
from datetime import datetime
from pprint import pformat

from glaciercorecalls import GlacierConnection, GlacierWriter
from glaciercorecalls import GlacierVault, GlacierJob
from chain_exception import CausedException

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

    class GlacierWrapperException(CausedException):
        """
        This is the common type of exception that all exceptions inherits from.
        It logs the error message (amount of information depends on the log
        level) and passes it on to a higher level to handle.

        TODO: Explain usage
        """
        
        def __init__(self, message, code=None, cause=None):
            """ Handles the exception.

            :param message: the error message.
            :type message: str
            :param code: the error code.
            :type code: 
            :param cause: explanation on what caused the error.
            :type cause: str
            """
            self.logger = logging.getLogger(self.__class__.__name__)

            if cause:
                CausedException.__init__(self, message, cause=cause)
                self.logger.error('ERROR: %s'% cause)

            else:
                CausedException.__init__(self, message)
                self.logger.error('An error occurred, exiting.')

            self.logger.info(self.fetch(message=True))
            self.logger.debug(self.fetch(stack=True))
##            raise Exception

    class InputException(GlacierWrapperException):
        """
        Exception that is raised when there is someting wrong with the
        user input.
        """
        
        VaultNameError = 1
        VaultDescriptionError = 2
        def __init__(self, message, code=None, cause=None):
            """ Handles the exception.

            :param message: the error message.
            :type message: str
            :param code: the error code.
            :type code: 
            :param cause: explanation on what caused the error.
            :type cause: str
            """

            
            GlacierWrapper.GlacierWrapperException.__init__(self, message, code=code, cause=cause)

    class ConnectionException(GlacierWrapperException):
        """
        Exception that is raised when there is something wrong with
        the connection.
        """
        
        GlacierConnectionError = 1
        SdbConnectionError = 2
        def __init__(self, message, code=None, cause=None):
            """ Handles the exception.

            :param message: the error message.
            :type message: str
            :param code: the error code.
            :type code: 
            :param cause: explanation on what caused the error.
            :type cause: str
            """
            GlacierWrapper.GlacierWrapperException.__init__(self, message, code=code, cause=cause)

    class CommunicationException(GlacierWrapperException):
        """
        Exception that is raised when there is something wrong in
        the communication with an external library like boto.
        """

        SdbReadError = 8
        SdbWriteError = 9

        def __init__(self, message, code=None, cause=None):
            """ Handles the exception.

            :param message: the error message.
            :type message: str
            :param code: the error code.
            :type code: 
            :param cause: explanation on what caused the error.
            :type cause: str
            """
            GlacierWrapper.GlacierWrapperException.__init__(self, message, code=code, cause=cause)

    class ResponseException(GlacierWrapperException):
        """
        Exception that is raised when there is an http response error.
        """
        
        # Will be removed when merge with boto
        Error_403 = 403
        def __init__(self, message, code=None, cause=None):
            GlacierWrapper.GlacierWrapperException.__init__(self, message, code=code, cause=cause)

    def setuplogging(self, logfile, loglevel, printtostdout):
        """
        Set up the logging facility. If no logging parameters are
        given, WARNING-level logging will be printed to stdout.

        :param logfile: the fully qualified file name of where to log to.
        :type logfile: str
        :param loglevel: the level of logging.
        :type loglevel: str
        :param printtostdout: whether to sent log messages to stdout.
        :type printtostdout: boolean
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
        if not loglevel in levels.keys():
            print 'Invalid loglevel; defaulting to level WARNING.'
            loglevel = 'WARNING'
        else:
            loglevel = levels[loglevel]

        datefmt = '%b %d %H:%M:%S'
        logformat = '%(asctime)s %(levelname)-8s glacier-cmd %(message)s'
        
        if logfile:
            logging.basicConfig(level=loglevel,
                                filename=logfile,
                                format=logformat,
                                datefmt=datefmt)
        
        if printtostdout or not logfile:
            soh = logging.StreamHandler(sys.stderr)
            soh.setLevel(loglevel)
            logger = logging.getLogger()
            logger.addHandler(soh)

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
                                                         region=self.region)
                except boto.exception.AWSConnectionError as e:
                    raise GlacierWrapper.ConnectionException("Cannot connect to Amazon Glacier.",
                                                             cause=e,
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

            # TODO: give SimpleDB its own class? Or move the few calls
            # we need to glaciercorecalls?
            
            if not hasattr(self, 'sdb_conn'):
                try:
                    self.logger.debug("""Connecting to Amazon SimpleDB domain %s with\   naws_access_key %s\   naws_secret_key %s""",
                                      self.bookkeeping_domain_name,
                                      self.aws_access_key,
                                      self.aws_secret_key)
                    self.sdb_conn = boto.connect_sdb(aws_access_key_id=self.aws_access_key,
                                                     aws_secret_access_key=self.aws_secret_key)
                    domain_name = self.bookkeeping_domain_name
                    self.sdb_domain = self.sdb_conn.get_domain(domain_name, validate=True)
                except boto.exception.AWSConnectionError as e:
                    raise GlacierWrapper.ConnectionException(
                        "Cannot connect to Amazon SimpleDB.",
                        cause=e,
                        code="SdbConnectionError")

                except boto.exception.SDBResponseError as e:
                    raise GlacierWrapper.ConnectionException(
                        "Cannot connect to Amazon SimpleDB.",
                        cause=e,
                        code="SdbConnectionError")
                
            return func(*args, **kwargs)

        return sdb_connect_wrap

    def _check_response(self, response):
        """
        Checks if response is correct and raise exception if it's not.

        :param response: the response as receved from Amazon.
        :type response: response

        :returns: True if valid, raises exception otherwise.
        :rtype: boolean
        :raises: GlacierWrapper.ResponseException
        """
        if response.status in [403, 404]:
            message = '%s %s\n%s'% (response.status,
                                   response.reason,
                                   json.loads(response.read())['message'])
            code = {403: ('Error_403',
                          'Forbidden - please check your credentials.'),
                    404: ('Error_404',
                          'Not found - check name and try again.')
                    }[response.status]
            raise GlacierWrapper.ResponseException(message,
                                                   code=code[0],
                                                   cause=code[1])

        self.logger.debug('Amazon response OK.')
        return True

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
            raise GlacierWrapper.InputException(
                u"Vault name can be at most %s characters long."% self.MAX_VAULT_NAME_LENGTH,
                cause='Vault name more than %s characters long.'% self.MAX_VAULT_NAME_LENGTH,
                code="VaultNameError")
        
        if len(name) == 0:
            raise GlacierWrapper.InputException(
                u"Vault name has to be at least 1 character long.",
                cause='Vault name has to be at least 1 character long.',
                code="VaultNameError")

        m = re.match(self.VAULT_NAME_ALLOWED_CHARACTERS, name)
        if m.end() != len(name):
            raise GlacierWrapper.InputException(
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
            raise GlacierWrapper.InputException(
                u"Description must be no more than %s characters."% self.MAX_VAULT_DESCRIPTION_LENGTH,
                cause='Vault description contains more than %s characters.'% self.MAX_VAULT_DESCRIPTION_LENGTH,
                code="VaultDescriptionError")

        for char in description:
            n = ord(char)
            if n < 32 or n > 126:
                raise GlacierWrapper.InputException(
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
            raise GlacierWrapper.InputException(
                'A %s must be %s characters long. This ID is %s characters.'% (id_type, length[id_type], len(amazon_id)),
                cause='Incorrect length of the %s string.'% id_type,
                code="IdError")
        
        m = re.match(self.ID_ALLOWED_CHARACTERS, amazon_id)
        if m.end() != len(amazon_id):
            raise GlacierWrapper.InputException(
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
            raise GlacierWrapper.InputException(
                "Region given is not a valid region.",
                cause='Invalid region code.',
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
        is connected to a tty (i.e. run from the command prompt),
        nothing otherwise.

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

    @glacier_connect
    @log_class_call("Listing vaults.",
                    "Listing vaults complete.")
    def lsvault(self):
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

        try:
            response = self.glacierconn.list_vaults()
        except Exception, e:
            raise GlacierWrapper.CommunicationException(
                "Problem listing vaults",
                cause=e)

        self.logger.debug('list_vaults response received.')
        self._check_response(response)
        try:
            jdata = response.read()
            vault_list = json.loads(jdata)['VaultList']
        except Exception, e:
            raise GlacierWrapper.ResponseException(
                "Problem parsing vault list: %s"% jdata,
                cause=e)
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
        :rtype: list ::
        
        [('x-amzn-requestid', 'Example_8WVoVPYabvPNT9pFLbalAtQhMzzu2Tl_Example'),
         ('date', 'Mon, 01 Oct 2012 13:24:55 GMT'),
         ('content-length', '2'),
         ('content-type', 'application/json'),
         ('location', '/335522851586/vaults/your_vault_name')]
         
        :raises: GlacierWrapper.CommunicationException
        """

        self._check_vault_name(vault_name)
        try:
            response = GlacierVault(self.glacierconn, vault_name).create_vault()
        except Exception, e:
            raise GlacierWrapper.CommunicationException(
                "Cannot create vault",
                cause=e)

        return response.getheaders()

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
            response = GlacierVault(self.glacierconn, vault_name).delete_vault()
        except Exception, e:
            raise GlacierWrapper.CommunicationException(
                "Cannot remove vault.",
                cause=e)

        return response.getheaders()

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
            gv = GlacierVault(self.glacierconn, name=vault_name)
            response = gv.describe_vault()
        except Exception, e:
            raise GlacierWrapper.CommunicationException(
                "Cannot get vault description.",
                cause=e)
                
        self._check_response(response)
        try:
            jdata = response.read()
            res = json.loads(jdata)
        except Exception, e:
            raise GlacierWrapper.CommunicationException(
                'Failed to decode response: %s'% jdata,
                cause=e)

        return res

    @glacier_connect
    @log_class_call("Requesting jobs list.",
                    "Active jobs list received.")
    def listjobs(self, vault_name):
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
          
        :raises: GlacierWrapper.CommunicationException
        """
        self._check_vault_name(vault_name)
        try:
            gv = GlacierVault(self.glacierconn, name=vault_name)
            response = gv.list_jobs()
        except Exception, e:
            raise GlacierWrapper.CommunicationException(
                "Cannot get jobs list.",
                cause=e)
        
        self._check_response(response)
        return gv.job_list

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
            gv = GlacierVault(self.glacierconn, name=vault_name)
            gj = GlacierJob(gv, job_id=job_id)
            response = gj.job_status()
        except Exception, e:
            raise GlacierWrapper.CommunicationException(
                "Cannot get jobs list.",
                cause=e)

        self._check_response(response)
        try:
            jdata = response.read()
            res = json.loads(jdata)
        except Exception, e:
            raise GlacierWrapper.CommunicationException(
                'Failed to decode response: %s'% jdata,
                cause=e)

        return res

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
            gv = GlacierVault(self.glacierconn, name=vault_name)
            response = gv.abort_multipart(upload_id)
        except Exception, e:
            raise GlacierWrapper.CommunicationException(
                "Cannot abort multipart upload.",
                cause=e)
        
        self._check_response(response)
        return response.getheaders()
    
    @glacier_connect
    @log_class_call("Listing multipart uploads.",
                    "Multipart uploads list received successfully.")
    def listmultiparts(self, vault_name):
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
        try:
            gv = GlacierVault(self.glacierconn, name=vault_name)
            response = gv.list_multipart_uploads()
        except Exception, e:
            raise GlacierWrapper.CommunicationException("Cannot abort multipart upload.",
                                                        cause=e)
        self._check_response(response)
        try:
            jdata = response.read()
            res = json.loads(jdata)
        except Exception, e:
            raise GlacierWrapper.CommunicationException(
                'Failed to decode response: %s'% jdata,
                cause=e)

        if res.has_key('UploadsList'):
            res = res['UploadsList']

        else:
            res = None

        return res

    @glacier_connect
    @sdb_connect
    @log_class_call("Uploading archive.",
                    "Upload of archive finished.")
    def upload(self, vault_name, file_name, description, region, stdin, part_size):

        if description:
            description = " ".join(description)
        else:
            description = file_name

        self._check_vault_description(description) # ???file description same restrictions???
        self._check_vault_name(vault_name)
        
        reader = None

        # If filename is given, try to use this file.
        # Otherwise try to read data from stdin.
        total_size = 0
        if not stdin:
            try:
                reader = open(file_name, 'rb')
                total_size = os.path.getsize(file_name)
            except IOError, e:
                raise GlacierWrapper.InputException("Couldn't access the file given.",
                                                    cause=e)
            
        elif select.select([sys.stdin,],[],[],0.0)[0]:
            reader = sys.stdin
            total_size = 0
        else:
            print "Nothing to upload."
            return False

        if part_size < 0:
            
            # User did not specify part_size. Compute the optimal value.
            if total_size > 0:
                part_size = self._next_power_of_2(total_size / (1024*1024*self.MAX_PARTS))
            else:
                part_size = GlacierWriter.DEFAULT_PART_SIZE / 1024 / 1024
                
        else:
            part_size = self._next_power_of_2(part_size)

        if total_size > part_size*1024*1024*self.MAX_PARTS:
            
            # User specified a value that is too small. Adjust.
            part_size = self._next_power_of_2(total_size / (1024*1024*self.MAX_PARTS))
            print "WARNING: Part size given is too small; using %s MB parts to upload."% part_size

        read_part_size = part_size * 1024 * 1024
        writer = GlacierWriter(self.glacierconn, vault_name, description=description,
                               part_size=read_part_size)

        # Read file in parts so we don't fill the whole memory.
        start_time = current_time = previous_time = time.time()
        for part in iter((lambda:reader.read(read_part_size)), ''):

            writer.write(part)
            current_time = time.time()
            overall_rate = int(writer.uploaded_size/(current_time - start_time))
            if total_size > 0:
                
                # Calculate transfer rates in bytes per second.
                current_rate = int(read_part_size/(current_time - previous_time))

                # Estimate finish time, based on overall transfer rate.
                if overall_rate > 0:
                    time_left = (total_size - writer.uploaded_size)/overall_rate
                    eta = time.strftime("%H:%M:%S", time.localtime(current_time + time_left))
                else:
                    time_left = "Unknown"
                    eta = "Unknown"

                self._progress('\rWrote %s of %s (%s%%). Rate %s/s, average %s/s, eta %s.' %
                               (self._size_fmt(writer.uploaded_size),
                                self._size_fmt(total_size),
                                int(100 * writer.uploaded_size/total_size),
                                self._size_fmt(current_rate, 2),
                                self._size_fmt(overall_rate, 2),
                                eta))

            else:
                self._progress('\rWrote %s. Rate %s/s.' %
                               (self._size_fmt(writer.uploaded_size),
                                self._size_fmt(overall_rate, 2)))

            previous_time = current_time

        writer.close()
        current_time = time.time()
        overall_rate = int(writer.uploaded_size/(current_time - start_time))
        self._progress('\rWrote %s. Rate %s/s.\n' %
                       (self._size_fmt(writer.uploaded_size),
                        self._size_fmt(overall_rate, 2)))

        archive_id = writer.get_archive_id()
        location = writer.get_location()
        sha256hash = writer.get_hash()

        if self.bookkeeping:
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

            if file_name:
                file_attrs['filename'] = file_name
            elif stdin:
                file_attrs['filename'] = description

            self.sdb_domain.put_attributes(file_attrs['filename'], file_attrs)

        print "Created archive with ID: ", archive_id
        print "Archive SHA256 tree hash: ", sha256hash


    @glacier_connect
    @log_class_call("Processing archive retrieval job.",
                    "Archive retrieval job response received.")
    def getarchive(self, vault, archive):
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

        :returns: Tuple of Vault job and Glacier job
                  TODO: Return example
        :rtype: (json, json)
        """

        results = None
        self._check_vault_name(vault)
        self._check_id(archive, 'ArchiveId')
            
##        else:
##            if file_name:
##                results = search(file_name=file_name)
##            elif search_term:
##                results = search(search_term=search_term)
##            else:
##                raise GlacierWrapper.InputException(
##                    "Must provide at least one of archive ID, a file name or a search term.")
##
##            if len(results) == 0:
##                raise GlacierWrapper.InputException(
##                    "No results.")
##
##            if len(results) > 1:
##                raise GlacierWrapper.InputException(
##                    "Too many results; please narrow down your search terms.")
##
##            archive = results[0]['archive_id']

        # We have a unique result; check whether we have a retrieval job
        # running for it.
        job_list = self.listjobs(vault)
        for job in job_list:
            try:
                if job['ArchiveId'] == archive:
                    
                    # no need to start another archive retrieval
                    if not job['Completed']:
                        return ('running', job, None, results)
                    
                    if job['Completed']:
                        job2 = GlacierJob(gv, job_id=job['JobId'])
                        return ('ready', job, job2, results)
                    
            except Exception, e:
                GlacierWrapper.ResponseException(
                    "Cannot process job list response.",
                    cause=e)

        # No job found related to this archive, start a new job.        
        try:
            job = gv.retrieve_archive(archive)
        except Exception, e:
            raise GlacierWrapper.CommunicationException(
                "Cannot retrieve archive.",
                cause=e,
                code="ArchiveRetrieveError")
        return ("initiated", job, None, results)

    @glacier_connect
    @sdb_connect
    @log_class_call("Download an archive.",
                    "Download archive done.")
    def download(self, vault, archive, out_file=None, overwrite=False):
        """
        Download a file from Glacier, and store it in out_file.
        If no out_file is given, the file will be dumped on stdout.
        """

        # Sanity checking on the input.
        self._check_vault_name(vault)
        self._check_id(archive, 'ArchiveId')

        # Check whether the requested file is available from Amazon Glacier.
        gv = GlacierVault(self.glacierconn, vault)
        job_list = self.listjobs(vault)
        for job in job_list:
            if job['ArchiveId'] == archive:
                if not job['Completed']:
                    raise GlacierWrapper.CommunicationException(
                        "Archive retrieval request not completed yet. Please try again later.")
                self.logger.debug('Archive retrieval completed; archive is available for download now.')
                break
            
        else:
            raise GlacierWrapper.InputException(
                "Requested archive not available. Please make sure \
your archive ID is correct, and start a retrieval job using \
'getarchive' if necessary.")

        # Check whether we can access the file the archive has to be written to.
        if out_file:
            if os.path.isfile(out_file) and not overwrite:
                raise GlacierWrapper.InputException(
                    "File exists already, aborting. Use the overwrite flag to overwrite existing file.",
                    code="FileError")
            try:
                out = open(out_file, 'w')
            except Exception, e:
                raise GlacierWrapper.InputException(
                    "Cannot access the ouput file.",
                    cause=e,
                    code="FileError")

        job2 = GlacierJob(gv, job_id=job['JobId'])
        if out_file:
            self.logger.debug('Starting download of archive to file %s.'% out_file)
            ffile = open(out_file, "w")
            ffile.write(job2.get_output().read())
            ffile.close()
            self.logger.debug('Download of archive finished.')

            #TODO: tree-hash check.
            return 'File download successful.'
        
        else:
            self.logger.debug('Downloading archive and sending output to stdout.')
            print job2.get_output().read(),

    @glacier_connect
    @sdb_connect
    @log_class_call("Searching for archive.",
                    "Search done.")
    def search(self, vault=None, region=None, file_name=None, search_term=None, print_results=False):

        # Sanity checking.
        if not self.bookkeeping:
            raise Exception(
                u"You must enable bookkeeping to be able to do searches.")

        if region:
            self._check_region(region)

        if file_name:
            file_name = re.escape(file_name)
            
        if search_term:
            search_term = re.escape(search_term)

        search_params = []
        table_title = ''
        if region:
            search_params += ["region='%s'" % (region,)]
        else:
            table_title += "Region\t"

        if vault:
            search_params += ["vault='%s'" % (vault,)]
        else:
            table_title += "Vault\t"

        table_title += "Filename\tArchive ID"

        if file_name:
            search_params += ["filename like '"+ file_name+"%'" ]
            
        if search_term:
            search_params += ["description like '"+search_term+"%'" ]

        search_params = " and ".join(search_params)
        query = 'select * from `%s` where %s' % (self.bookkeeping_domain_name, search_params)
        items = self.sdb_domain.select(query)

        if print_results:
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
            if print_results:
                print "\t".join(item_attrs)

        if not print_results:
            return items

    @glacier_connect
    @sdb_connect
    @log_class_call("Deleting archive.", "Archive deleted.")
    def rmarchive(self, vault, archive):
        """
        Remove an archive from an Amazon Glacier vault.

        :param vault: the vault name.
        :type vault: str
        :param archive: the archive ID
        :type archive: str

        :raises: GlacierWrapper.CommunicationException
        """
        self._check_vault_name(vault)
        self._check_id(archive, 'ArchiveId')
               
        try:
            gv = GlacierVault(self.glacierconn, vault)
            self._check_response(gv.delete_archive(archive))
        except Exception, e:
            raise GlacierWrapper.CommunicationException("Cannot delete archive.",
                                                        code="ArchiveDeleteError",
                                                        cause=e)

        if self.bookkeeping:
            try:
                # TODO: can't find a method for counting right now
                # TODO: proper message for when archive name is simply not in the
                #       bookkeeping db (e.g. originally uploaded with other tool).
                query = ('select * from `%s` where archive_id="%s"' %
                            (self.bookkeeping_domain_name, archive))
                items = self.sdb_domain.select(query)
            except boto.exception.SDBResponseError as e:
                raise GlacierWrapper.CommunicationException("Cannot get archive info from Amazon SimpleDB.",
                                                            code="SdbReadError",
                                                            cause=e)
            
            try:
                for item in items:
                    self.sdb_domain.delete_item(item)
            except boto.exception.SDBResponseError as e:
                raise GlacierWrapper.CommunicationException("Cannot delete item from Amazon SimpleDB.",
                                                            code="SdbWriteError",
                                                            cause=e)


    @glacier_connect
    @sdb_connect
    @log_class_call("Requesting inventory overview.",
                    "Inventory response received.")
    def inventory(self, vault_name, force_start):
        """
        Retrieves inventory and returns retrieval job, or if it's already retrieved
        returns overview of the inventoy. If force=True it will force start a new
        inventory taking job.

        :param vault_name: Vault name
        :type vault_name: str
        :param force_start: Force new inventory retrieval.
        :type force_start: boolean

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
        gv = GlacierVault(self.glacierconn, vault_name)
        
        # List active jobs and check whether inventory any inventory retrieval
        # has been completed, and whether any is in progress.
        inventory = None
        inventory_retrievals_done = []
        inventory_retrievals_in_progress = []
        if not force_start:
            job_list = self.listjobs(vault_name)
            for job in job_list:
                try:

                    # Finished jobs.
                    if job['Action'] == "InventoryRetrieval" and \
                       job['StatusCode'] == "Succeeded":
                        d = dtparse(job['CompletionDate']).replace(tzinfo=pytz.utc)
                        job['inventory_date'] = d
                        inventory_retrievals_done += [job]
                        self.logger.debug('Found finished inventory job %s.'% job)

                    # Running jobs.
                    elif job['Action'] == "InventoryRetrieval" and \
                       job['StatusCode'] == "InProgress":
                        inventory_retrievals_in_progress += [job]
                        self.logger.debug('Found running inventory job %s.'% job)
                        
                except Exception, e:
                    raise GlacierWrapper.ResponseException("Cannot process returned job list.",
                                                           cause=e,
                                                           code="JobListError")

            # If inventory retrieval is complete, process it.
            # It is possible there were multiple jobs; use the last one.
            if len(inventory_retrievals_done):
                self.logger.debug('Fetching results of finished inventory retrieval.')
                try:
                    list.sort(inventory_retrievals_done,
                            key=lambda i: i['inventory_date'], reverse=True)
                    job = inventory_retrievals_done[-1]
                    job = GlacierJob(gv, job_id=job['JobId'])
                    inventory = json.loads(job.get_output().read())
                except Exception, e:
                    raise GlacierWrapper.ResponseException("Cannot process completed job.",
                                                           cause=e,
                                                           code="JobListError")

                # if bookkeeping is enabled update cache
                if self.bookkeeping:
                    self.logger.debug('Updating the bookkeeping with the latest inventory.')
                    d = dtparse(inventory['InventoryDate']).replace(tzinfo=pytz.utc)
                    try:
                        self.sdb_domain.put_attributes("%s" % (d,), inventory)
                    except boto.exception.SDBResponseError as e:
                        raise GlacierWrapper.CommunicationException("Cannot update inventory cache, Amazon SimpleDB is not happy.",
                                                                    cause=e,
                                                                    code="SdbWriteError")

                    if ((datetime.utcnow().replace(tzinfo=pytz.utc) - d).days > 1):
                        try:
                            gv.retrieve_inventory(format="JSON")
                        except Exception, e:
                            raise GlacierWrapper.CommunicationException(r_ex,
                                                                        cause=e,
                                                                        code="InventoryRetrieveError")

        # If force_start == True or no current inventory jobs either finished or
        # in progress, we have to start a new job. Then request the job details
        # through describejob to return.
        if force_start or (not inventory_retrievals_in_progress and not inventory_retrievals_done):
            self.logger.debug('No inventory jobs finished or running; starting a new job.')
            try:
                job = gv.retrieve_inventory(format="JSON")
            except Exception, e:
                raise GlacierWrapper.CommunicationException(r_ex,
                                                            cause=e,
                                                            code="InventoryRetrieveError")
            job = self.describejob(vault_name, job.job_id)

        return (job, inventory)
    

    def __init__(self, aws_access_key, aws_secret_key, region,
                 bookkeeping=False, bookkeeping_domain_name=None,
                 logfile=None, loglevel='WARNING', printtostdout=True):
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
        :param printtostdout: whether to print messages to stdout.
        :type printtostdout: boolean
        """
        
        self.aws_access_key = aws_access_key
        self.aws_secret_key = aws_secret_key
        self.bookkeeping = bookkeeping
        self.bookkeeping_domain_name = bookkeeping_domain_name
        self.region = region

        self.setuplogging(logfile, loglevel, printtostdout)
        self.logger = logging.getLogger(self.__class__.__name__)

        self.logger.debug("""Creating GlacierWrapper instance with aws_access_key=%s, \
        aws_secret_key=%s, bookkeeping=%r, bookkeeping_domain_name=%s, region=%s, \
        logfile %s, loglevel %s.""",
                          aws_access_key, aws_secret_key, bookkeeping,
                          bookkeeping_domain_name, region, logfile,
                          loglevel)
