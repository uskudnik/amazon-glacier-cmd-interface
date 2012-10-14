Release notes
=============

**15/10/2012: Bookkeeping database layout has changed a bit, the old format would cause problems if multiple files with the same name were uploaded to a vault. If you are upgrading this tool, run `glacier-cmd updatedb` once to update your bookkeeping database to the new layout. If you do not use bookkeeping, no need for this.**

**WARNING: make sure this SimpleDB domain is only used for glacier-cmd bookkeeping data storage, as all items that are not recognised will be cleaned up in the process.**

**Command line parameter description changed from positional argument to optional argument. This means from now on you must add `--description <description>` on the command line to give a description. This to allow for multiple file names and wild cards to be used in conjunction with the `upload` subcommand.**

**Renamed configuration file from `.glacier` to `.glacier-cmd` to reflect new name of this utility.** 

**Glacier command line utility was renamed from `glacier` to `glacier-cmd`, because of inconsistencies with boto.**

**For everybody having problems with install, don't forget to install git.**

Amazon Glacier CLI
==================

Command line interface for Amazon Glacier. Allows managing vaults, uploading
and downloading archives and bookkeeping of created archives.

Installation:
-------------

Required libraries are glaciercorecalls and boto, use version 2.6.0 or newer.

You also need to install GIT, with something like `apt-get install git` to download sources from github.

    >>> python setup.py install
    >>> glacier-cmd [args] 

Development:
------------

Currently use of `virtualenv` is recommended, but we will migrate to buildout shortly:

    >>> virtualenv --no-site-packages --python=python2.7 amazon-glacier-cmd-interface
    >>> source amazon-glacier-cmd-interface/bin/activate
    >>> python setup.py develop
    >>> glacier-cmd command [args]

Usage:
------

There are a couple of ways to pass in settings. While you can pass in everything
on command line you can also create a config file `.glacier-cmd` in your home folder
or in folder where you run glacier (current working directory) or a global
configuration file called `/etc/glacier-cmd.conf`. To specify special
location of your config file use `-c` option on command line.

Here is an example configuration:

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

You can also pass in all these options as environment variables:

    $ aws_access_key=your_access_key aws_secret_key=your_secret_key region=us-east-1 bookkeeping=True bookkeeping-domain-name=your_simple_db_domain_name glacier [args]

It does not matter if option names are upper-case or lower-case or if they have 
`aws_` in string. Currently only section names must be lower-case.

We created a special feature called bookkeeping, where we keep a cache of all uploaded
archive and their names, hashes, sizes and similar meta-data in an Amazon SimpleDB.
This is still work in progress and can be enabled by setting bookkeeping to True.
Some commands like search require bookkeeping to be enabled. You will also have
to set bookkeeping-domain-name:

    $ TODO: example here

To list your vault contents use `lsvault`, to create vault use `mkvault` and to
remove use `rmvault` obvious:

    $ glacier-cmd mkvault Test
    201 Created
    /487528549940/vaults/Test

    $ glacier-cmd lsvault
    200 OK
    +------------+----------------------------------------------------+--------------------------+----------+
    | Vault name |                        ARN                         |         Created          |   Size   |
    +------------+----------------------------------------------------+--------------------------+----------+
    |    Test    | arn:aws:glacier:us-east-1:771747372727:vaults/Test | 2012-08-30T03:26:05.507Z | 56932337 |
    +------------+----------------------------------------------------+--------------------------+----------+


    $ glacier-cmd rmvault Test
    204 No Content
    +------------------+-------------------------------------------------+
    |      Header      |                      Value                      |
    +------------------+-------------------------------------------------+
    | x-amzn-requestid | 5Ckitc3kUKC30UWrflkKNLK_hJFm1c_Y7lm4ZG2MAkcInI8 |
    |       date       |          Wed, 12 Sep 2012 05:51:00 GMT          |
    +------------------+-------------------------------------------------+


You can list active jobs by using `listjobs`:

    $ glacier-cmd listjobs Test
    200 OK
    +--------------------+------------+-----------+--------------------------+----------------------------------------------------+----------------------------------------------------------------------------------------------+
    |       Action       | Archive ID |   Status  |        Initiated         |                      VaultARN                      |                                            Job ID                                            |
    +--------------------+------------+-----------+--------------------------+----------------------------------------------------+----------------------------------------------------------------------------------------------+
    | InventoryRetrieval |    None    | Succeeded | 2012-09-12T01:03:13.991Z | arn:aws:glacier:us-east-1:771747372727:vaults/Test | tOMuoC8Y0B9S867fZsczjZBUS02mnELuS1-WqTY_SCCnNPWQg85YRI3GoJe6eObGuPEBdRz6BeXb35PQWBokHBhPqZ0X |
    | InventoryRetrieval |    None    | Succeeded | 2012-09-11T06:37:22.950Z | arn:aws:glacier:us-east-1:771747372727:vaults/Test | TK27LnflXEXN9ACn-ShfvQXHnJxFRVWnwnPiR-2d0eyePFHs_xrFRkAq1TEgxzM1oWo06tTUPbtGCnHmiL7Hon9anlik |
    +--------------------+------------+-----------+--------------------------+----------------------------------------------------+----------------------------------------------------------------------------------------------+


