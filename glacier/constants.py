
# constants definition
CHUNK_SIZE = 1024
DEFAULT_PART_SIZE = 128 # in MB, power of 2.
# After every failed block upload we sleep (SLEEP_TIME * retries) seconds.
# The more retries we've made for one particular block, the longer we sleep
# before re-attempting to re-upload that block.
SLEEP_TIME = 300
# How many retries we should make to upload a particular block. We will not
# give up unless we've made at LEAST this many attempts to upload a block.
BLOCK_RETRIES = 10
# How many retries we should allow for the whole upload. We will not give up
# unless we've made at LEAST this many attempts to upload the archive.
TOTAL_RETRIES = 100
# For large files, the limits above could be surpassed. We also set a per-Gb
# criteria that allows more errors for larger uploads.
MAX_TOTAL_RETRY_PER_GB = 2
HEADERS_OUTPUT_FORMAT = ["csv","json"]
TABLE_OUTPUT_FORMAT = ["csv","json", "print"]
SYSTEM_WIDE_CONFIG_FILENAME = "/etc/glacier-cmd.conf"
USER_CONFIG_FILENAME = "~/.glacier-cmd"
HELP_MESSAGE_CONFIG = u"(Required if you have not created a "
                       "~/.glacier-cmd or /etc/glacier-cmd.conf config file)"
ERRORCODE = {'InternalError': 127,        # Library internal error.
             'UndefinedErrorCode': 126,   # Undefined code.
             'NoResults': 125,            # Operation yielded no results.
             'GlacierConnectionError': 1,  # Can not connect to Glacier.
             'SdbConnectionError': 2,     # Can not connect to SimpleDB.
             'CommandError': 3,           # Command line is invalid.
             'VaultNameError': 4,         # Invalid vault name.
             'DescriptionError': 5,       # Invalid archive description.
             'IdError': 6,                # Invalid upload/archive/job ID given.
             'RegionError': 7,            # Invalid region given.
             'FileError': 8,              # Error related to reading/writing a file.
             'ResumeError': 9,            # Problem resuming a multipart upload.
             'NotReady': 10,              # Requested download is not ready yet.
             'BookkeepingError': 11,      # Bookkeeping not available.
             'SdbCommunicationError': 12, # Problem reading/writing SimpleDB data.
             'ResourceNotFoundException': 13, # Glacier can not find the requested resource.
             'InvalidParameterValueException': 14,  # Parameter not accepted.
             'DownloadError': 15,         # Downloading an archive failed.
             'SNSConnectionError': 126,   # Can not connect to SNS
             'SNSConfigurationError': 127,  # Problem with configuration file
             'SNSParameterError':128,     # Problem with arguments passed to SNS
    }
VAULT_NAME_ALLOWED_CHARACTERS = "[a-zA-Z\.\-\_0-9]+"
ID_ALLOWED_CHARACTERS = "[a-zA-Z\-\_0-9]+"
MAX_VAULT_NAME_LENGTH = 255
MAX_VAULT_DESCRIPTION_LENGTH = 1024
MAX_PARTS = 10000
AVAILABLE_REGIONS = ('us-east-1', 'us-west-2', 'us-west-1',
                     'eu-west-1', 'eu-central-1', 'sa-east-1',
                     'ap-northeast-1', 'ap-southeast-1', 'ap-southeast-2')
AVAILABLE_REGIONS_MESSAGE = """\
    Invalid region. Available regions for Amazon Glacier are:
    us-east-1 (US - Virginia)
    us-west-1 (US - N. California)
    us-west-2 (US - Oregon)
    eu-west-1 (EU - Ireland)
    eu-central-1 (EU - Frankfurt)
    sa-east-1 (South America - Sao Paulo)
    ap-northeast-1 (Asia-Pacific - Tokyo)
    ap-southeast-1 (Asia Pacific (Singapore)
    ap-southeast-2 (Asia-Pacific - Sydney)\
    """


UPLOAD_DATA_ERROR_MSG = "Received data does not match uploaded data; please check your uploadid and try again."
