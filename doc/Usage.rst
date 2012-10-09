
**********
Usage.
**********

``$ glacier-cmd --help``

This command gives you a quick overview of all supported command line options, with a short explanation of what they do.

.. program-output:: glacier-cmd -h


Configuration.
---------------

Program settings may be passed in via a config file, via the command line or via environment variables. The default config files are ``/etc/glacier.cfg`` and ``~/.glacier``, alternative config files can be indicated using the ``-c`` command line option. Having a config file itself is optional even.
The content of the config file should look like this::

    [aws]
    access_key=your_access_key
    secret_key=your_secret_key

    [glacier]
    region=us-east-1
    bookkeeping=True
    bookkeeping-domain-name=your_simple_db_domain_name
    logfile=~/.glacier-cmd.log
    loglevel=INFO

The environment variables for the options are::

    aws_access_key=your_access_key 
    aws_secret_key=your_secret_key 
    region=us-east-1 
    bookkeeping=True 
    bookkeeping-domain-name=your_simple_db_domain_name
    logfile=~/.glacier-cmd.log
    loglevel=INFO

All these variable names can also be used as command line options to pass in the information.

Currently available regions are::

   us-east-1 (US - Virginia)
   us-west-1 (US - N. California)
   us-west-2 (US - Oregon)
   eu-west-1 (EU - Ireland)
   ap-northeast-1 (Asia-Pacific - Tokyo)

Available log levels::

   3, CRITICAL,
   2, ERROR,
   1, WARNING,
   0, INFO,
   -1, DEBUG}

The recommended loglevels are INFO and WARNING. Do not set it to DEBUG unless you need it as it is really noisy.

Switching on bookkeeping allows glacier-cmd to keep track of your inventory. Note that you must create a Amazon SimpleDB domain for this to work, as the bookkeeping data is stored online in such a SimpleDB. This database contains a list of the IDs of all uploaded archives and their names, hashes, sizes and other meta data. You must have bookkeeping enable to allow the search command to work.

Vault management.
-----------------
Vault management including creating, listing and removing of vaults is provided via the following command line directives.

Creating a vault.
^^^^^^^^^^^^^^^^^

``$ glacier-cmd mkvault <vault name>``

This command creates a vault. It must be preceded by the name of the vault you want to create. Note: vault names are case sensitive, and may only contain characters a-z, A-Z, 0-9, '_' (underscore), '-' (hyphen), and '.' (period). The vault name should be at least one, and no more than 255 characters in length.

.. command-output:: glacier-cmd mkvault Test

Listing available vaults.
^^^^^^^^^^^^^^^^^^^^^^^^^

``$ glacier-cmd lsvault``

This command gives an overview of the available vaults.

.. command-output:: glacier-cmd lsvault

Describing status of a vault.
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

``$ glacier-cmd decribevault <vault name>``

This command produces a table containing an overview of the status of a vault, including the number of archives, the size, and when the vault was created. ::

    $ glacier-cmd describevault Test
    200 OK
    +--------------------------+----------+----------+----------------------------------------------------+--------------------------+
    |      LastInventory       | Archives |   Size   |                        ARN                         |         Created          |
    +--------------------------+----------+----------+----------------------------------------------------+--------------------------+
    | 2012-09-14T20:14:31.609Z |    19    | 44056372 | arn:aws:glacier:us-east-1:771747372727:vaults/Test | 2012-08-30T03:26:05.507Z |
    +--------------------------+----------+----------+----------------------------------------------------+--------------------------+

Deleting a vault.
^^^^^^^^^^^^^^^^^

``$ glacier-cmd rmvault <vault name>``

This command deletes a vault. Only empty vaults can be deleted, if you have archives in a vault you must delete these archives first. 

.. command-output glacier-cmd rmvault Test

Listing inventory of a vault.
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

``$ glacier-cmd inventory <vault name>``.

This command lists the latest inventory of a vault.

Glacier does not automatically take inventory of a vault, instead it does so only on request. If no inventory available, this command will initiate an inventory retrieval job, which takes about four hours to finish.

