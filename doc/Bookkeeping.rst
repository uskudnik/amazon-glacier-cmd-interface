.. Bookkeeping:

************
Bookkeeping.
************
One of the major drawbacks of Amazon Glacier is that it will not keep track of what you actually put into your vault. All your files will be assigned an ArchiveId instead of a file name, you only have the description to go by. Also inventory taking is painfully slow and done no more than once a day, so to keep track of your files your own bookkeeping is a must.

Luckily ``glacier-cmd`` tries to make this easy on you, by using Amazon SimpleDB to store your vault inventory details.

To use this feature, you must create an Amazon SimpleDB domain name. You can do this via the general AWS control panel. Then add your domain name to the ``glacier-cmd`` configuration, and it will automatically store your upload information in that database. For most use cases, using SimlpeDB is free of charge, refer to the online documentation on the free use tier and charges.

Without bookkeeping ``glacier-cmd`` will still work, but it will miss important features, and some functions such as ``search`` do not work at all as it tries to search the bookkeeping database. 

So while not mandatory, setting up a SimpleDB domain for use with ``glacier-cmd`` is highly recommended.
