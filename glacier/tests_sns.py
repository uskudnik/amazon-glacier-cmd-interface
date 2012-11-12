import unittest

import ConfigParser
import argparse
import os
import sys
import inspect

from GlacierWrapper import GlacierWrapper
import glacier

from boto.glacier.exceptions import UnexpectedHTTPResponseError

import localsettings_tests


class TestGlacierSNS(unittest.TestCase):
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
        self.aws = dict(prepand_options("aws"))

    def tearDown(self):
        vaults = [vault[u'VaultARN'].split("vaults/")[-1]
                  for vault in self.gw.lsvault()
                  if vault[u'VaultARN'].split("vaults/")[-1]
                  .startswith("test_vvault")]
        if vault in vaults:
            self.gw.rmvault(vault)

    def test_snssync_auto_basic(self):
        """
        Configuration:
        [SNS]
        """
        args = self.aws.copy()

        args.update({"region": "us-east-1"})

        sns_options = {'topic': 'aws-glacier-notifications',
                       'topics_present': False}

        self.gw = GlacierWrapper(**args)

        vault_name = "test_vvault0"

        # Lets create one vault for our testing purposes
        self.gw.mkvault(vault_name)

        # Only after a call to one of gw functions was executed
        # is glacierconn available
        gc = vars(self.gw)['glacierconn']

        # No vault notifications set for fresh vault
        with self.assertRaises(UnexpectedHTTPResponseError) as cm:
            gc.get_vault_notifications(vault_name)
        self.assertEqual(cm.exception.status, 404)
        self.assertEqual(cm.exception.message,
                         ("Expected 200, got (404, "
                         "code=ResourceNotFoundException, "
                         "message=No notification configuration "
                         "is set for vault: %s)") % (vault_name,))

        # Set all vaults
        response = self.gw.sns_sync(sns_options=sns_options, output="csv")
        successful_vaults = [r["Vault Name"] for r in response]
        self.assertIn(vault_name, successful_vaults)

        # Check out vault has set notifications
        vaults = [vault[u'VaultARN'].split("vaults/")[-1]
                  for vault in self.gw.lsvault()]
        for vault in vaults:
            response = gc.get_vault_notifications(vault)
            events = response['Events']
            self.assertIn(u"ArchiveRetrievalCompleted", events)
            self.assertIn(u"InventoryRetrievalCompleted", events)

        # Remove test vault
        self.gw.rmvault(vault_name)

    def test_sns_sync_multiconf(self):
        """
        Configuration

        [SNS:test_topic_1]
        method=email,email.1@example.com;

        [SNS:test_topic_2]
        vaults=test_vvault0,test_vvault2
        method=email,email.1@example.com;email,email.2@example.com
        """
        args = self.aws.copy()
        args.update({"region": "us-east-1"})

        vaults = ['test_vvault0', 'test_vvault1', 'test_vvault2']
        vaults_used = [vaults[0], vaults[2]]

        sns_options = {'topics': [
            {'topic': 'test_topic_1', 'options':
                {'method': 'email,%s;' % localsettings_tests.email_1}},
            {'topic': 'test_topic_2', 'options':
                {'vaults': 'test_vvault0,test_vvault2',
                 'method': ('email,%s;'
                            'email,%s') % (localsettings_tests.email_1,
                                           localsettings_tests.email_2)}}
        ],
            'topics_present': True}

        self.gw = GlacierWrapper(**args)

        for vault in vaults:
            self.gw.mkvault(vault)

        response = self.gw.sns_sync(sns_options=sns_options, output="csv")

        for obj in response:
            del obj['Request Id']
            print obj

        # Testing topic 1 - no vaults passed in,
        # should be subscribed to all vaults (our testing vaults and some more)
        for vault in vaults:
            self.assertIn(
                dict([('Topic', 'test_topic_1'),
                    ('Subscribe Result', u'pending confirmation'),
                    ('Vault Name', vault)]),
                response)

        # Testing topic 2
        # should be subscribed only to test_vvault0, test_vvault2
        for vault in vaults_used:
            self.assertIn(
                dict([('Topic', 'test_topic_2'),
                    ('Subscribe Result', u'pending confirmation'),
                    ('Vault Name', vault)]),
                response)

        for vault in vaults:
            self.gw.rmvault(vault)


if __name__ == '__main__':
    args = sys.argv[1:]

    if len(args):
        test_cases = TestGlacierSNS.__dict__.copy()

        ts = unittest.TestSuite()
        ts.addTest(test_cases["setUp"])

        for arg in args:
            if test_cases.get(arg, False):
                ts.addTest(TestGlacierSNS.__dict__[arg])
        ts.addTest(test_cases["tearDown"])
        unittest.TextTestRunner().run(ts)
    else:
        unittest.main()