To force the start of a new inventory retrieval job, use the ``--refresh`` command line option::

    $ glacier-cmd inventory Test
    Inventory of vault arn:aws:glacier:us-east-1:771747372727:vaults/Test
    Inventory Date: 2012-09-11T22:03:37Z
    Content:
    +---------------------------------------------+----------------------+----------+--------------------------------------------------------------------------------------------------------------------------------------------+------------------------------------------------------------------+
    |             Archive Description             |       Uploaded       |   Size   |                                                                 Archive ID                                                                 |                           SHA256 hash                            |
    +---------------------------------------------+----------------------+----------+--------------------------------------------------------------------------------------------------------------------------------------------+------------------------------------------------------------------+
    |                 DSC01600.xcf                | 2012-08-31T03:49:34Z | 38679745 | riTD8lqS96TvEwrqMy79jziF-l0vc_jbhYeCli1qtCAEH4IfzvvIU96VSiSOIytGRKJfw8Pf0SRk5i1ruxIIZuyfH7W7jTEW_h-Zd5Ho6aveZdfW8JfoYXXMRz6Dn_Yg0FsgYCLGQw | cb7ca5b0fa02af0180e0c172489c2f40f3469db2dfc86ae41e713b7bacea68e7 |
    |                     2016                    | 2012-09-10T05:09:20Z |  250178  | JZ8Xsys9LnN0djnOaC-5YNQYoKnd2jL0eLp8H3SlMexls0tqLdlvZQGnS56Q3Hb3ahsle7XNKQv5ouZjY2fOu9gI6BRErK8gKHAKxlFtdIeGFD6w_KVElczfehJV4XJIz8zCtGcjsg | d8f50c77cdef296ae57b0a3386e3f3d73435c94f5e6d320d5426bd1b239397d4 |
    +---------------------------------------------+----------------------+----------+--------------------------------------------------------------------------------------------------------------------------------------------+------------------------------------------------------------------+

Jobs management.
----------------

``$ glacier-cmd listjobs <vault name>`` 

This command gives an overview of recent jobs such as inventory and archive retrieval jobs and their status.

.. command-output:: glacier-cmd listjobs Test

Archive management.
-------------------

You may upload, retrieve and delete archives using glacier-cmd.

Note that when deleting a file, it takes up to a day for Glacier to update your inventory and actually purge the file. 

When downloading a file, you first must request the file to be retrieved by Glacier before you can download it. This retrieval process takes around four hours, and the file will be available for download for 24 hours after which it is removed from the available queue.

Uploading an archive.
^^^^^^^^^^^^^^^^^^^^^

``$ glacier-cmd upload <vault name> /path/to/archive [path/to/anotherarchive]``

You may add an arbitrary number of files on the command line, or use wildcards in the file names.

Note that the description of the archive may be no more than 1,024 characters, and contain only 7-bit ASCII characters without control codes, specifically ASCII values 32-126 decimal or 0x20-0x7E hexadecimal.

Files are uploaded in blocks, the default size is the smallest possible size to fit the file in no more than 10,000 blocks. When uploading data piped in via stdin, a default block size of 128 MB is used. After the upload of each block a progress update will be printed, showing the amount of data uploaded, the upload speed and an estimated finish time. When finished, the archive ID and an SHA256 hash will be printed.

Note: this hash is not the same as you get when running the ``sha256sum /path/to/archive`` command as the hash is a tree hash, caclulated by taking the individual hashes of each 1 MB part of the file.

Uploading options.
""""""""""""""""""
* ``--description "description of archive"``

Set a description of your archive. This may be up to 1024 characters long, and will be listed in the inventory of your vault, and stored in the bookkeeping database. If no description given, the file name of the archive is used instead.

* ``--partsize <size in MB>``

This overrides the default part size, and the calculated optimal part size. The size is given in MB, and must be a power of two. Valid values are 1, 2, 4, 8, ...,  2048, 4096.

Amazon Glacier limits uploads to 10,000 parts. With the default part size of 128 MB, this means archives are limited to about 1.3 TB. For larger archives you must set a larger part size; for smaller archives you may set a smaller part size. If the part size given is too small to fit the file in 10,000 parts, it will be automaticially changed to the minimal required part size.
Some examples::

partsize   Maximum archive size
1          1*1024*1024*10000 ~= 9.7 GB
4          4*1024*1024*10000 ~= 39 GB
16         16*1024*1024*10000 ~= 156 GB
128        128*1024*1024*10000 ~= 1.2 TB
4096       4096*1024*1024*10000 ~= 39 TB


* ``--stdin``

Use this option to tell glacier-cmd to expect data to be piped in over stdin. ::

   $ cat /path/to/archive | glacier-cmd upload Test "Data from stdin" --name /nice/name/for/archive --stdin

* ``--name``

Specify a file name for your archive. 

This is required when you pipe in data over stdin, and can be useful to override the local file name of the archive, for example when the local file is a temporary file with a randomly generated name. This file name will be used for the bookkeeping entry of this upload. ::

   $ glacier-cmd upload --name /path/BetterName Test /tmp/temp.tQ6948 "Some description"

* ``--bacula``

