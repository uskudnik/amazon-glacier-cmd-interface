# -*- coding: utf-8 -*-
"""
.. module:: GlacierWrapper
   :platform: Unix, Windows
   :synopsis: Wrapper for glacier, with amazon sdb support and other features.
"""

import json
import pytz
import re
import logging
import boto

from functools import wraps
from dateutil.parser import parse as dtparse
from datetime import datetime
from pprint import pformat

from glaciercorecalls import GlacierConnection, GlacierWriter
from glaciercorecalls import GlacierVault, GlacierJob
from chain_exception import CausedException

class log_class_call(object):
    """
    Decorator that logs class calls to specific functions
    """

    def __init__(self, start, finish, getter=None):
        """
        Decorator constructor.

        :param enter: Message logged when starting the class.
        :type enter: str
        :param getout: Message logged when finishing the class.
        :type getout: str
        """
        
        self.start = start
        self.finish = finish
        self.getter = getter

    def __call__(self, fn):
        def wrapper(*args, **kwargs):
            that = args[0]
            that.logger.info(self.start)
            ret = fn(*args, **kwargs)
            that.logger.info(self.finish)
            if self.getter:
                that.logger.info(pformat(self.getter(ret)))
            else:
                that.logger.info(pformat(ret))

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
    Wrapper for glacier, with amazon sdb support and other features.
    """

    VAULT_NAME_ALLOWED_CHARACTERS = "[a-zA-Z\.\-\_0-9]+"
    MAX_VAULT_NAME_LENGTH = 255
    MAX_VAULT_DESCRIPTION_LENGTH = 1024

    class GlacierWrapperException(CausedException):
        """
        This is common type of exception that all exceptions inherits from

        TODO: Explain usage
        """
        
        def __init__(self, message, code=None, cause=None):
            if not cause:
                CausedException.__init__(self, message)
            else:
                CausedException.__init__(self, message, cause=cause)

            if isinstance(code, basestring):
                self.code = getattr(self, code, None)
            else:
                self.code = code

    class InputException(GlacierWrapperException):
        """
        Exception that is raised when there is someting wrong with input data.
        """
        
        VaultNameError = 1
        VaultDescriptionError = 2
        def __init__(self, message, code=None, cause=None):
            GlacierWrapper.GlacierWrapperException.__init__(self, message, code, cause)

    class ConnectionException(GlacierWrapperException):
        """
        Exception that is raised when there is something wrong with the connection.
        """
        
        GlacierConnectionError = 1
        SdbConnectionError = 2
        def __init__(self, message, code=None, cause=None):
                GlacierWrapper.GlacierWrapperException.__init__(self, message, code, cause)

    class CommunicationException(GlacierWrapperException):
        """
        Exception that is raised when there is something wrong in the communication
        with an external library like boto.
        """

        SdbReadError = 8
        SdbWriteError = 9

        def __init__(self, message, code=None, cause=None):
                GlacierWrapper.GlacierWrapperException.__init__(self, message, code, cause)

    class ResponseException(GlacierWrapperException):
        """
        Exception that is raised when there is an http response error.
        """
        
        # Will be removed when merge with boto
        Error_403 = 403
        def __init__(self, message, code=None, cause=None):
                GlacierWrapper.GlacierWrapperException.__init__(self, message, code, cause)


    def glacier_connect(func):
        """
        Decorator which connects to glacier

        :param func: Function to wrap
        :type func: function

        :returns: wrapper function
        :rtype: function
        """

        @wraps(func)
        def glacier_connect_wrap(*args, **kwargs):
            self = args[0]
            if not hasattr(self, "glacierconn") or \
                (hasattr(self, "glacierconn") and not self.glacierconn):
                try:
                    self.logger.debug("""Connecting to Amazon Glacier with \naws_access_key %s\naws_secret_key %s\nregion %s""",
                                      self.aws_access_key,
                                      self.aws_access_key,
                                      self.region)
                    self.glacierconn = GlacierConnection(self.aws_access_key,
                                                         self.aws_secret_key,
                                                         region=self.region)
                except:
                    self.logger.debug("Connection to Amazon Glacier failed.")
                    raise GlacierWrapper.ConnectionException("Cannot connect to Amazon Glacier.",
                                                             code="GlacierConnectionError")

                self.logger.debug("Successfully connected to Amazon Glacier.")
            return func(*args, **kwargs)
        return glacier_connect_wrap

    def sdb_connect(func):
        """
        Decorator which connects to Amazon SimpleDB.

        :param func: Function to wrap
        :type func: function

        :returns: wrapper function
        :rtype: function
        """

        @wraps(func)
        def sdb_connect_wrap(*args, **kwargs):
            self = args[0]
            
            if not self.sdb_conn:
                try:
                    self.logger.debug("""Connecting to Amazon SimpleDB with\naws_access_key %s\naws_secret_key %s""",
                                      self.aws_access_key,
                                      self.aws_access_key)
                    self.sdb_conn = boto.connect_sdb(aws_access_key_id=self.aws_access_key,
                                                     aws_secret_access_key=self.aws_secret_key)
                    domain_name = self.bookkeeping_domain_name
                    self.sdb_domain = self.sdb_conn.get_domain(domain_name, validate=True)
                except boto.exception.AWSConnectionError as e:
                    self.debugger.log("Failed to connect to Amazon SimpleDB. Error: %s"% e)
                    raise GlacierWrapper.ConnectionException("Cannot connect to Amazon SimpleDB.",
                                                             cause=e,
                                                             code="SdbConnectionError")

                self.debugger.log("Succesfully connected to Amazon SimpleDB.")
            return func(*args, **kwargs)

        return sdb_connect_wrap

    def _check_response(self, response):
        """
        Checks if response is correct and raise exception if it's not.

        :param response: a
        :type response: a

        :returns : a
        :rtype: a
        """
        if response.status == 403:
            raise GlacierWrapper.ResponseException("403 Forbidden " + response.read() + response.msg,
                                                   code="Error_403")

        if response.status == 404:
            raise GlacierWrapper.ResponseException("404 Not found " + response.read() + response.msg,
                                                   code="Error_404")

    def _check_vault_name(self, name):
        """
        Checks whether we have a valid vault name.

        :param name: Vault name
        :type name: str

        :returns: True if it's valid, false otherwise
        :rtype: boolean
        """

        m = re.match(self.VAULT_NAME_ALLOWED_CHARACTERS, name)
        if len(name) > self.MAX_VAULT_NAME_LENGTH:
            ex= u"Vault name can be at most %s characters long."% self.MAX_VAULT_NAME_LENGTH,
            raise GlacierWrapper.InputException(ex, code="VaultNameError")
        
        if len(name) == 0:
            ex= u"Vault name has to be at least 1 character long."
            raise GlacierWrapper.InputException(ex, code="VaultNameError")

        if m.end() != len(name):
            ex= u"""Allowed characters are a¿z, A¿Z, 0¿9, '_' (underscore), '-' (hyphen), and '.' (period)"""
            raise GlacierWrapper.InputException(ex, code="VaultNameError")
        
        return True

    def _check_vault_description(self, description):
        """
        Checks if vault description is valid.

        :param description: Vault sescription
        :type description: str

        :returns: True if correct, false otherwise
        :rtype: boolean
        """

        if len(description) > self.MAX_VAULT_DESCRIPTION_LENGTH:
            ex= u"Description must be less or equal to %s characters."% self.MAX_VAULT_DESCRIPTION_LENGTH,
            raise GlacierWrapper.InputException(ex, code="VaultDescriptionError")

        for char in description:
            n = ord(char)
            if n < 32 or n > 126:
                ex= u"""The allowed characters are 7-bit ASCII without control codes, \
