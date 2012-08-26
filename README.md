amazon-glacier-cmd-interface
============================

Command line interface for Amazon Glacier  

Required libraries are glacier (which is included into repository) and boto - at the moment you still need to use development branch of boto (which you can get by running "pip install --upgrade git+https://github.com/boto/boto.git").  

While you can pass in your AWS Access and Secret key (--aws-access-key and --aws-secret-key), it is recommended that you create glacier_settings.py file into which you put AWS_ACCESS_KEY and AWS_SECRET_KEY strings.  

You can also put REGION into glacier_settings.py to specify the default region on which you will operate (default is us-east-1). When you want to operate on a non-default region you can pass in the --region settings to the commands.  
  
positional arguments:  
    lsvault				List vaults  
    mkvault				Create a new vault  
    rmvault				Remove vault  
    listjobs			List jobs  
    describejob			Describe job  
    upload				Upload an archive  
    download			Download an archive  
    rmarchive			Remove archive  
    inventar			List inventar of a vault  
  
optional arguments:  
  -h, --help            this help message and exit  
  --aws-access-key AWS_ACCESS_KEY  
  --aws-secret-key AWS_SECRET_KEY  
