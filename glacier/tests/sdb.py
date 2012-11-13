import unittest
import wraptools

import ConfigParser
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from GlacierWrapper import GlacierWrapper

from  boto.glacier.layer1 import Layer1 as Layer1
from boto.glacier.exceptions import UnexpectedHTTPResponseError

import localsettings


class FakeBotoGlacier:
    @staticmethod
    def initiate_job(self, glacierconn, vault_name, job_id):
        out = {u'Location': '/123456789101/vaults/{0}/jobs/fake_hash'
               .format(vault_name),
               u'RequestId': 'fake_request',
               u'JobId': "abcd" * 23}
        return out

    @staticmethod
    def describe_job(self, glacierconn, vault_name, job_id):
        return {u'CompletionDate': None,
                u'VaultARN': u'arn:aws:glacier:us-east-1:'
                '123456789101:vaults/{0}'.format(vault_name),
                u'CreationDate': u'2012-11-13T21:24:27.496Z',
                u'SHA256TreeHash': None,
                u'Completed': False,
                u'InventorySizeInBytes': None,
                u'SNSTopic': None,
                u'Action': u'InventoryRetrieval',
                u'JobDescription': None,
                u'RequestId': 'fake_request_id',
                u'ArchiveSizeInBytes': None,
                u'ArchiveId': None,
                u'JobId': '',
                u'StatusMessage': None,
                u'StatusCode': u'InProgress'}

    @staticmethod
    def get_job_output(vault_name, job_id, byte_range=None):
        print "Calling logging job output "
        return {u'TreeHash': None,
                u'VaultARN': u'arn:aws:glacier:us-east-1:'
                '123456789101:vaults/{0}',
                u'ContentType': 'application/json',
                u'RequestId': 'fake_request_id',
                u'ContentRange': None,
                u'InventoryDate':
                u'2012-10-14T20:24:52Z',
                u'ArchiveList': [
                    {u'ArchiveId': "a" * 138,
                     u'ArchiveDescription': u'foobarramsteak.txt',
                     u'CreationDate': u'2012-10-14T01:51:26Z',
                     u'SHA256TreeHash': u'25623b53e0984428da972f4c635706d32d01'
                     'ec92dcd2ab39066082e0b9488c9d',
                     u'Size': 12}
                ]}


class TestGlacierSDB(unittest.TestCase):
    def setUp(self):
        config = ConfigParser.SafeConfigParser()
        config.read(['/etc/glacier-cmd.conf',
                    os.path.expanduser('~/.glacier-cmd')])

        secs = config.sections()
        for sec in secs:
            if sec != "aws":
                config.remove_section(sec)

        prepand_options = lambda section: [(section + "_" + k, v)
                                           for k, v in config.items(section)]
        self.args = dict(prepand_options("aws"))
        self.args.update({"region": "us-east-1"})

        self.test_file = "test_file.txt"
        test_file_obj = open(self.test_file, "w")
        test_file_obj.write("Lorem Ipsum.")
        test_file_obj.close()

    def tearDown(self):
        os.remove(self.test_file)


class TestSDBUploadArchive(TestGlacierSDB):
    def test_upload(self):
        self.args.update({"bookkeeping": True})
        self.gw = GlacierWrapper(**self.args)


class TestSDBInventoryBuild(TestGlacierSDB):
    def test_inventory(self):
        self.args.update({
            "bookkeeping": True,
            "bookkeeping_domain_name": "test_amazon-glacier"
        })
        self.gw = GlacierWrapper(**self.args)

        wraptools.wrap_method(Layer1.initiate_job,
                              FakeBotoGlacier.initiate_job)
        wraptools.wrap_method(Layer1.describe_job,
                              FakeBotoGlacier.describe_job)
        wraptools.wrap_method(Layer1.get_job_output,
                              FakeBotoGlacier.get_job_output)

        print self.gw.inventory("tralala", "hopsasa")
