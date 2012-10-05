
**********
Usage.
**********

``$ glacier-cmd --help``

This command gives you a quick overview of all supported command line options, with a short explanation of what they do.

.. program-output:: glacier-cmd -h


Configuration.
---------------

Program settings may be passed in via a config file, via the command line or via environment variables. The default config files are ``/etc/glacier.cfg`` and ``~/.glacier``, alternative config files can be indicated using the ``-c`` command line option. 
The content of the config file should look like this::

    [aws]
    access_key=your_access_key
    secret_key=your_secret_key

    [glacier]
    region=us-east-1
    bookkeeping=True
    bookkeeping-domain-name=your_simple_db_domain_name

The environment variables for the options are::

    aws_access_key=your_access_key 
    aws_secret_key=your_secret_key 
    region=us-east-1 
    bookkeeping=True 
    bookkeeping-domain-name=your_simple_db_domain_name

These variables can also be used as command line options to pass in the information.

[TODO: add overview of regions.]

Switching on bookkeeping allows glacier-cmd to keep track of your inventory. Note that you must create a Amazon SimpleDB domain for this to work, as the bookkeeping data is stored online in such a SimpleDB. This database contains a list of the IDs of all uploaded archives and their names, hashes, sizes and other meta data. You must have bookkeeping enable to allow the search command to work.

Vault management.
-----------------
Vault management including creating, listing and removing of vaults is provided via the following command line directives.

Creating a vault.
^^^^^^^^^^^^^^^^^

``$ glacier-cmd mkvault <vault name>``

This command creates a vault. It must be preceded by the name of the vault you want to create. Note: vault names are case sensitive, and may only contain characters [TODO: which and how many characters?]

.. command-output:: glacier-cmd mkvault Test

Listing available vaults.
^^^^^^^^^^^^^^^^^^^^^^^^^

``$ glacier-cmd lsvault``

This command gives an overview of the available vaults.

.. command-output:: glacier-cmd lsvault

Deleting a vault.
^^^^^^^^^^^^^^^^^

``$ glacier-cmd rmvault <vault name>``

This command deletes a vault. Only empty vaults can be deleted, if you have archives in a vault you must delete these archives first. 

.. command-output glacier-cmd rmvault Test

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

Listing inventory of a vault.
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

``$ glacier-cmd inventory <vault name>``.

This command lists the latest inventory of a vault. 

Note: Glacier updates the vault inventory only once per day, a just uploaded archive will not be listed here.
[TODO: how about RetrievingInventory jobs that result from this command?] ::

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

This command gives an overview of  recent jobs such as inventory retrieval jobs and their status.

.. command-output:: glacier-cmd listjobs Test




Archive management.
-------------------

You may upload, retrieve and delete archives using glacier-cmd.

Note that when deleting a file, it takes up to a day for Glacier to update your inventory and actually purge the file. 

When downloading a file, you first must request the file to be retrieved by Glacier before you can download it. This retrieval process takes around four hours, and the file will be available for download for 24 hours after which it is removed from the available queue.

Uploading an archive.
^^^^^^^^^^^^^^^^^^^^^

``$ glacier-cmd upload <vault name> /path/to/archive "description of archive"``

Note that the description of the archive may be no more than 1,024 characters, and contain only [TODO: which characters?].

Files are uploaded in blocks, the default size is 128 MB. After the upload of each block a progress update will be printed, showing the amount of data uploaded, the upload speed and an estimated finish time. When finished, the archive ID and an SHA256 hash will be printed.

Note: this hash is not the same as you get when running the ``sha256sum /path/to/archive`` command as the hash is computed by glacier-cmd block by block. Amazon Glacier calculates the SHA256 sum in this manner too.

Uploading options.
""""""""""""""""""
* ``--blocksize``

[TODO: describe ``--blocksize`` option]

Amazon Glacier limits uploads to 10,000 blocks. With the default block size of 128 MB, this means archives are limited to about 1.3 TB. For larger archives you must set a larger block size; for smaller archives you may set a smaller block size.

[TODO: describe consequences of block size]


* ``--stdin``

Use this option to tell glacier-cmd to expect data to be piped in over stdin.

[TODO is this correct?]

    ``$ cat /path/to/archive | glacier-cmd upload Test "Data from stdin" --name /nice/name/for/archive --stdin``

* ``--name``

Specify a file name for your archive. 

This is required [TODO: is this so? It should be!] when you pipe in data over stdin, and can be useful to override the local file name of the archive, for example when the local file is a temporary file with a randomly generated name. This file name will be used for the bookkeeping entry of this upload.

    ``$ glacier-cmd upload --name /path/BetterName Test /tmp/temp.tQ6948 "Some description"``

Downloading an archive.
^^^^^^^^^^^^^^^^^^^^^^^

There are two distict commands available for downloading an archive: ``download`` and ``getarchive``.

[TODO: describe the inventory retrieval and download availability time leg, and what these commands do there. First instance start a job; second instance do the download if available?]

* ``$ glacier-cmd download <"search query"> [vault] [--region REGION]``

The search query must be either a complete file name or (part of) the description of the file. The search may be narrowed down further using the vault name or the region. Requires bookkeeping to be active.
[TODO: is this entry correct?]

* ``$ glacier-cmd getarchive <archive-ID>``

Retrieves an archive by its archive ID.
Note: if the archive ID starts with a hyphen (-) then it must be preceded by the ``--`` command line switch.

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

Searching by file name.
^^^^^^^^^^^^^^^^^^^^^^^

    ``$ glacier-cmd search``

[TODO: is this description correct?]

This command will dump a complete of archives uploaded by glacier-cmd. Requires bookkeeping. Archives uploaded by other means, or by glacier-cmd not using bookkeeping, will not be listed.

Managing multipart jobs.
^^^^^^^^^^^^^^^^^^^^^^^^
[TODO properly describe multipart segment.]

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

