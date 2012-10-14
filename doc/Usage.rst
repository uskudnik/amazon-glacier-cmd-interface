
**********
Usage.
**********

``$ glacier-cmd --help``

.. program-output:: glacier-cmd --help

This command gives you a quick overview of all supported command line options, with a short  explanation of what they do.

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
    output=print

The environment variables for the options are::

    aws_access_key=your_access_key 
    aws_secret_key=your_secret_key 
    region=us-east-1 
    bookkeeping=True 
    bookkeeping-domain-name=your_simple_db_domain_name
    logfile=~/.glacier-cmd.log
    loglevel=INFO
    output=print

All these variable names can also be used as command line options to pass in the information.

Currently available regions are::

   us-east-1 (US - Virginia)
   us-west-1 (US - N. California)
   us-west-2 (US - Oregon)
   eu-west-1 (EU - Ireland)
   ap-northeast-1 (Asia-Pacific - Tokyo)

Available log levels::

   3, CRITICAL
   2, ERROR
   1, WARNING
   0, INFO
   -1, DEBUG

The recommended loglevels are ``INFO`` and ``WARNING``. Do not set it to ``DEBUG`` unless you need it as it is really noisy.

Available options for ``output`` are::

 print  prints the output to the screen (formatted in tables, like the examples in this document).
 csv    produce output in CSV format.
 json   produce output in JSON format.

Switching on :doc:`Bookkeeping` allows glacier-cmd to keep track of your inventory. Note that you must create a Amazon SimpleDB domain for this to work, as the bookkeeping data is stored online in such a SimpleDB. This database contains a list of the IDs of all uploaded archives and their names, hashes, sizes and other meta data. You must have bookkeeping enable to allow the search command to work.

Vault management.
-----------------
Vault management including creating, listing and removing of vaults is provided via the following command line directives.

Creating a vault.
^^^^^^^^^^^^^^^^^

``$ glacier-cmd mkvault <vault name>`` 

.. program-output:: glacier-cmd mkvault -h

Create a vault. It must be preceded by the name of the vault you want to create. Note: vault names are case sensitive, and may only contain characters a-z, A-Z, 0-9, '_' (underscore), '-' (hyphen), and '.' (period). The vault name should be at least one, and no more than 255 characters in length.

::

 $ glacier-cmd mkvault Test
 +-----------+-------------------------------------------------+
 |   Header  |                      Value                      |
 +-----------+-------------------------------------------------+
 | RequestId | EEw55d4pLutq_mM14U2V3jSeKUilNyv5DDVxaWiRxQs6qw0 |
 |  Location |            /335522851586/vaults/Test            |
 +-----------+-------------------------------------------------+


Listing available vaults.
^^^^^^^^^^^^^^^^^^^^^^^^^

``$ glacier-cmd lsvault``

.. program-output:: glacier-cmd lsvault -h

Give an overview of the available vaults. ::

 +-------------+---------------------------------------------------------------+--------------------------+-----------------+
 |     Size    |                              ARN                              |         Created          |    Vault name   |
 +-------------+---------------------------------------------------------------+--------------------------+-----------------+
 |   66782456  |       arn:aws:glacier:us-east-1:335522851586:vaults/Test      | 2012-10-03T04:42:42.251Z |       Test      |
 +-------------+---------------------------------------------------------------+--------------------------+-----------------+


Describing status of a vault.
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

``$ glacier-cmd decribevault <vault name>``

.. program-output:: glacier-cmd describevault -h

Produces a table containing an overview of the status of a vault, including the number of archives, the size, and when the vault was created. ::

    $ glacier-cmd describevault Test
    200 OK
    +--------------------------+----------+----------+----------------------------------------------------+--------------------------+
    |      LastInventory       | Archives |   Size   |                        ARN                         |         Created          |
    +--------------------------+----------+----------+----------------------------------------------------+--------------------------+
    | 2012-09-14T20:14:31.609Z |    19    | 66782456 | arn:aws:glacier:us-east-1:771747372727:vaults/Test | 2012-08-30T03:26:05.507Z |
    +--------------------------+----------+----------+----------------------------------------------------+--------------------------+

Deleting a vault.
^^^^^^^^^^^^^^^^^

``$ glacier-cmd rmvault <vault name>`` 

.. program-output:: glacier-cmd rmvault -h

Delete a vault. Only empty vaults can be deleted, if you have archives in a vault you must delete these archives first. An error will be shown if you try to delete a non-empty vault.

::

 $ glacier-cmd rmvault Test
 +-----------+-------------------------------------------------+
 |   Header  |                      Value                      |
 +-----------+-------------------------------------------------+
 | RequestId | JsEMXEx3_1gOW_wKKWRjQpBCv2qilMOudEgcxCFH9GPPpb4 |
 +-----------+-------------------------------------------------+

