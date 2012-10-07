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
    
    def __init__(self, message, code=None, cause=None):
        """
        Constructor. Logs the error.

        :param message: the error message.
        :type message: str
        :param code: the error code.
        :type code: 
        :param cause: explanation on what caused the error.
        :type cause: str
        """
        self.logger = logging.getLogger(self.__class__.__name__)
        self.code = code
        if cause:
            self.logger.error('ERROR: %s'% cause)
            self.cause = cause if isinstance(cause, tuple) else (cause,)
            self.stack = traceback.format_stack()[:-2]
            self.wrapped = None

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
            
            self.wrapped = message

        self.logger.info(self.fetch(message=True))
        self.logger.debug(self.fetch(stack=True))

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
            exc = self if self.wrapped is None else self.wrapped
            for line in traceback.format_exception_only(exc.__class__, exc):
                yield line
            
            if self.cause:
                yield ("caused by: %d exception%s\n" %
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
