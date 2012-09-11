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

We created speciall feature called bookkeeping, where we keep cache of all uploaded
archive and it's names, hashes, sizes and similar meta-data in amazon SimpleDB.
This is still work in progress and can be enabled by setting bookkeeping to True.
Some commands like search require bookkeeping to be enabled. You will also have
to set bookkeeping-domain-name:

    $ TODO: example here

To list your vault contents use `lsvault`, to create vault use `mkvault` and to
remove use `rmvault` obvious:

    $ glacier mkvault
    $ 201 Created
    $ /487528549940/vaults/test1

    $ glacier lsvault      
    $ 200 OK
    $ Vault name	ARN	Created	Sizei
    $ test1	arn:aws:glacier:us-east-1:487528549940:vaults/test1	2012-09-11T08:52:56.309Z	0

    $ glacier rmvault test1
    $ 204 No Content

You can list active jobs by using `listjobs`:

    $ glacier listjobs test
    $ 200 OK
    $ Action	Archive ID	Status	Initiated	VaultARN	Job ID
    $ InventoryRetrieval	None	InProgress	2012-09-11T08:50:11.224Z	arn:aws:glacier:us-east-1:487528549940:vaults/test	yvBx6FG7yo5Vocr4Aq-Rv7yY0Cfx0Gpcapr6IevhvJvEgIUwC1yI-s74RQlsd0ESOriFiKO7uHkhmZ9zih069eNsPi-0

To upload archive use `upload`. You can upload data from file or data from stdin:

    $ TODO: example here

You have two options to retrieve an archive - first one is `download`, 
second one is `getarchive`

If you use `download`, you will have to uniquely identify the file either by 
its file name, its description, or limit the search by region and vault. 
If that is not enough you should use `getarchive` and specify the archive ID of
the archive you want to retrieve:

    $ TODO: example here

To remove uploaded archive use `rmarchive`. You can currently delete only by
archive id:

    $ TODO: example here

To search for uploaded arhives in your cache use `search`. This requires bookkeeping
enabled:

    $ TODO: example here

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
