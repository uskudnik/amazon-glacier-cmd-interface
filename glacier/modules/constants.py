

# from http://docs.aws.amazon.com/general/latest/gr/rande.html#glacier_region

AVAILABLE_REGIONS=[
                   "us-east-1",
                   "us-east-2",
                   "us-west-1",
                   "us-west-2",
                   "ca-central-1",
                   "ap-south-1",
                   "ap-northeast-2",
                   "ap-southeast-2",
                   "ap-northeast-1",
                   "eu-central-1",
                   "eu-west-1",
                   "eu-west-2"
                  ]

AVAILABLE_REGIONS_MESSAGE = """\
Invalid region. Available regions for Amazon Glacier are:
us-east-1 (US - Virginia)
us-west-1 (US - N. California)
us-west-2 (US - Oregon)
eu-west-1 (EU - Ireland)
eu-central-1 (EU - Frankfurt)
ap-northeast-1 (Asia-Pacific - Tokyo)
ap-southeast-1 (Asia Pacific (Singapore)
ap-southeast-2 (Asia-Pacific - Sydney)\
"""

VAULT_NAME_ALLOWED_CHARACTERS = "[a-zA-Z\.\-\_0-9]+"
ID_ALLOWED_CHARACTERS = "[a-zA-Z\-\_0-9]+"
MAX_VAULT_NAME_LENGTH = 255
MAX_VAULT_DESCRIPTION_LENGTH = 1024
MAX_PARTS = 10000
