**********
Scripting.
**********

Being a command-line utility, glacier-cmd is very suitable to use in combination with other software, allowing one to greatly automate tasks such as the regular uploading of backup archives.

Encryption and compression.
---------------------------

To encrypt and compress a file before sending it to Glacier:
[TODO: test and check whether this actually works!]

``$ openssl aes-192-cbc -salt -in .glacier | gzip -f | glacier-cmd --name <filename> <vault> "description"``

To decrypt the file, after downloading:

``$ cat <downloaded_file> | gzip -d | openssl aes-192-cbc -d -salt -out <local_filename>``


Bacula.
-------

Bacula is a popular backup software, which allows for scripts to be run after a backup has been created. A possibility is to call glacier-cmd to upload this file to a Glacier vault for off-site backup. This example assumes you backup to a harddisk. ::

Job {
  # other JobDefs.
  RunAfterJob = "/usr/local/bin/glacier-cmd upload <vault> %v %n"
}

This example will pass the volume name as input file name and the job name as description to glacier-cmd for uploading of the volume to <vault>. Bacula will wait until the script finishes, and if successful give an OK on the backup. Note that this may block other backup jobs, if any.

To not block other backup jobs, and run the upload independent from Bacula, use::

Job {
  # other JobDefs.
  RunAfterJob = "echo '/usr/local/bin/glacier-cmd upload <vault> %v %n' | batch"
}

This way it will run the upload as soon as the system is not too busy. In this case, any output from glacier-cmd will be e-mailed to <root@localhost>.