To upload archive use `upload`. You can upload data from file or data from
stdin. To upload from file:

    $ glacier-cmd upload Test /path/SomeFile --description "The file description"
    Created archive with ID: EQocIYw9ZmofbWixjD2oKb8faeIg4D1uSi1PxpdyBVy__lDMCWcmXLIzNKBP4ikPH3Ngn4w8ApqCMN7XJqNL7V4sxRzq42Zu74DctpLG9GSPSNjLc1_vorGVk3YqVEdjd2cqnWTdiA
    Archive SHA256 hash: e837acd31ee9b04a73fb176f1845695364dfabe019fca17f4097cf80687082c0

You can only compare the SHA256 returned by AWS with the locally computed one (using the `shasum` utility) if your archive was under 1Mb. Use the built-in treehash function instead.

    $ glacier-cmd treehash SomeFile
    e837acd31ee9b04a73fb176f1845695364dfabe019fca17f4097cf80687082c0  SomeFile

For files larger than 1Mb, a special SHA256 needs to be computed. There are
plans to update the tool in the future to compute these special SHA256 values
off-line.

If you are uploading a temp file with a meaningless name, or using --stdin, you
can use the --name option to tell glacier to ignore the file name and use the
given name when it creates the bookkeeping entry:

    $ glacier-cmd upload Test /tmp/temp.tQ6948 --description "Some description" --name /path/BetterName

To upload from stdin:

    $ cat file | glacier-cmd upload Test --description "Some description" --stdin  --name /path/BetterName

IMPORTANT NOTE: If you're uploading from stdin, and you don't specify a
--partsize option, your upload will be limited to 1.3Tb, and the progress
report will come out every 128Mb. For more details, run:

    $ glacier-cmd upload -h

You have two options to retrieve an archive - first one is `download`, 
second one is `getarchive`

If you use `download`, you will have to uniquely identify the file either by 
its file name, its description, or limit the search by region and vault. 
If that is not enough you should use `getarchive` and specify the archive ID of
the archive you want to retrieve:

    $ TODO: example here

To remove uploaded archive use `rmarchive`. You can currently delete only by
archive id (notice the use of `--` when the archive ID starts with a dash):

    $ glacier-cmd rmarchive Test -- -6AKuLSU3wxtSqq_GeeAss9zLvto8Xr1su4mqmvluTTv4HcXbFJJNy0yiTu9tG5vFjrBXvmQKXGwFJpNMghqYBerUKpsjq56mrzv1wUbe6DWuzl6Ntb8WSQHYo0kzw8rcLaVx5MFug
    204 No Content
    +------------------+-------------------------------------------------+
    |      Header      |                      Value                      |
    +------------------+-------------------------------------------------+
    | x-amzn-requestid | 1-UC36MM2ZxNwdf-Q2yyT0f7j5KVJ1neGwf-FzsU2H6YDyo |
    |       date       |          Fri, 14 Sep 2012 02:48:46 GMT          |
    +------------------+-------------------------------------------------+

To search for uploaded archives in your cache use `search`. This requires bookkeeping
enabled:

    $ TODO: example here

To list the inventory of a vault use `inventory`:

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

To describe a vault use `describevault`. It shows the time of the last inventory among other things:

    $ glacier-cmd describevault Test
    200 OK
    +--------------------------+----------+----------+----------------------------------------------------+--------------------------+
    |      LastInventory       | Archives |   Size   |                        ARN                         |         Created          |
    +--------------------------+----------+----------+----------------------------------------------------+--------------------------+
    | 2012-09-14T20:14:31.609Z |    19    | 44056372 | arn:aws:glacier:us-east-1:771747372727:vaults/Test | 2012-08-30T03:26:05.507Z |
    +--------------------------+----------+----------+----------------------------------------------------+--------------------------+

To see the multipart uploads currently in progress, use `listmultiparts`:

    $ glacier-cmd listmultiparts Test
    200 OK
    Marker:  None
    +--------------------+--------------------------+----------------------------------------------------------------------------------------------+-----------------+----------------------------------------------------+
    | ArchiveDescription |       CreationDate       |                                      MultipartUploadId                                       | PartSizeInBytes |                      VaultARN                      |
    +--------------------+--------------------------+----------------------------------------------------------------------------------------------+-----------------+----------------------------------------------------+
    |  fancyme.glacier   | 2012-09-20T04:29:21.485Z | D18RNXeq5ffV99PITXrHBvJOULDt15EJJl0eBD5GFD-pc76ptWCz0k9mrJy4W4oUu2fQ0ljWxiqDXIKGLZVIfFIexErC |     4194304     | arn:aws:glacier:us-east-1:771747372727:vaults/Test |
    +--------------------+--------------------------+----------------------------------------------------------------------------------------------+-----------------+----------------------------------------------------+

