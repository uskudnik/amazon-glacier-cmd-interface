Amazon Glacier CLI
==================

Command line interface for Amazon Glacier. Allows managing vaults, uploading
and downloading archives and bookkeeping of created archives.

Installation:
-------------

Required libraries are glaciercorecalls (temporarily, while we wait for glacier 
support to land in boto's develop branch) and boto - at the moment you still 
need to use development branch of boto.

    >>> python setup.py install
    >>> glacier [args] 

Development:
------------

Currently use of `virtualenv` is recommended, but we will migrate to buildout shortly:

    >>> virtualenv --no-site-packages --python=python2.7 amazon-glacier-cmd-interface
    >>> cd amazon-glacier-cmd-interface && source bin/activate
    >>> python setup.py develop
    >>> glacier command [args]

Usage:
------

There are a couple of ways to pass in settings. While you can pass in everything
on command line you can also cretate config file `.glacier` in your home folder
or in folder where you run glacier(current working directory). To speciffy speciall
location of your config file use `-c` option on command line.

Here is an example configuration:

    [aws]
    access_key=your_access_key
    secret_key=your_secret_key

    [glacier]
    region=us-east-1
    bookkeeping=True
    bookkeeping-domain-name=your_simple_db_domain_name

You can also pass in all these options as environemnt variables:

    $ aws_access_key=your_access_key aws_secret_key=your_secret_key region=us-east-1 bookkeeping=True bookkeeping-domain-name=your_simple_db_domain_name glacier [args]

It doesn't matter if option names are upper-case or lower-case or if they have 
`aws_` in string. Currently only section names must be lower-case.

We created a special feature called bookkeeping, where we keep a cache of all uploaded
archive and their names, hashes, sizes and similar meta-data in an Amazon SimpleDB.
This is still work in progress and can be enabled by setting bookkeeping to True.
Some commands like search require bookkeeping to be enabled. You will also have
to set bookkeeping-domain-name:

    $ TODO: example here

To list your vault contents use `lsvault`, to create vault use `mkvault` and to
remove use `rmvault` obvious:

    $ glacier mkvault Test
    201 Created
    /487528549940/vaults/Test

    $ glacier lsvault
    200 OK
    +------------+----------------------------------------------------+--------------------------+----------+
    | Vault name |                        ARN                         |         Created          |   Size   |
    +------------+----------------------------------------------------+--------------------------+----------+
    |    Test    | arn:aws:glacier:us-east-1:771747372727:vaults/Test | 2012-08-30T03:26:05.507Z | 56932337 |
    +------------+----------------------------------------------------+--------------------------+----------+


    $ glacier rmvault Test
    204 No Content
    +------------------+-------------------------------------------------+
    |      Header      |                      Value                      |
    +------------------+-------------------------------------------------+
    | x-amzn-requestid | 5Ckitc3kUKC30UWrflkKNLK_hJFm1c_Y7lm4ZG2MAkcInI8 |
    |       date       |          Wed, 12 Sep 2012 05:51:00 GMT          |
    +------------------+-------------------------------------------------+


You can list active jobs by using `listjobs`:

    $ glacier listjobs Test
    200 OK
    +--------------------+------------+-----------+--------------------------+----------------------------------------------------+----------------------------------------------------------------------------------------------+
    |       Action       | Archive ID |   Status  |        Initiated         |                      VaultARN                      |                                            Job ID                                            |
    +--------------------+------------+-----------+--------------------------+----------------------------------------------------+----------------------------------------------------------------------------------------------+
    | InventoryRetrieval |    None    | Succeeded | 2012-09-12T01:03:13.991Z | arn:aws:glacier:us-east-1:771747372727:vaults/Test | tOMuoC8Y0B9S867fZsczjZBUS02mnELuS1-WqTY_SCCnNPWQg85YRI3GoJe6eObGuPEBdRz6BeXb35PQWBokHBhPqZ0X |
    | InventoryRetrieval |    None    | Succeeded | 2012-09-11T06:37:22.950Z | arn:aws:glacier:us-east-1:771747372727:vaults/Test | TK27LnflXEXN9ACn-ShfvQXHnJxFRVWnwnPiR-2d0eyePFHs_xrFRkAq1TEgxzM1oWo06tTUPbtGCnHmiL7Hon9anlik |
    +--------------------+------------+-----------+--------------------------+----------------------------------------------------+----------------------------------------------------------------------------------------------+


To upload archive use `upload`. You can upload data from file or data from
stdin. To upload from file:

    $ glacier upload Test /path/SomeFile "The file description"
    Created archive with ID: EQocIYw9ZmofbWixjD2oKb8faeIg4D1uSi1PxpdyBVy__lDMCWcmXLIzNKBP4ikPH3Ngn4w8ApqCMN7XJqNL7V4sxRzq42Zu74DctpLG9GSPSNjLc1_vorGVk3YqVEdjd2cqnWTdiA
    Archive SHA256 hash: e837acd31ee9b04a73fb176f1845695364dfabe019fca17f4097cf80687082c0

You can compare the SHA256 returned by AWS with the locally computed one to
make sure the upload was successful:

    $ shasum -a 256 SomeFile
    e837acd31ee9b04a73fb176f1845695364dfabe019fca17f4097cf80687082c0  SomeFile

If you are uploading a temp file with a meaningless name, or using --stdin, you
can use the --name option to tell glacier to ignore the filename and use the
given name when it creates the bookkeeping entry:

    $ glacier upload --name /path/BetterName Test /tmp/temp.tQ6948 "Some description"

To upload from stdin:

    $ TODO: example for using --stdin

You have two options to retrieve an archive - first one is `download`, 
second one is `getarchive`

If you use `download`, you will have to uniquely identify the file either by 
its file name, its description, or limit the search by region and vault. 
If that is not enough you should use `getarchive` and specify the archive ID of
the archive you want to retrieve:

    $ TODO: example here

To remove uploaded archive use `rmarchive`. You can currently delete only by
archive id (notice the use of `--` when the archive ID starts with a dash):

    $ glacier rmarchive Test -- -6AKuLSU3wxtSqq_GeeAss9zLvto8Xr1su4mqmvluTTv4HcXbFJJNy0yiTu9tG5vFjrBXvmQKXGwFJpNMghqYBerUKpsjq56mrzv1wUbe6DWuzl6Ntb8WSQHYo0kzw8rcLaVx5MFug
    204 No Content
    +------------------+-------------------------------------------------+
    |      Header      |                      Value                      |
    +------------------+-------------------------------------------------+
    | x-amzn-requestid | 1-UC36MM2ZxNwdf-Q2yyT0f7j5KVJ1neGwf-FzsU2H6YDyo |
    |       date       |          Fri, 14 Sep 2012 02:48:46 GMT          |
    +------------------+-------------------------------------------------+

To search for uploaded arhives in your cache use `search`. This requires bookkeeping
enabled:

    $ TODO: example here

To list the inventory of a vault use `inventory`:

    $ glacier inventory Test
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

    $ glacier describevault Test
    200 OK
    +--------------------------+----------+----------+----------------------------------------------------+--------------------------+
    |      LastInventory       | Archives |   Size   |                        ARN                         |         Created          |
    +--------------------------+----------+----------+----------------------------------------------------+--------------------------+
    | 2012-09-14T20:14:31.609Z |    19    | 44056372 | arn:aws:glacier:us-east-1:771548372826:vaults/Test | 2012-08-30T03:26:05.507Z |
    +--------------------------+----------+----------+----------------------------------------------------+--------------------------+


Usage description(help):

    positional arguments:
    {lsvault,mkvault,rmvault,listjobs,describejob,upload,getarchive,rmarchive,search,inventory,download}
        lsvault             List vaults
        mkvault             Create a new vault
        rmvault             Remove vault
        listjobs            List jobs
        describejob         Describe job
        upload              Upload an archive
        getarchive          Get a file by explicitly setting archive id
        rmarchive           Remove archive
        search              Search SimpleDB database (if it was created)
        inventory           List inventory of a vault
        download            Download a file by searching through SimpleDB cache
                            for it.
        describevault       Describe a vault

    optional arguments:
    -h, --help            show this help message and exit
    -c FILE, --conf FILE  Specify config file

    aws:
    --aws-access-key AWS_ACCESS_KEY
                            Your aws access key (Required if you haven't created
                            .glacier config file)
    --aws-secret-key AWS_SECRET_KEY
                            Your aws secret key (Required if you haven't created
                            .glacier config file)

    glacier:
    --region REGION       Region where glacier should take action (Required if
                            you haven't created .glacier config file)
    --bookkeeping         Should we keep book of all creatated archives. This
                            requires a SimpleDB account and it's bookkeeping
                            domain name set
    --bookkeeping-domain-name BOOKKEEPING_DOMAIN_NAME
                            SimpleDB domain name for bookkeeping.

TODO:
-----

- Integrate with boto
- Support for output status codes
- Migrate documentation to sphinx
- Documentation examples of output from speciffic commands
- Description for command line arguments
- Tests

Changelog:
----------

    TODO

License:
--------

MIT License
