import unittest

import ConfigParser
import argparse
import os
import inspect

from GlacierWrapper import GlacierWrapper
import glacier

from boto.glacier.exceptions import UnexpectedHTTPResponseError


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

        self.test_vault_name = "test_vaultek"

    def tearDown(self):
        vaults = [vault[u'VaultARN'].split("vaults/")[-1]
                  for vault in self.gw.lsvault()]
        if self.test_vault_name in vaults:
            self.gw.rmvault(self.test_vault_name)

    def test_snssync_auto_basic(self):
        """
        Configuration:
        [SNS]
        """
        args = self.aws.copy()

        args.update({"sns_enable": True, "region": "us-east-1"})

        self.gw = GlacierWrapper(**args)

        # Lets create one vault for our testing purposes
        self.gw.mkvault(self.test_vault_name)

        # Only after a call to one of gw functions was executed
        # is glacierconn available
        gc = vars(self.gw)['glacierconn']

        # No vault notifications set for fresh vault
        with self.assertRaises(UnexpectedHTTPResponseError) as cm:
            gc.get_vault_notifications(self.test_vault_name)
        self.assertEqual(cm.exception.status, 404)
        self.assertEqual(cm.exception.message,
                         ("Expected 200, got (404, "
                         "code=ResourceNotFoundException, "
                         "message=No notification configuration "
                         "is set for vault: %s)") % (self.test_vault_name,))

        # Set all vaults
        response = self.gw.sns_sync()
        successful_vaults = [r["Vault Name"] for r in response]
        self.assertIn(self.test_vault_name, successful_vaults)

        # Check out vault has set notifications
        vaults = [vault[u'VaultARN'].split("vaults/")[-1]
                  for vault in self.gw.lsvault()]
        for vault in vaults:
            response = gc.get_vault_notifications(vault)
            events = response['Events']
            self.assertIn(u"ArchiveRetrievalCompleted", events)
            self.assertIn(u"InventoryRetrievalCompleted", events)

        # Remove test vault
        self.gw.rmvault(self.test_vault_name)

    def trolo_test_snssync_multiconf(self):
        """
        Configuration
        [SNS]
        domain_prefix=aws-glacier-sns-notifications

        [SNS:neki1]
        vaults=vvt,vv1
        method=email,urban.skudnik@gmail.com

        [SNS:neki2]
        vaults=trololo
        method=http,example.com;email,urban.skudnik@gmail.com
        """
        args = self.aws.copy()

        args.update({"sns_enable": True, "region": "us-east-1"})

        self.gw = GlacierWrapper(**args)

        # Lets create one vault for our testing purposes
        self.gw.mkvault(self.test_vault_name)


if __name__ == '__main__':
    unittest.main()
