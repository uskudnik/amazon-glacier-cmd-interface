************
Development.
************

Currently use of `virtualenv` is recommended, but we will migrate to buildout shortly::

    >>> virtualenv --no-site-packages --python=python2.7 amazon-glacier-cmd-interface
    >>> cd amazon-glacier-cmd-interface && source bin/activate
    >>> python setup.py develop
    >>> glacier-cmd command [args]


TODO:
-----

- Integrate with boto
- Support for output status codes
- Documentation examples of output from specific commands
- Description for command line arguments
- Tests

Changelog:
----------

    TODO

