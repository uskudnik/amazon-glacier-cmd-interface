import traceback
import re
import sys

class CausedException(Exception):
    def __init__(self, *args, **kwargs):
        if len(args) == 1 and not kwargs and isinstance(args[0], Exception):
            # we shall just wrap a non-caused exception
            self.stack = (
                traceback.format_stack()[:-2] +
                traceback.format_tb(sys.exc_info()[2]))
            # ^^^ let's hope the information is still there; caller must take
            #     care of this.
            self.wrapped = args[0]
            self.cause = ()
            return
        self.wrapped = None
        self.stack = traceback.format_stack()[:-1]  # cut off current frame
        try:
            cause = kwargs['cause']
            del kwargs['cause']
        except:
            cause = ()
        self.cause = cause if isinstance(cause, tuple) else (cause,)
        super(CausedException, self).__init__(*args, **kwargs)

    def causeTree(self, indentation='  ', alreadyMentionedTree=[]):
        yield "Traceback (most recent call last):\n"
        ellipsed = 0
        for i, line in enumerate(self.stack):
            if (ellipsed is not False and i < len(alreadyMentionedTree) and
                line == alreadyMentionedTree[i]):
                ellipsed += 1
            else:
                if ellipsed:
                    yield "  ... (%d frame%s repeated)\n" % (
                        ellipsed, "" if ellipsed == 1 else "s")
                    ellipsed = False  # marker for "given out"
                yield line
        exc = self if self.wrapped is None else self.wrapped
        for line in traceback.format_exception_only(exc.__class__, exc):
            yield line
        if self.cause:
            yield ("caused by: %d exception%s\n" %
                (len(self.cause), "" if len(self.cause) == 1 else "s"))
            for causePart in self.cause:
                for line in causePart.causeTree(indentation, self.stack):
                    yield re.sub(r'([^\n]*\n)', indentation + r'\1', line)

    def write(self, stream=None, indentation='  '):
        stream = sys.stderr if stream is None else stream
        for line in self.causeTree(indentation):
            stream.write(line)

if __name__ == '__main__':
    class ChildrenException(CausedException):
        def __init__(self, message):
            CausedException.__init__(self, message)

    class ParentException(CausedException):
        def __init__(self, message, cause):
            CausedException.__init__(self, message, cause=cause)

    try:
        try:
            raise ChildrenException("parent")
        except ChildrenException, e:
            raise ParentException("children", cause=e)
    except ParentException, e:
        e.write(indentation='||  ')
