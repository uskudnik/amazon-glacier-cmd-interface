Amazon Glacier CLI
==================

Command line interface for Amazon Glacier
-----------------------------------------

Required libraries are glacier (which is included into repository) and boto - at the moment you still need to use development branch of boto (which you can get by running "pip install --upgrade git+https://github.com/boto/boto.git").  

While you can pass in your AWS Access and Secret key (--aws-access-key and --aws-secret-key), it is recommended that you create glacier_settings.py file into which you put AWS_ACCESS_KEY and AWS_SECRET_KEY strings.  

You can also put REGION into glacier_settings.py to specify the default region on which you will operate (default is us-east-1). When you want to operate on a non-default region you can pass in the --region settings to the commands.  
 
Positional arguments:  

	lsvault	[--region REGION]										List vaults
	mkvault	[--region REGION] vault									Create a new vault
	rmvault	[--region REGION] vault									Remove vault
	listjobs [--region REGION] vault								List jobs
	describejob [--region REGION] vault jobid						Describe job
	upload [--region REGION] vault filename [description ...]		Upload an archive
	download [--region REGION] vault archive [filename]				Download an archive
	rmarchive [--region REGION] vault archive						Remove archive
	inventory [--region REGION] vault								List inventar of a vault
  
Optional arguments:  
  
	--aws-access-key 		AWS_ACCESS_KEY  
	--aws-secret-key 		AWS_SECRET_KEY  
