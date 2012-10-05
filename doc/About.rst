
******************
Amazon Glacier CLI
******************

A command line interface and library for Amazon Glacier. It allows managing vaults, uploading and downloading of archives, and managing inventory using an Amazon SimpleDB database for bookkeeping.

Key to this software is the GlacierWrapper library, a higher-level library around the general Amazon Glacier interface, allowing for easy archive management.

Key features include:
- Vault management (creating, removing, inventory, etc).
- Archive management (upload, download, removal, etc).
- Bookkeeping: keepking track of your archives with original upload date, size, original file name, description, etc using the Amazon SimpleDB service.
- Search function: search the bookkeeping database for your archives.

Planned features:
- automatic resumption of interrupted uploads.
- automatic download of archives following a retrieval request.

This software depends on the Boto library (see http://docs.pythonboto.org/en/latest/index.html) for making connections to Amazon Web Services.