The file name is a bacula-style list of multiple files. This is useful if this script is used in conjunction with the Bacula backup software.
The file list should look like ``/path/to/backups/vol001|vol002|vol003``.

Downloading an archive.
^^^^^^^^^^^^^^^^^^^^^^^

This is a two-step process as first you have to instruct Glacier to retrieve an archive and make it available for download via ``getarchive``, and when that job is done it can be downloaded using ``download``.

* ``$ glacier-cmd getarchive <vault> <archive-ID>``

This command will start a job retrieving the archive with given archive ID from the vault. If a job for the same archive is running already, or is finished, it will notify the user of the status of this job.

Note: if the archive ID starts with a hyphen (-) then it must be preceded by the ``--`` command line switch.

* ``$  glacier-cmd download [--outfile <outfile>] [--overwrite] <vault> <archive-ID>``

This will download an archive if it is available. If not available it will inform the user. The download is done as a single block, so no progress updates of the download can be given. It is also not possible to resume an interrupted download at this moment.

Downloading options.
""""""""""""""""""""
* ``--outfile <outfile>``
The name of the file to write the downloaded data to. If omitted, use stdout.

* ``--overwrite`` 
Overwrite a local file with the same name. If not given, an error will be shown if `<outfile>` exists already.

Deleting an archive.
^^^^^^^^^^^^^^^^^^^^

``$ glacier-cmd rmarchive <vault> <archive-ID>`` 

This command will remove the archive with <archive-ID> from the vault <vault>.

Note: if the archive ID starts wiht a - (hyphen), you must precede it with a ``--`` switch, as otherwise it is recognised as command line option.

Example::

   $ glacier-cmd rmarchive Test -- -6AKuLSU3wxtSqq_GeeAss9zLvto8Xr1su4mqmvluTTv4HcXbFJJNy0yiTu9tG5vFjrBXvmQKXGwFJpNMghqYBerUKpsjq56mrzv1wUbe6DWuzl6Ntb8WSQHYo0kzw8rcLaVx5MFug
    204 No Content
    +------------------+-------------------------------------------------+
    |      Header      |                      Value                      |
    +------------------+-------------------------------------------------+
    | x-amzn-requestid | 1-UC36MM2ZxNwdf-Q2yyT0f7j5KVJ1neGwf-FzsU2H6YDyo |
    |       date       |          Fri, 14 Sep 2012 02:48:46 GMT          |
    +------------------+-------------------------------------------------+

Note: it takes up to a day for Glacier to update your vault inventory, so the archive will not be delisted from the inventory immediately.

Searching by file name or description.
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

    ``$ glacier-cmd search [--filename <file name>] [--searchterm <search term>][--region <region>] [<vault>]``

This command searches the database for available archives. This requires the bookkeeping option to work.

If no options are given, it prints all archives stored in the default region. All searches are limited to one region, if no ``--region`` option is set, the default region will be used.
``--filename <file name>`` searches for a (partial) match on file name.
``--searchterm <search term>`` searches for a (partial) match on description.
``<vault>`` limits the search to the given vault.

Note: no apostrophe (') or quotation mark (") is allowed to be used in the search terms.

Managing multipart jobs.
^^^^^^^^^^^^^^^^^^^^^^^^

Uploads are sent block by block, when an upload is in progress (or halted) a multipart job is present in that vault.

To see the multipart uploads currently in progress, use `listmultiparts`::

    $ glacier-cmd listmultiparts Test
    200 OK
    Marker:  None
    +--------------------+--------------------------+----------------------------------------------------------------------------------------------+-----------------+----------------------------------------------------+
    | ArchiveDescription |       CreationDate       |                                      MultipartUploadId                                       | PartSizeInBytes |                      VaultARN                      |
    +--------------------+--------------------------+----------------------------------------------------------------------------------------------+-----------------+----------------------------------------------------+
    |  fancyme.glacier   | 2012-09-20T04:29:21.485Z | D18RNXeq5ffV99PITXrHBvJOULDt15EJJl0eBD5GFD-pc76ptWCz0k9mrJy4W4oUu2fQ0ljWxiqDXIKGLZVIfFIexErC |     4194304     | arn:aws:glacier:us-east-1:771747372727:vaults/Test |
    +--------------------+--------------------------+----------------------------------------------------------------------------------------------+-----------------+----------------------------------------------------+

To abort one of the multipart uploads, use `abortmultipart` subcommand:

    ``$ glacier-cmd abortmultipart Test D18RNXeq5ffV99PITXrHBvJOULDt15EJJl0eBD5GFD-pc76ptWCz0k9mrJy4W4oUu2fQ0ljWxiqDXIKGLZVIfFIexErC``

