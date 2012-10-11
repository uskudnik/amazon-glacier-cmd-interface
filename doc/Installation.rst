*************
Installation.
*************

Required libraries are glaciercorecalls which is included in this package, and boto v.2.6.0 or later.

You also need to install git, with something like ``apt-get install git``, to install the sources directly from the repository. There is no packaged release available yet, though github does provide snapshots as tarball.

To install glacier-cmd from source, run the following command from the source directory::

$ sud python setup.py install

Then you may run the script:

$ glacier-cmd [args]