Listing inventory of a vault.
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

``$ glacier-cmd inventory <vault name>``

.. program-output:: glacier-cmd inventory -h

List the latest inventory of a vault.

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

Jobs are tasks that run on the Amazon Glacier servers. There are two types of jobs: inventory retrieval jobs and archive retrieval jobs.

Listing jobs.
^^^^^^^^^^^^^

``$ glacier-cmd listjobs <vault name>``

.. program-output:: glacier-cmd listjobs -h

Give an overview of current jobs and their status.

::

 $ glacier-cmd listjobs Test
 +----------------------------------------------------+----------------------------------------------------------------------------------------------+--------------------------------------------------------------------------------------------------------------------------------------------+--------------------+--------------------------+------------+
 |                      VaultARN                      |                                            Job ID                                            |                                                                 Archive ID                                                                 |       Action       |        Initiated         |   Status   |
 +----------------------------------------------------+----------------------------------------------------------------------------------------------+--------------------------------------------------------------------------------------------------------------------------------------------+--------------------+--------------------------+------------+
 | arn:aws:glacier:us-east-1:335522851586:vaults/Test | OFDah2UrPJdGlkf8iYENPKZhzHBq262hXdWOk0VTILnIwIP4xnkv7nXf1BcAin0S_e6UfhHPSe7d7q-PJZt9b3Jbt8T4 | aS10l5-JAWA6X5r4uFgUAYucpAde1qoy8jfQQbNM3NNNZyWmNTduZ3uC0o7GNh5MGnTelZUz5ODl3e958LDCjHmG--ckRpTxCK1LbV67tB2N3mPCY3GjvYsBb_ujXHvKl7fTdiP2VA |  ArchiveRetrieval  | 2012-10-11T15:02:53.903Z | InProgress |
 | arn:aws:glacier:us-east-1:335522851586:vaults/Test | 7HS2YzOfydeiyM5NLUIhiLpah2HpurXfFg5_YMpsrqRoIWwpQtPuKGwTrjTFimAL_WZfPsur57wRX0jkKDUORY-0BbmI |                                                                    None                                                                    | InventoryRetrieval | 2012-10-11T01:57:08.135Z | Succeeded  |
 +----------------------------------------------------+----------------------------------------------------------------------------------------------+--------------------------------------------------------------------------------------------------------------------------------------------+--------------------+--------------------------+------------+

Describing jobs.
^^^^^^^^^^^^^^^^

``$ glacier-cmd describejob <vault> <jobid>``

.. program-output:: glacier-cmd describejob -h

Provides more information on a specific job, such as type of job, when it was started, and the current status. ::

 $ glacier-cmd describejob Test 7HS2YzOfydeiyM5NLUIhiLpah2HpurXfFg5_YMpsrqRoIWwpQtPuKGwTrjTFimAL_WZfPsur57wRX0jkKDUORY-0BbmI
 +----------------------+----------------------------------------------------------------------------------------------+
 |        Header        |                                            Value                                             |
 +----------------------+----------------------------------------------------------------------------------------------+
 |    CompletionDate    |                                   2012-10-11T05:55:19.803Z                                   |
 |       VaultARN       |                      arn:aws:glacier:us-east-1:335522851586:vaults/Test                      |
 |    SHA256TreeHash    |                                             None                                             |
 |      Completed       |                                             True                                             |
 | InventorySizeInBytes |                                            21890                                             |
 |        JobId         | 7HS2YzOfydeiyM5NLUIhiLpah2HpurXfFg5_YMpsrqRoIWwpQtPuKGwTrjTFimAL_WZfPsur57wRX0jkKDUORY-0BbmI |
 |       SNSTopic       |                                             None                                             |
 |      ArchiveId       |                                             None                                             |
 |    JobDescription    |                                             None                                             |
 |      RequestId       |                       rP_WWo2itP1SCcJQDCMMpiqB7NDtEqIvH1TuNoHjpBvNpA8                        |
 |      StatusCode      |                                          Succeeded                                           |
 |        Action        |                                      InventoryRetrieval                                      |
 |     CreationDate     |                                   2012-10-11T01:57:08.135Z                                   |
 |    StatusMessage     |                                          Succeeded                                           |
 |  ArchiveSizeInBytes  |                                             None                                             |
 +----------------------+----------------------------------------------------------------------------------------------+ 

Archive management.
-------------------

You may upload, retrieve, download and delete archives using glacier-cmd.

Note that when deleting a file, it takes up to a day for Glacier to update your inventory and actually delist the archive from your vault.

When downloading a file, you first must request the file to be retrieved by Glacier before you can download it. This retrieval process takes around four hours, and the file will be available for download for 24 hours after which it is removed from the available queue.

Uploading an archive.
^^^^^^^^^^^^^^^^^^^^^

