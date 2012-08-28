Amazon Glacier CLI
==================

Command line interface for Amazon Glacier
-----------------------------------------

Required libraries are glacier (which is included into repository) and boto - at the moment you still need to use development branch of boto (which you can get by running `pip install --upgrade git+https://github.com/boto/boto.git`).  

While you can pass in your AWS Access and Secret key (`--aws-access-key` and `--aws-secret-key`), it is recommended that you create `glacier_settings.py` file into which you put `AWS_ACCESS_KEY` and `AWS_SECRET_KEY` strings.

You can also put `REGION` into `glacier_settings.py` to specify the default region on which you will operate (default is `us-east-1`). When you want to operate on a non-default region you can pass in the `--region` settings to the commands.

It is recommended that you enable `BOOKKEEPING` in `glacier_settings.py` to allow for saving cache information into Amazon SimpleDB database.

You have two options to retrieve an archive - first one is `download`, second one is `getarchive`.

If you use `download`, you will have to uniquely identify the file either by its file name, its description, or limit the search by region and vault. If that is not enough you should use `getarchive` and specify the archive ID of the archive you want to retrieve.

Positional arguments:  

	lsvault	[--region REGION]										List vaults
	mkvault	[--region REGION] vault									Create a new vault
	rmvault	[--region REGION] vault									Remove vault
	listjobs [--region REGION] vault								List jobs
	describejob [--region REGION] vault jobid						Describe job
	upload [--region REGION] vault filename [description ...]		Upload an archive
	download [--region REGION] filename								Only if BOOKKEEPING is enabled: Download an archive by searching through SimpleDB cache. Result must be unique (one archive) - if not, specify --region, --vault, or use getarchive to specify archive ID of the archive you want to download. 
			 [--vault VAULT]										
			 [--out-file OUT_FILE]									If you pass in --out-file parameter, output will be downloaded into out_file. Otherwise it will be outputted straight into command line (stdout).
	getarchive [--region REGION] vault archive [filename]			Download an archive. Specify filename if you want it to output to file, other it will dump plain output into command line.
	rmarchive [--region REGION] vault archive						Remove archive
	inventory [--region REGION] vault								List inventar of a vault
	search [--region REGION] [--vault VAULT] search_term			If BOOKKEEPING is enabled, search through SimpleDB for search_term
  
Optional arguments:  
  
	--aws-access-key AWS_ACCESS_KEY
                      Required if you haven't created glacier_settings.py
                      file with AWS_ACCESS_KEY and AWS_SECRET_KEY in it. Command
                      line keys will override keys set in
                      glacier_settings.py.
	--aws-secret-key AWS_SECRET_KEY
                      Required if you haven't created glacier_settings.py
                      file with AWS_ACCESS_KEY and AWS_SECRET_KEY in it. Command
                      line keys will override keys set in
                      glacier_settings.py.