specifically ASCII values 32¿126 decimal or 0x20¿0x7E hexadecimal.""",
                raise GlacierWrapper.InputException(ex, code="VaultDescriptionError")
        return True

    @glacier_connect
    @log_class_call("Listing vaults.", "Listing vaults complete.")
    def lsvault(self):
        """
        Lists available vaults.

        :returns : Vault list
                   TODO: Return value example
        :rtype: json
        """

        try:
            response = self.glacierconn.list_vaults()
        except Exception, e:
            raise GlacierWrapper.CommunicationException("Problem listing vaults",
                                                        cause=e)

        self._check_response(response)
        try:
            jdata = json.loads(response.read())
            vault_list = jdata['VaultList']
        except Exception, e:
            raise GlacierWrapper.ResponseException("Problem parsing vault list",
                                                   cause=e)

        return vault_list

    @glacier_connect
    @log_class_call("Creating vault.", "Vault creation completed.")
    def mkvault(self, vault_name):
        """
        Creates new vault.

        :param vault_name: Name of newly created vault.
        :type vault_name: str

        :returns: Response data.
                  TODO: Return value example.
        :rtype: str
        """

        if self._check_vault_name(vault_name):
            try:
                response = GlacierVault(self.glacierconn, vault_name).create_vault()
            except Exception, e:
                raise GlacierWrapper.CommunicationException("Cannot create vault",
                                                            cause=e)
            self._check_response(response)

            return response.getheaders()

    @glacier_connect
    @log_class_call("Removing vault.", "Vault removal complete.")
    def rmvault(self, vault_name):
        """
        Removes a vault.

        :param vault_name: Name of vault to be removed.
        :type vault_name: str

        :returns: Response data
                  TODO: Return value example
        :rtype: str
        """

        if self._check_vault_name(vault_name):
            try:
                response = GlacierVault(self.glacierconn, vault_name).delete_vault()
            except Exception, e:
                raise GlacierWrapper.CommunicationException("Cannot remove vault.",
                                                            cause=e)
            self._check_response(response)

            return response.getheaders()

    @glacier_connect
    @log_class_call("Requesting vault description.", "Vault description received.")
    def describevault(self, vault_name):
        """
        Describes vault inventory and other details.

        :param vault_name: Name of vault.
        :type vault_name: str

        :returns: List of jobs
                  TODO: Return value example.
        :rtype: json
        """

        if self._check_vault_name(vault_name):
            try:
                gv = GlacierVault(self.glacierconn, name=vault_name)
                response = gv.describe_vault()
            except Exception, e:
                raise GlacierWrapper.CommunicationException("Cannot get vault description.",
                                                            cause=e)
            self._check_response(response)

            jdata = json.loads(response.read())
            return jdata

    @glacier_connect
    @log_class_call("Requesting jobs list.", "Active jobs list received.")
    def listjobs(self, vault_name):
        if self._check_vault_name(vault_name):
            try:
                gv = GlacierVault(self.glacierconn, name=vault_name)
                response = gv.list_jobs()
            except Exception, e:
                raise GlacierWrapper.CommunicationException("Cannot get jobs list.",
                                                            cause=e)
            self._check_response(response)

            return (response.getheaders(), gv.job_list)

    @glacier_connect
    @log_class_call("Aborting multipart upload.", "Multipart upload successfully aborted.")
    def abortmultipart(self, vault_name, upload_id):
        if self._check_vault_name(vault_name):
            try:
                gv = GlacierVault(self.glacierconn, name=vault_name)
                response = gv.abort_multipart(upload_id)
            except Exception, e:
                raise GlacierWrapper.CommunicationException("Cannot abort multipart upload.",
                                                            cause=e)
            self._check_response(response)

            return response.getheaders()

    @glacier_connect
    @log_class_call("Retrieving archive.", "Archive retrieval job response received.")
    def getarchive(self, vault, archive):
        """
        Gets archive

        If retrieval job is not yet initiated: initiate a job, return tuple (job status, None)
        If retrieval job is already initiated: return tuple (job status, None).
        If the file is ready for download: return tuple (status, GlacierJob).

        :param vault: Vault name from where we want to retrieve the archive.
        :type vault: str
        :param archive: ArchiveID of archive to be retrieved.
        :type archive: str

        :returns: Tuple of Vault job and Glacier job
                  TODO: Return example
        :rtype: (json, json)
        """

        try:
            gv = GlacierVault(self.glacierconn, vault)
            gv.list_jobs()
        except Exception, e:
             raise GlacierWrapper.CommunicationException("Cannot get jobs list.",
                                                         cause=e,
                                                         code="JobListError")

        for job in gv.job_list:
            try:
                if job['ArchiveId'] == archive:
                    
                    # no need to start another archive retrieval
                    if not job['Completed']:
                        return (job, None)
                    
                    if job['Completed']:
                        job2 = GlacierJob(gv, job_id=job['JobId'])
                        return (job, job2)
                    
            except Exception, e:
                GlacierWrapper.ResponseException("Cannot process job list response.",
                                                 cause=e)

        try:
            job = gv.retrieve_archive(archive)
        except Exception, e:
            raise GlacierWrapper.CommunicationException("Cannot retrieve archive",
                                                        cause=e,
                                                        code="ArchiveRetrieveError")
        return (job, None)

    @glacier_connect
    @sdb_connect
    @log_class_call("Deleting archive.", "Archive deleted.")
    def deletearchive(self, vault, archive):
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
    @log_class_call("Requesting inventory overview.", "Inventory response received.")
    def inventory(self, vault, force):
        """
        Retrieves inventory and returns retrieval job, or if it's already retrieved
        returns overview of the inventoy.

        :param vault: Vault name
        :type vault: str
        :param force: Force new inventory retrieval.
        :type force: boolean

        :returns: Tuple of retrieval job and inventory data if available.
                  TODO: Return example
        :rtype: (json, json)
        """

        r_ex= "Cannot retrieve inventory."

        gv = GlacierVault(self.glacierconn, vault)
        
        # Force inventory retrieval, even if it's already complete.
        if force:
            try:
                job = gv.retrieve_inventory(format="JSON")
            except Exception, e:
                raise GlacierWrapper.CommunicationException(r_ex,
                                                            cause=e,
                                                            code="InventoryRetrieveError")

            return (job, None)

        # List active jobs and check if inventory retrieval is complete
        try:
            gv.list_jobs()
        except Exception, e:
            raise GlacierWrapper.CommunicationException("Cannot get jobs list.",
                                                        cause=e,
                                                        code="JobListError")
        
        inventory= None
        inventory_retrievals_done = []
        for job in gv.job_list:
            try:
                if job['Action'] == "InventoryRetrieval" and \
                   job['StatusCode'] == "Succeeded":
                    d = dtparse(job['CompletionDate']).replace(tzinfo=pytz.utc)
                    job['inventory_date'] = d
                    inventory_retrievals_done += [job]
            except Exception, e:
                raise GlacierWrapper.ResponseException("Cannot process returned job list.",
                                                       cause=e,
                                                       code="JobListError")

        # If inventory retrieval is complete, process it
        if len(inventory_retrievals_done):
            try:
                list.sort(inventory_retrievals_done,
                        key=lambda i: i['inventory_date'], reverse=True)
                job = inventory_retrievals_done[0]
                job = GlacierJob(gv, job_id=job['JobId'])
                inventory = json.loads(job.get_output().read())
            except Exception, e:
                raise GlacierWrapper.ResponseException("Cannot process completed job.",
                                                       cause=e,
                                                       code="JobListError")

            # if bookkeeping is enabled update cache
            if self.bookkeeping:
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
        
        else:
            try:
                job = gv.retrieve_inventory(format="JSON")
            except Exception, e:
                raise GlacierWrapper.CommunicationException(r_ex,
                                                            cause=e,
                                                            code="InventoryRetrieveError")

        return (job, inventory)
    

    def __init__(self, aws_access_key, aws_secret_key, region,
                 bookkeeping=None, bookkeeping_domain_name=None):
        self.logger = logging.getLogger(self.__class__.__name__)

        self.logger.debug("""Creating GlacierWrapper with aws_access_key=%s, \
aws_secret_key=%s, bookkeeping=%r, bookkeeping_domain_name=%s, region=%s.""",
                          aws_access_key, aws_secret_key, bookkeeping,
                          bookkeeping_domain_name, region)
        self.aws_access_key = aws_access_key
        self.aws_secret_key = aws_secret_key
        self.bookkeeping = bookkeeping
        self.bookkeeping_domain_name = bookkeeping_domain_name
        self.region = region
        
