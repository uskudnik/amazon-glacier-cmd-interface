import traceback
import re
import sys
import logging

"""

**********
Note by wvmarle:

This file contains the complete code from chained_exception.py plus the
error handling code from GlacierWrapper.py, allowing it to be used in other
modules like glaciercorecalls as well.
**********

"""
class GlacierException(Exception):
    """
    An extension of the built-in Exception class, this handles
    an additional cause keyword argument, adding it as cause
    attribute to the exception message.
    It logs the error message (amount of information depends on the log
    level) and passes it on to a higher level to handle.
    Furthermore it allows for the upstream handler to call for a
    complete stack trace or just a simple error and cause message.

    TODO: describe usage.
    """

    ERRORCODE = {'InternalError': 255,        # Library internal error.
                 'UndefinedErrorCode': 254,   # Undefined code.
                 'GlacierConnectionError': 1, # Can not connect to Glacier. 
                 'SdbConnectionError': 2,     # Can not connect to SimpleDB.
                 'CommandError': 3,           # Command line is invalid.
                 'VaultNameError': 4,         # Invalid vault name.
                 'DescriptionError': 5,       # Invalid archive description.
                 'IdError': 6,                # Invalid upload/archive/job ID given.
                 'RegionError': 7,            # Invalid region given.
                 'FileError': 8,              # Error related to reading/writing a file.
                 'ResumeError': 9,            # Problem resuming a multipart upload.
                 'NotReady': 10,              # Requested download is not ready yet.
                 'BookkeepingError': 11,      # Bookkeeping not available.
                 'SdbCommunicationError': 12, # Problem reading/writing SimpleDB data.
                 'ResourceNotFoundException': 13, # Glacier can not find the requested resource.
                 'DownloadError': 14 }        # Downloading an archive failed.
                 
                 
    def __init__(self, message, code=None, cause=None):
        """
        Constructor. Logs the error.

        :param message: the error message.
        :type message: str
        :param code: the error code.
        :type code: str
        :param cause: explanation on what caused the error.
        :type cause: str
        """
        self.logger = logging.getLogger(self.__class__.__name__)
        self.exitcode = self.ERRORCODE[code] if code in self.ERRORCODE else 254
        self.code = code
        if cause:
            self.logger.error('ERROR: %s'% cause)
            self.cause = cause if isinstance(cause, tuple) else (cause,)
            self.stack = traceback.format_stack()[:-2]

        else:
            self.logger.error('An error occurred, exiting.')
            self.cause = ()

            # Just wrap up a cause-less exception.
            # Get the stack trace for this exception.
            self.stack = (
                traceback.format_stack()[:-2] +
                traceback.format_tb(sys.exc_info()[2]))
            # ^^^ let's hope the information is still there; caller must take
            #     care of this.
            
        self.message = message
        self.logger.info(self.fetch(message=True))
        self.logger.debug(self.fetch(stack=True))
        if self.exitcode == 254:
            self.logger.debug('Unknown error code: %s.'% code)

    # Works as a generator to help get the stack trace and the cause
    # written out.
    def causeTree(self, indentation='  ', alreadyMentionedTree=[], stack=False, message=False):
        """
        Returns a complete stack tree, an error message, or both.
        Returns a warning if neither stack or message are True.
        """
        if stack:
            yield "Traceback (most recent call last):\n"
            ellipsed = 0
            for i, line in enumerate(self.stack):
                if (ellipsed is not False
                    and i < len(alreadyMentionedTree)
                    and line == alreadyMentionedTree[i]):
                    ellipsed += 1
                else:
                    if ellipsed:
                        yield "  ... (%d frame%s repeated)\n" % (
                            ellipsed,
                            "" if ellipsed == 1 else "s")
                        ellipsed = False  # marker for "given out"
                        
                    yield line

        if message:
            exc = self if self.message is None else self.message
            for line in traceback.format_exception_only(exc.__class__, exc):
                yield line
                
            if self.cause:
                yield ("Caused by: %d exception%s\n" %
                    (len(self.cause), "" if len(self.cause) == 1 else "s"))
                
                for causePart in self.cause:
                    if hasattr(causePart,"causeTree"):
                        for line in causePart.causeTree(indentation, self.stack):
                            yield re.sub(r'([^\n]*\n)', indentation + r'\1', line)
                    else:
                        for line in traceback.format_exception_only(causePart.__class__, causePart):
                            yield re.sub(r'([^\n]*\n)', indentation + r'\1', line)

        if not message and not stack:
            yield ('No output. Specify message=True and/or stack=True \
to get output when calling this function.\n')

    def write(self, stream=None, indentation='  ', message=False, stack=False):
        """
        Writes the error details to sys.stderr or a stream.
        """
        
        stream = sys.stderr if stream is None else stream
        for line in self.causeTree(indentation, message=message, stack=stack):
            stream.write(line)

    def fetch(self, indentation='  ', message=False, stack=False):
        """
        Fetches the error details and returns them as string.
        """
        out = ''
        for line in self.causeTree(indentation, message=message, stack=stack):
            out += line

        return out



class InputException(GlacierException):
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
        GlacierException.__init__(self, message, code=code, cause=cause)

class ConnectionException(GlacierException):
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
        GlacierException.__init__(self, message, code=code, cause=cause)

class CommunicationException(GlacierException):
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
        GlacierException.__init__(self, message, code=code, cause=cause)

class ResponseException(GlacierException):
    """
    Exception that is raised when there is an http response error.
    """
    
    # Will be removed when merge with boto
    Error_403 = 403
    def __init__(self, message, code=None, cause=None):
        GlacierException.__init__(self, message, code=code, cause=cause)




if __name__ == '__main__':
    class ChildrenException(Exception):
        def __init__(self, message):
            Exception.__init__(self, message)

    class ParentException(GlacierException):
        def __init__(self, message, cause=None):
            if cause:
                GlacierException.__init__(self, message, cause=cause)
            else:
                 GlacierException.__init__(self, message)

    try:
        try:
            raise ChildrenException("parent")
        except ChildrenException, e:
            raise ParentException("children", cause=e)
    except ParentException, e:
        e.write(indentation='||  ')