``$ glacier-cmd upload <vault name> /path/to/archive [path/to/anotherarchive]``

.. command-output:: glacier-cmd upload -h

You may add an arbitrary number of files on the command line, or use wildcards in the file names.

Files are uploaded in blocks, the default size is the smallest possible size to fit the file in no more than 10,000 blocks. When uploading data piped in via stdin, a default block size of 128 MB is used. After the upload of each block a progress update will be printed, showing the amount of data uploaded, the upload speed and an estimated finish time. When finished, the archive ID and an SHA256 hash will be printed.

Note: for files larger than 1 MB this hash is not the same as you get when running the ``sha256sum /path/to/archive`` command as the hash is a tree hash, calculated by taking the individual hashes of each 1 MB part of the file, and hashing those together. Use the ``$ glacier-cmd treehash <filename>`` as described below to calculate hashes of local files.

Uploading options.
""""""""""""""""""
* ``--stdin``

Use this option to tell glacier-cmd to expect data to be piped in over stdin. ::

   $ cat /path/to/archive | glacier-cmd upload Test --description "Interesting data!" --name /nice/filename/for/archive --stdin

* ``--name``

Specify a file name for your archive. 

This is required when you pipe in data over stdin, and can be useful to override the local file name of the archive, for example when the local file is a temporary file with a randomly generated name. This file name will be used for the bookkeeping entry of this upload. ::

   $ glacier-cmd upload --name /path/BetterName Test /tmp/temp.tQ6948 "Some description"

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

* ``--description "description of archive"``

Set a description of your archive. This may be up to 1024 characters long, and will be listed in the inventory of your vault, and stored in the bookkeeping database. If no description given, the file name of the archive is used instead. The description may contain only 7-bit ASCII characters without control codes, specifically ASCII values 32-126 decimal or 0x20-0x7E hexadecimal.

* ``--uploadid <uploadid>``

Resume an interrupted job with the specified uploadid. If this option is present, ``glacier-cmd`` will check wether this uploadid exists, and if so check the hashes of the already uploaded parts to the local file. If all parts match, the upload will be resumed. If there is any problem, an error message will be shown.

* ``--resume``

Not implemented yet.

Attempt to automatically resume an upload using information stored in the bookkeeping database. This option requires :doc:`Bookkeeping` to be enabled.

* ``--bacula``

The file name is a bacula-style list of multiple files. This is useful if this script is used in conjunction with the Bacula backup software. Bacula separates files with the `|` character; see :doc:`Scripting` for more details.
The file list should look like ``/path/to/backups/vol001|vol002|vol003``, with the path given by the user script.

Downloading an archive.
^^^^^^^^^^^^^^^^^^^^^^^

This is a two-step process as first you have to instruct Glacier to retrieve an archive and make it available for download via ``getarchive``, and when that job is done it can be downloaded using ``download``.