To abort one of the multipart uploads, use `abortmultipart` subcommand:

    $ glacier-cmd abortmultipart Test D18RNXeq5ffV99PITXrHBvJOULDt15EJJl0eBD5GFD-pc76ptWCz0k9mrJy4W4oUu2fQ0ljWxiqDXIKGLZVIfFIexErC


Usage description(help):
$ glacier-cmd --help
usage: glacier-cmd [-h] [-c FILE] [--logtostdout]
                   [--aws-access-key AWS_ACCESS_KEY]
                   [--aws-secret-key AWS_SECRET_KEY] [--region REGION]
                   [--bookkeeping]
                   [--bookkeeping-domain-name BOOKKEEPING_DOMAIN_NAME]
                   [--logfile LOGFILE]
                   [--loglevel {-1,DEBUG,0,INFO,1,WARNING,2,ERROR,3,CRITICAL}]
                   [--output {print,csv,json}]


{mkvault,lsvault,describevault,rmvault,upload,listmultiparts,abortmultipart,inventory,getarchive,download,rmarchive,search,listjobs,describejob,treehash}
                  ...

Command line interface for Amazon Glacier

optional arguments:
 -h, --help            show this help message and exit
 -c FILE, --conf FILE  Name of the file to log messages to. (default:
                       ~/.glacier-cmd)
 --logtostdout         Send log messages to stdout instead of the config
                       file. (default: False)

Subcommands:
  {mkvault,lsvault,describevault,rmvault,upload,listmultiparts,abortmultipart,inventory,getarchive,download,rmarchive,search,listjobs,describejob,treehash}
                       For subcommand help, use: glacier-cmd <subcommand> -h
   mkvault             Create a new vault.
   lsvault             List available vaults.
   describevault       Describe a vault.
   rmvault             Remove a vault.
   upload              Upload an archive to Amazon Glacier.
   listmultiparts      List all active multipart uploads.
   abortmultipart      Abort a multipart upload.
   inventory           List inventory of a vault, if available. If not
                       available, creates inventory retrieval job if none
                       running already.
   getarchive          Requests to make an archive available for download.
   download            Download a file by archive id.
   rmarchive           Remove archive from Amazon Glacier.
   search              Search Amazon SimpleDB database for available archives
                       (requires bookkeeping to be enabled).
   listjobs            List active jobs in a vault.
   describejob         Describe a job.
   treehash            Calculate the tree-hash (Amazon style sha256-hash) of
                       a file.

aws:
 --aws-access-key AWS_ACCESS_KEY
                       Your aws access key (Required if you have not created
                       a ~/.glacier-cmd or /etc/glacier-cmd.conf config file)
                       (default: AKIAIP5VPUSCSJQ6BSSQ)
 --aws-secret-key AWS_SECRET_KEY
                       Your aws secret key (Required if you have not created
                       a ~/.glacier-cmd or /etc/glacier-cmd.conf config file)
                       (default: WDgq6ZZn7Y4Lkt5LxPuionw2pTLbonwdFZz1BGtS)

glacier:
 --region REGION       Region where you want to store your archives (Required
                       if you have not created a ~/.glacier-cmd or /etc
                       /glacier-cmd.conf config file) (default: us-east-1)
 --bookkeeping         Should we keep book of all created archives. This
                       requires a Amazon SimpleDB account and its bookkeeping
                       domain name set (default: True)
 --bookkeeping-domain-name BOOKKEEPING_DOMAIN_NAME
                       Amazon SimpleDB domain name for bookkeeping. (default:
                       squirrel)
 --logfile LOGFILE     File to write log messages to. (default: /home/wouter
                       /.glacier-cmd.log)
 --loglevel {-1,DEBUG,0,INFO,1,WARNING,2,ERROR,3,CRITICAL}
                       Set the lowest level of messages you want to log.
                       (default: DEBUG)
 --output {print,csv,json}
                       Set how to return results: print to the screen, or as
                       csv resp. json string. (default: print)


Bandwidth throttling
--------------------

`glacier-cmd` does not by itself support bandwidth throttling and uses all the available bandwidth it can get hold off. Should you require bandwidth throttling you should use a utility designed for such purpose. One such utility is [tc](http://linux.die.net/man/8/tc). A short [example](https://github.com/uskudnik/amazon-glacier-cmd-interface/issues/32#issuecomment-8754845) by @gburca:
    
    TC=/sbin/tc
    IF=eth0
    REGION="us-east-1"
    IP=`dig +short +answer "glacier.${REGION}.amazonaws.com" A | grep -v '\.$' | tr '\n' ' '`
    U32="$TC filter add dev $IF protocol ip parent 1:0 prio 1 u32"

    $TC qdisc add dev $IF root handle 1: htb default 30
    $TC class add dev $IF parent 1: classid 1:2 htb rate 200kbps
    for ip in $IP; do
        $U32 match ip dst $ip/32 flowid 1:2
    done

and later, to disable filtering:
    
    $TC qdisc del dev $IF root


TODO:
-----

- Tests

Changelog:
----------

    TODO

License:
--------

MIT License
