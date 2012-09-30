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
import os.path
import time
import sys
import re

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
    Wrapper for glacier, with amazon sdb support and other features.
    """

    VAULT_NAME_ALLOWED_CHARACTERS = "[a-zA-Z\.\-\_0-9]+"
    MAX_VAULT_NAME_LENGTH = 255
    MAX_VAULT_DESCRIPTION_LENGTH = 1024
    MAX_PARTS = 10000
    DEFAULT_PART_SIZE = GlacierWriter.DEFAULT_PART_SIZE

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
        @log_class_call("Connecting to Amazon SimpleDB.", "Connection to Amazon SimpleDB successful.")
        def sdb_connect_wrap(*args, **kwargs):
            self = args[0]
            
            if not hasattr(self, 'sdb_conn'):
                try:
                    self.logger.debug("""Connecting to Amazon SimpleDB domain %s with\naws_access_key %s\naws_secret_key %s""",
                                      self.bookkeeping_domain_name,
                                      self.aws_access_key,
                                      self.aws_secret_key)
                    self.sdb_conn = boto.connect_sdb(aws_access_key_id=self.aws_access_key,
                                                     aws_secret_access_key=self.aws_secret_key)
                    domain_name = self.bookkeeping_domain_name
                    self.sdb_domain = self.sdb_conn.get_domain(domain_name, validate=True)
                except boto.exception.AWSConnectionError as e:
                    self.debugger.log("Failed to connect to Amazon SimpleDB. Error: %s"% e)
                    raise GlacierWrapper.ConnectionException("Cannot connect to Amazon SimpleDB.",
                                                             cause=e,
                                                             code="SdbConnectionError")

                self.logger.debug("Succesfully connected to Amazon SimpleDB.")
                
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
        if response.status in [403, 404]:
            message = '%s %s\n%s'% (response.status,
                                   response.reason,
                                   json.loads(response.read())['message'])
            code = {403: 'Error_403',
                    404: 'Error_404'}[response.status]
            raise GlacierWrapper.ResponseException(message, code=code)

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

        :param description: Vault description
        :type description: str

        :returns: True if correct, false otherwise
        :rtype: boolean
        """

        if len(description) > self.MAX_VAULT_DESCRIPTION_LENGTH:
            ex= u"Description must be no more than %s characters."% self.MAX_VAULT_DESCRIPTION_LENGTH,
            raise GlacierWrapper.InputException(ex, code="VaultDescriptionError")

        for char in description:
            n = ord(char)
            if n < 32 or n > 126:
                ex= u"""The allowed characters are 7-bit ASCII without control codes, \
specifically ASCII values 32¿126 decimal or 0x20¿0x7E hexadecimal.""",
                raise GlacierWrapper.InputException(ex, code="VaultDescriptionError")
        return True

    def _check_id(self, amazon_id):
        """
        Checks if an id (jobID, uploadID, archiveID) is valid.

        :param description: id to be validated
        :type description: str

        :returns: True if correct, false otherwise
        :rtype: boolean
        """

        #TODO: implement amazon_id validation check (correct length; characters valid)
        
        return True

    def _check_region(self, region):
        """
        Checks whether the region given is valid.
        """

        regions = ('us-east-1', 'us-west-2', 'us-west-1', 'eu-west-1', 'ap-northeast-1')
        if not region in regions:
            raise GlacierWrapper.InputException("Region given is not a valid region.")
        
        return True

    def _next_power_of_2(self, v):
        """
        Returns the next power of 2, or the argument if it's already a power of 2.
        """
        if v == 0:
            return 1
        
        v -= 1
        v |= v >> 1
        v |= v >> 2
        v |= v >> 4
        v |= v >> 8
        v |= v >> 16
        print 'v: %s'% v
        return v + 1

    def _progress(self, msg):
        if sys.stdout.isatty():
            print msg,
            sys.stdout.flush()

    # Formats file sizes in human readable format. Anything bigger than TB
    # is returned is TB. Number of decimals is optional, defaults to 1.
    def _size_fmt(self, num, decimals = 1):
        fmt = "%%3.%sf %%s"% decimals
        for x in ['bytes','KB','MB','GB']:
            if num < 1024.0:
                return fmt % (num, x)
            
            num /= 1024.0
            
        return fmt % (num, 'TB')

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
            return json.loads(response.read())

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
    @log_class_call("Requesting job description.", "Job description received.")
    def describejob(self, vault_name, job_id):
        if self._check_vault_name(vault_name) and self._check_id (job_id):
            try:
                gv = GlacierVault(self.glacierconn, name=vault_name)
                gj = GlacierJob(gv, job_id=job_id)
                response = gj.job_status()
            except Exception, e:
                raise GlacierWrapper.CommunicationException("Cannot get jobs list.",
                                                            cause=e)

            self._check_response(response)
            return json.loads(response.read())
        

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
    @log_class_call("Listing multipart uploads.", "Multipart uploads list received successfully.")
    def listmultiparts(self, vault_name):
        if self._check_vault_name(vault_name):
            try:
                gv = GlacierVault(self.glacierconn, name=vault_name)
                response = gv.list_multipart_uploads()
            except Exception, e:
                raise GlacierWrapper.CommunicationException("Cannot abort multipart upload.",
                                                            cause=e)
            self._check_response(response)

            return json.loads(response.read())

    @glacier_connect
    @sdb_connect
    @log_class_call("Uploading archive.", "Upload of archive finished.")
    def upload(self, vault_name, file_name, description, region, stdin, part_size):

        if description:
            description = " ".join(description)
        else:
            description = file_name

        if self._check_vault_description(description):
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
    @log_class_call("Processing archive retrieval job.", "Archive retrieval job response received.")
    def getarchive(self, vault, archive=None, file_name=None, search_term=None):
        """
        Requests Amazon Glacier to make archive available for download.
        Returns a tuple (action, job status, job id, search results)

        If retrieval job is not yet initiated: initiate a job, return tuple ("initiated", job status, None, results)
        If retrieval job is already initiated: return tuple ("running", job status, None, results).
        If the file is ready for download: return tuple ("ready", job status, GlacierJob, results).

        :param vault: Vault name from where we want to retrieve the archive.
        :type vault: str
        :param archive: ArchiveID of archive to be retrieved.
        :type archive: str

        :returns: Tuple of Vault job and Glacier job
                  TODO: Return example
        :rtype: (json, json)
        """

        results = None

        # If we have an archive id, check wether it's valid and if so,
        # continue with this id.
        # Otherwise try to search for file name or search term, and
        # raise an error if there is more than one result.
        if archive and self._check_id(archive):
            pass
        else:
            if file_name:
                results = search(file_name=file_name)
            elif search_term:
                results = search(search_term=search_term)
            else:
                raise GlacierWrapper.InputException("Must provide at least one of archive ID, a file name or a search term.")

            if len(results) == 0:
                raise GlacierWrapper.InputException("No results.")

            if len(results) > 1:
                raise GlacierWrapper.InputException("Too many results; please narrow down your search terms.")

            archive = results[0]['archive_id']

        # We have a unique result; check whether we have a retrieval job
        # running for it.
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
                        return ('running', job, None, results)
                    
                    if job['Completed']:
                        job2 = GlacierJob(gv, job_id=job['JobId'])
                        return ('ready', job, job2, results)
                    
            except Exception, e:
                GlacierWrapper.ResponseException("Cannot process job list response.",
                                                 cause=e)

        # No job found related to this archive, start a new job.        
        try:
            job = gv.retrieve_archive(archive)
        except Exception, e:
            raise GlacierWrapper.CommunicationException("Cannot retrieve archive",
                                                        cause=e,
                                                        code="ArchiveRetrieveError")
        return ("initiated", job, None, results)

    @glacier_connect
    @sdb_connect
    @log_class_call("Download an archive.", "Download archive done.")
    def download(self, vault, archive, out_file=None):
        """
        Download a file from Glacier, and store it in out_file.
        If no out_file is given, the file will be dumped on stdout.
        """

        # Sanity checking on the input.
        self._check_vault_name(vault)
        self._check_id(archive)
        self._check_region(region)
        if out_file:
            try:
                out = open(out_file)
            except Exception, e:
                raise GlacierWrapper.InputException("Cannot access the ouput file.",
                                                    cause=e,
                                                    code="FileError")

        # Check whether the requested file is available from Amazon Glacier.
        gv = GlacierVault(glacierconn, vault)
        jobs = gv.list_jobs()
        found = False
        for job in gv.job_list:
            if job['ArchiveId'] == archive:
                found = True
                if not job['Completed']:
                    raise GlacierWrapper.CommunicationException("Archive retrieval request \
not completed yet. Please try again later.")
                break

        if found:
            print "File is available, starting download now."
            job2 = glaciercorecalls.GlacierJob(gv, job_id=job['JobId'])
            if out_file:
                ffile = open(out_file, "w")
                ffile.write(job2.get_output().read())
                ffile.close()
            else:
                print job2.get_output().read()

        raise GlacierWrapper.InputException("Requested archive not available. Please make sure \
your archive ID is correct, and start a retrieval job using 'getarchive' if necessary.")

    
    @glacier_connect
    @sdb_connect
    @log_class_call("Searching for archive.", "Search done.")
    def search(self, vault=None, region=None, archive=None, file_name=None, search_term=None, print_results=False):

        # Sanity chekcing.
        if not self.bookkeeping:
            raise Exception(u"You must enable bookkeeping to be able to do searches.")

        self._check_region(region)
        self._check_id(archive)
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
        returns overview of the inventoy. If force=True it will force start a new
        inventory taking job.

        :param vault: Vault name
        :type vault: str
        :param force: Force new inventory retrieval.
        :type force: boolean

        :returns: Tuple of retrieval job and inventory data (as list) if available.
                  TODO: Return example
        :rtype: (str, list)
        """

        r_ex= "Cannot retrieve inventory."

        gv = GlacierVault(self.glacierconn, vault)
        
        # Force inventory retrieval, even if it's already complete.
        if force:
            try:
                job = json.loads(gv.retrieve_inventory(format="JSON"))
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
        