Retrieve the archive from storage.
""""""""""""""""""""""""""""""""""

* ``$ glacier-cmd getarchive <vault> <archive-ID>`` 

.. program-output:: glacier-cmd getarchive -h

Start a job retrieving the archive with given archive ID from the vault. This takes about four hours. If a job for the same archive is running already, or is finished, it will notify the user of the status of this job.

Note: if the archive ID starts with a hyphen (-) then it must be preceded by the ``--`` command line switch. ::

 $ glacier-cmd getarchive Test aS10l5-JAWA6X5r4uFgUAYucpAde1qoy8jfQQbNM3NNNZyWmNTduZ3uC0o7GNh5MGnTelZUz5ODl3e958LDCjHmG--ckRpTxCK1LbV67tB2N3mPCY3GjvYsBb_ujXHvKl7fTdiP2VA
 +---------------------+----------------------------------------------------------------------------------------------+
 |        Header        |                                            Value                                             |
 +----------------------+----------------------------------------------------------------------------------------------+
 |    CompletionDate    |                                             None                                             |
 |       VaultARN       |                arn:aws:glacier:us-east-1:335522851586:vaults/Squirrel_backup                 |
 |       SNSTopic       |                                             None                                             |
 |    SHA256TreeHash    |               90175184b2b4667ec826b66b9f86ee73644accd1cdaaa5cb7ff6ef176cf39741               |
 |      Completed       |                                            False                                             |
 | InventorySizeInBytes |                                             None                                             |
 |        JobId         | OFDah2UrPJdGlkf8iYENPKZhzHBq262hXdWOk0VTILnIwIP4xnkv7nXf1BcAin0S_e6UfhHPSe7d7q-PJZt9b3Jbt8T4 |
 |    JobDescription    |                                             None                                             |
 |      StatusCode      |                                          InProgress                                          |
 |        Action        |                                       ArchiveRetrieval                                       |
 |     CreationDate     |                                   2012-10-11T15:02:53.903Z                                   |
 |    StatusMessage     |                                             None                                             |
 |  ArchiveSizeInBytes  |                                           35723460                                           |
 +----------------------+----------------------------------------------------------------------------------------------+


Download the data.
""""""""""""""""""

* ``$ glacier-cmd download <vault> <archive-ID>`` 

.. program-output:: glacier-cmd download -h

Download an archive if it is available. If not available it will inform the user to start an archive retrieval job for it. The download is done as a single block, so no progress updates of the download can be given. It is also not possible to resume an interrupted download at this moment.

Downloading options.
""""""""""""""""""""
* ``--outfile <outfile>``

The name of the file to write the downloaded data to. If omitted, stdout is used.

* ``--overwrite`` 

Overwrite a local file with the same name. If not given, an error will be shown if `<outfile>` exists already.

Deleting an archive.
^^^^^^^^^^^^^^^^^^^^

``$ glacier-cmd rmarchive <vault> <archive-ID>`` ::

.. program-output:: glacier-cmd rmarchive -h

Remove the archive with <archive-ID> from the vault <vault>.

Note: if the archive ID starts wiht a - (hyphen), you must precede it with a ``--`` switch, as otherwise it is recognised as command line option. ::

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

``$ glacier-cmd search``

.. command-output:: glacier-cmd search -h

Search the bookkeeping database for stored archives. Bookkeeping must be enabled for this function to work.

If no options are given, it prints a list of all archives that are stored in the default region. All searches are limited to one region, if no ``--region`` option is set, the default region will be used.

* ``--filename <file name>`` 

Searches for a (partial) match on file name.

* ``--searchterm <search term>`` 

Searches for a (partial) match on description.

* ``<vault>`` 

Limits the search to the given vault.

Managing multipart jobs.
^^^^^^^^^^^^^^^^^^^^^^^^

Uploads are sent block by block, when an upload is in progress (or halted) a multipart job is present in that vault. After about 24 hours of no activity, these jobs are removed and any uploaded data is lost.

List uploads in progress.
^^^^^^^^^^^^^^^^^^^^^^^^^

``$ glacier-cmd listmultiparts <vault>``

.. program-output:: glacier-cmd listmultiparts -h

List the multipart uploads currently in progress, with or without current activity. ::

    $ glacier-cmd listmultiparts Test
    200 OK
    Marker:  None
    +--------------------+--------------------------+----------------------------------------------------------------------------------------------+-----------------+----------------------------------------------------+
    | ArchiveDescription |       CreationDate       |                                      MultipartUploadId                                       | PartSizeInBytes |                      VaultARN                      |
    +--------------------+--------------------------+----------------------------------------------------------------------------------------------+-----------------+----------------------------------------------------+
    |  fancyme.glacier   | 2012-09-20T04:29:21.485Z | D18RNXeq5ffV99PITXrHBvJOULDt15EJJl0eBD5GFD-pc76ptWCz0k9mrJy4W4oUu2fQ0ljWxiqDXIKGLZVIfFIexErC |     4194304     | arn:aws:glacier:us-east-1:771747372727:vaults/Test |
    +--------------------+--------------------------+----------------------------------------------------------------------------------------------+-----------------+----------------------------------------------------+


Abort an upload.
^^^^^^^^^^^^^^^^

``$ glacier-cmd abortmultipart <vault> <uploadid>`` 

.. program-output:: glacier-cmd abortmultipart -h

Abort a multipart upload that is in progress. After giving this command that multipart upload can not be resumed.

Tree hashing.
-------------

``$glacier-cmd treehash <filename>``

.. program-output:: glacier-cmd treehash -h

Amazon uses a special way of taking an SHA256 hash from a file: they use a tree hash. This means the normal ``sha256hash`` command will give a different hash than Amazon for files larger than 1 MB.

To calculate the tree hash from a local file, to compare with the hash Amazon provides, you may use the ``treehash`` command where filename may be a list of files, and may contain wildcards. ::

 $ glacier-cmd treehash *.jpg
 +--------------+------------------------------------------------------------------+
 |  File name   |                         SHA256 tree hash                         |
 +--------------+------------------------------------------------------------------+
 | P1050041.jpg | 7c5aa9d2af811f41abf0db7756623e2c9b09af09c28618ca891932cff3b3e3ed |
 | P1050044.jpg | 829f91b33d26abd636f732f205590f58f6824cf07460b3b6bef0778d911e5e3d |
 | P1050052.jpg | 5427a1488db2a0dab25d7a247d16e110c1342a291528c5025c7280b640da9c75 |
 | P1050068.jpg | 05278217d88dab5a7d1f7bcbe8b698f2d5cc284e1eb687d97f5185e8026a089d |
 +--------------+------------------------------------------------------------------+


