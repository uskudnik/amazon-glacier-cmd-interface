# -*- coding: utf-8 -*-
"""
.. module:: GlacierWrapper
   :platform: Unix, Windows
   :synopsis: Wrapper for glacier, with amazon sdb support and other features
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
    Decorator that logs class call to speciffic function
    """

    def __init__(self, enter, exit, getter=None):
        """
        Decorator constructor

        :param enter: Message to display on class enter
        :type enter: str
        :param exit: Message to display on class exit
        :type exit: str
        """
        self.enter = enter
        self.exit = exit
        self.getter = getter

    def __call__(self, fn):
        def wrapper(*args, **kwargs):
            that= args[0]

            that.logger.info(self.enter)
            ret= fn(*args,**kwargs)
            that.logger.info(self.exit)
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
    Wrapper for glacier, with amazon sdb support and other features
    """

    VAULT_NAME_ALLOWED_CHARACTERS = "[a-zA-Z\.\-\_0-9]+"
    MAX_VAULT_NAME_LENGTH = 255

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
                self.code= getattr(self, code, None)
            else:
                self.code= code

    class InputException(GlacierWrapperException):
        """
        Exception that is raised when there is someting wrong with input data
        """
        VaultNameError= 1
        VaultDescriptionError= 2
        def __init__(self, message, code=None, cause=None):
            GlacierWrapper.GlacierWrapperException.__init__(self, message, code, cause)

    class ConnectionException(GlacierWrapperException):
        """
        Exception that is raised when there is something wrong with connection
        """
        GlacierConnectionError=1
        SdbConnectionError=2
        def __init__(self, message, code=None, cause=None):
                GlacierWrapper.GlacierWrapperException.__init__(self, message, code, cause)

    class CommunicationException(GlacierWrapperException):
        """
        Exception that is raised when there is something wrong with communication
        with external library like boto
        """

        SdbReadError= 8
        SdbWriteError= 9

        def __init__(self, message, code=None, cause=None):
                GlacierWrapper.GlacierWrapperException.__init__(self, message, code, cause)

    class ResponseException(GlacierWrapperException):
        """
        Exception that is raised when there is something wrong with response
        or processing it
        """
        # Will be removed when merge with boto
        Error_403= 403
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
            self= args[0]

            if not hasattr(self,"glacierconn") or \
                (hasattr(self,"glacierconn") and not self.glacierconn):
                try:
                    self.logger.debug("""Connecting to glacier with
                                         aws_access_key %s
                                         aws_secret_key %s
                                         region %s""", self.aws_access_key,
                                                       self.aws_access_key,
                                                       self.region)
                    self.glacierconn = GlacierConnection(self.aws_access_key,
                                                         self.aws_secret_key,
                                                         region=self.region)
                except:
                    raise GlacierWrapper.ConnectionException("Cannot connect to glacier",
                                                code="GlacierConnectionError")

                self.logger.debug("Sucesfully connected to glacier!")
            return func(*args, **kwargs)
        return glacier_connect_wrap

    def sdb_connect(func):
        """
        Decorator which connects to simpleDB, and creates new domain if it
        does not exist yet

        :param func: Function to wrap
        :type func: function

        :returns : wrapper function
        :rtype: function
        """

        @wraps(func)
        def sdb_connect_wrap(*args, **kwargs):
            self= args[0]

            if not self.sdb_conn:
                try:
                    self.logger.debug("""Connecting to sdb with
                                         aws_access_key %s
                                         aws_secret_key %s""",
                                                       self.aws_access_key,
                                                       self.aws_access_key)
                    self.sdb_conn = boto.connect_sdb(aws_access_key_id=self.aws_access_key,
                                        aws_secret_access_key=self.aws_secret_key)
                    domain_name = self.bookkeeping_domain_name
                    self.sdb_domain = self.sdb_conn.get_domain(domain_name, validate=True)
                except boto.exception.AWSConnectionError as e:
                    raise GlacierWrapper.ConnectionException("Cannot connect to sdb",
                                        cause=e, code="SdbConnectionError")

                self.debugger.log("Succesfully connected to sdb")
            return func(*args, **kwargs)

        return sdb_connect_wrap

    def _check_response(self, response):
        """
        Checks if response is correct and raises exception if it's not

        :param response: a
        :type response: a

        :returns : a
        :rtype: a
        """
        if response.status == 403:
            raise GlacierWrapper.ResponseExceptiion("403 Forbidden "
                                              + response.read() + response.msg,
                                               code="Error_403")


    def _check_vault_name(self, name):
        """
        Checks if vault name is correct

        :param name: Vault name
        :type name: str

        :returns: True if it's correct, false otherwise
        :rtype: boolean
        """

        m = re.match(self.VAULT_NAME_ALLOWED_CHARACTERS, name)
        if len(name) > self.MAX_VAULT_NAME_LENGTH:
            ex= u"Vault name can be at most 255 charecters long.",
            raise GlacierWrapper.InputException(ex, code="VaultNameError")
        if len(name) == 0:
            ex= u"Vault name has to be at least 1 character long."
            raise GlacierWrapper.InputException(ex, code="VaultNameError")
        if m.end() != len(name):
            ex= u"""Allowed characters are a¿z, A¿Z, 0¿9, '_' (underscore),
                 '-' (hyphen), and '.' (period)"""
            raise GlacierWrapper.InputException(ex, code="VaultNameError")
        return True

    def _check_vault_description(self, description):
        """
        Checks if vault description is correct

        :param description: Vault sescription
        :type description: str

        :returns: True if correct, false otherwise
        :rtype: boolean
        """

        if len(description) > 1024:
            ex= u"Description must be less or equal to 1024 characters.",
            raise GlacierWrapper.InputException(ex, code="VaultDescriptionError")

        for char in description:
            n = ord(char)
            if n < 32 or n > 126:
                ex= """u"The allowable characters  are 7-bit ASCII without control
                       codes, specifically ASCII values 32¿126 decimal or 0x20¿0x7E
                       hexadecimal.""",
                raise GlacierWrapper.InputException(ex, code="VaultDescriptionError")
        return True

    @glacier_connect
    @log_class_call("Listing vaults", "Listing vaults complete")
    def lsvault(self):
        """
        Lists vaults

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
            raise GlacierWrapper.ResponseExceptiion("Problem parsing vault list",
                                                    cause=e)

        return vault_list

    @glacier_connect
    @log_class_call("Creating vault", "Vault creation complete")
    def mkvault(self, vault_name):
        """
        Creates new vault

        :param vault_name: Name of newly created vault
        :type vault_name: str

        :returns: Response data
                  TODO: Return value example
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
    @log_class_call("Removing vault", "Vault creation complete")
    def rmvault(self, vault_name):
        """
        Creates new vault

        :param vault_name: Name of newly created vault
        :type vault_name: str

        :returns: Response data
                  TODO: Return value example
        :rtype: str
        """

        if self._check_vault_name(vault_name):
            try:
                response = GlacierVault(self.glacierconn, vault_name).delete_vault()
            except Exception, e:
                raise GlacierWrapper.CommunicationException("Cannot create vault",
                                                            cause=e)
            self._check_response(response)

            return response.getheaders()

    @glacier_connect
    @log_class_call("Describing vault", "Response from describe vault")
    def describevault(self, vault_name):
        """
        Describes vault invertory

        :param vault_name: Name of vault
        :type vault_name: str

        :returns: List of jobs
                  TODO: Return value example
        :rtype: json
        """

        if self._check_vault_name(vault_name):
            try:
                gv = GlacierVault(self.glacierconn, name=vault_name)
                response = gv.describe_vault()
            except Exception, e:
                raise GlacierWrapper.CommunicationException("Cannot describe vault",
                                                            cause=e)
            self._check_response(response)

            jdata = json.loads(response.read())
            return jdata

    @glacier_connect
    @log_class_call("Listing jobs", "Jobs listed")
    def listjobs(self, vault_name):
        if self._check_vault_name(vault_name):
            try:
                gv = GlacierVault(self.glacierconn, name=vault_name)
                response = gv.list_jobs()
            except Exception, e:
                raise GlacierWrapper.CommunicationException("Cannot list jobs",
                                                            cause=e)
            self._check_response(response)

            return (response.getheaders(), gv.job_list)

    @glacier_connect
    @log_class_call("Aborting multipart upload", "Multipart upload aborted")
    def abortmultipart(self, vault_name, upload_id):
        if self._check_vault_name(vault_name):
            try:
                gv = GlacierVault(self.glacierconn, name=vault_name)
                response = gv.abort_multipart(upload_id)
            except Exception, e:
                raise GlacierWrapper.CommunicationException("Cannot abort multipart upload",
                                                            cause=e)
            self._check_response(response)

            return response.getheaders()

    @glacier_connect
    @log_class_call("Getting archive", "Response for getting archive")
    def getarchive(self, vault, archive):
        """
        Gets archive

        If retrival job is already initiated we return Vault job status,
        and if retrival is completed we also return job data. If retrival
        job does not exist yet we initialize retrival and return job status.

        :param vault: Vault name from where we want to retrive archive
        :type vault: str
        :param archive: Archive id
        :type archive: str

        :returns: Tupple of Vault job and Glacier job
                  TODO: Return example
        :rtype: (json, json)
        """

        try:
            gv = GlacierVault(self.glacierconn, vault)
            gv.list_jobs()
        except Exception, e:
             raise GlacierWrapper.CommunicationException("Cannot list jobs",
                                        cause=e, code="JobListError")

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
                GlacierWrapper.ResponseException("Cannot process returned job list",
                                                 cause=e)

        try:
            job = gv.retrieve_archive(archive)
        except Exception, e:
            raise GlacierWrapper.CommunicationException("Cannot retrive archive",
                                            cause=e, code="ArchiveRetriveError")
        return (job, None)

    @glacier_connect
    @sdb_connect
    @log_class_call("Deleting archive", "Archive deleted")
    def deletearchive(self, vault, archive):
        try:
            gv = GlacierVault(self.glacierconn, vault)
            self._check_response( gv.delete_archive(archive) )
        except Exception, e:
            raise GlacierWrapper.CommunicationException("Cannot delete archive",
                                            code="ArchiveDeleteError", cause=e)

        if self.bookkeeping:
            try:
                # TODO: can't find a method for counting right now
                query = ('select * from `%s` where archive_id="%s"' %
                            (self.bookkeeping_domain_name, archive))
                items = self.sdb_domain.select(query)
            except boto.exception.SDBResponseError as e:
                raise GlacierWrapper.CommunicationException("Cannot get archive from SDB",
                                            code="SdbReadError", cause=e)
            try:
                for item in items:
                    self.sdb_domain.delete_item(item)
            except boto.exception.SDBResponseError as e:
                raise GlacierWrapper.CommunicationException("Cannot delete item from SDB",
                                            code="SdbWriteError", cause=e)


    @glacier_connect
    @sdb_connect
    @log_class_call("Retriving invertory", "Response from invertory retrival")
    def inventory(self, vault, force):
        """
        Retrives invertory and returns retrival job, or if it's already retrived
        returns invertoy.

        :param vault: Vault name
        :type vault: str
        :param force: Force new invertory retrival
        :type force: boolean

        :returns: Tupple of retrival job and invertory data if it's avalibe
                  TODO: Return example
        :rtype: (json, json)
        """

        r_ex= "Cannot retrive invertory"

        gv = GlacierVault(self.glacierconn, vault)
        # We force invertory retrival, even if it's alread complete
        if force:
            try:
                job = gv.retrieve_inventory(format="JSON")
            except Exception, e:
                raise GlacierWrapper.CommunicationException(r_ex,
                                            cause=e, code="InvertoryRetriveError")

            return (job,)

        # List active jobs and check if invertory retrival is complete
        try:
            gv.list_jobs()
        except Exception, e:
            raise GlacierWrapper.CommunicationException("Cannot list jobs",
                                            cause=e, code="JobListError")
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
                ex= "Cannot process returned job list"
                raise GlacierWrapper.ResponseException(ex, cause=e)

        # If invertory retrival is complete, process it
        if len(inventory_retrievals_done):
            try:
                list.sort(inventory_retrievals_done,
                        key=lambda i: i['inventory_date'], reverse=True)
                job = inventory_retrievals_done[0]
                job = GlacierJob(gv, job_id=job['JobId'])
                inventory = json.loads(job.get_output().read())
            except Exception, e:
                ex= "Cannot process completed job"
                raise GlacierWrapper.ResponseExceptiion(ex, cause=e)

            # if bookkeeping is enabled update cache
            if self.bookkeeping:
                d = dtparse(inventory['InventoryDate']).replace(tzinfo=pytz.utc)
                try:
                    self.sdb_domain.put_attributes("%s" % (d,), inventory)
                except boto.exception.SDBResponseError as e:
                    ex= "Cannot update invertory cache, sdb is not happy"
                    raise GlacierWrapper.CommunicationException(ex, cause=e, code="SdbWriteError")

                if ((datetime.utcnow().replace(tzinfo=pytz.utc) - d).days > 1):
                    try:
                        gv.retrieve_inventory(format="JSON")
                    except Exception, e:
                        raise GlacierWrapper.CommunicationException(r_ex,
                                            cause=e, code="InvertoryRetriveError")
        else:
            try:
                job = gv.retrieve_inventory(format="JSON")
            except Exception, e:
                raise GlacierWrapper.CommunicationException(r_ex,
                                            cause=e, code="InvertoryRetriveError")

        return (job, inventory)


    def __init__(self, aws_access_key, aws_secret_key, region,
                 bookkeeping=None, bookkeeping_domain_name=None):
        self.logger = logging.getLogger(self.__class__.__name__)

        self.logger.debug("""Creating GlacierWrapper with aws_access_key=%s,
                             aws_secret_key=%s, bookkeeping=%r,
                             bookkeeping_domain_name=%s, region=%s""",
                          aws_access_key, aws_secret_key, bookkeeping,
                          bookkeeping_domain_name, region)
        self.aws_access_key = aws_access_key
        self.aws_secret_key = aws_secret_key
        self.bookkeeping = bookkeeping
        self.bookkeeping_domain_name = bookkeeping_domain_name
        self.region = region

