import traceback
import re
import sys
"""

**********
Note by wvmarle:
I am adding comments as I see fit, trying to make sense of what this is
really doing.
Purpose of my modifications: get rid of the stack trace dumped to the screen;
instead log this in the log file at debug level if it is an exception thrown
by ourselves, as this is useless and very confusing for an end user.
**********

"""
class CausedException(Exception):
    
    def __init__(self, *args, **kwargs):

        # Check wether we have a cause and whether the argument is an Exception.
        if len(args) == 1 and not kwargs and isinstance(args[0], Exception):
            
            # Just wrap up a cause-less exception.
            # Get the stack trace for this exception.
            self.stack = (
                traceback.format_stack()[:-2] +
                traceback.format_tb(sys.exc_info()[2]))
            # ^^^ let's hope the information is still there; caller must take
            #     care of this.
            
            self.wrapped = args[0]
            self.cause = ()
            return
        
        self.wrapped = None

        self.stack = traceback.format_stack()[:-2]

        # Get the cause of the exception.
        try:
            cause = kwargs['cause']
            del kwargs['cause']
        except:
            cause = ()
            
        self.cause = cause if isinstance(cause, tuple) else (cause,)
        super(CausedException, self).__init__(*args, **kwargs)


    # Works as a generator to help get the stack trace and the cause
    # written out.
    def causeTree(self, indentation='  ', alreadyMentionedTree=[], stack=False, message=False):
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

   
if __name__ == '__main__':
    class ChildrenException(Exception):
        def __init__(self, message):
            Exception.__init__(self, message)

    class ParentException(CausedException):
        def __init__(self, message, cause=None):
            if cause:
                CausedException.__init__(self, message, cause=cause)
            else:
                 CausedException.__init__(self, message)

    try:
        try:
            raise ChildrenException("parent")
        except ChildrenException, e:
            raise ParentException("children", cause=e)
    except ParentException, e:
        e.write(indentation='||  ')
