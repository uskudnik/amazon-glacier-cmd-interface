*************
Installation.
*************

Required libraries are glaciercorecalls (temporarily, while we wait for glacier support to land in boto's development branch) and boto - at the moment you still need to use the latest development branch of boto.

You also need to install git, with something like `apt-get install git`, to install the sources directly from the repository. There is no packaged release available yet. The boto development branch is also available via git.

To install glacier-cmd from source, run the following command from the source directory:

    ``$ python setup.py install``

Then you may run the script:

    ``$ glacier-cmd [args]``


