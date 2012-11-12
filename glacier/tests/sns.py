import unittest

import ConfigParser
import os
import sys

sys.path.append("/".join(sys.path[0].split("/")[:-1]))

from GlacierWrapper import GlacierWrapper

from boto.glacier.exceptions import UnexpectedHTTPResponseError

import localsettings

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
        self.args = dict(prepand_options("aws"))
        self.args.update({"region": "us-east-1"})

    def tearDown(self):
        for vault in self.gw.lsvault():
            if \
                vault[u'VaultARN'].split("vaults/")[-1]\
                    .startswith("test_vvault"):
                self.gw.rmvault(vault[u'VaultARN'].split("vaults/")[-1])

        topics = self.gw.sns_conn.get_all_topics()\
['ListTopicsResponse']\
['ListTopicsResult']\
['Topics']

        for topic in topics:
            if topic['TopicArn'].split(":")[-1].startswith("test_topic"):
                self.gw.sns_conn.delete_topic(topic['TopicArn'])


class TestGlacierSNSAuto(TestGlacierSNS):
    def test_sync_auto_basic(self):
        """
        No configuration
        """
        sns_options = {'topic': 'aws-glacier-notifications',
                       'topics_present': False}

        self.gw = GlacierWrapper(**self.args)

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


class TestGlacierSNSMultiConfig(TestGlacierSNS):
    def test_withOUT_method(self):
        """
        Configuration

        [SNS:test_topic_1]

        [SNS:test_topic_2]
        vaults=test_vvault0,test_vvault2

        {'topics': [
        """
        vaults = ['test_vvault0', 'test_vvault1', 'test_vvault2']
        vaults_used = [vaults[0], vaults[2]]

        sns_options = {'topics': [
            {'topic': 'test_topic_1', 'options':{}},
            {'topic': 'test_topic_2', 'options':
                {'vaults': ','.join(vaults_used)}}
        ],
            'topics_present': True}

        self.gw = GlacierWrapper(**self.args)

        for vault in vaults:
            self.gw.mkvault(vault)

        response = self.gw.sns_sync(sns_options=sns_options, output="csv")

        for obj in response:
            del obj['Request Id']

        # Testing topic 1 - no vaults passed in,
        # should be subscribed to all vaults (our testing vaults and some more)
        for vault in vaults:
            self.assertIn(
                dict([('Topic', 'test_topic_1'),
                    ('Subscribe Result', u''),
                    ('Vault Name', vault)]),
                response)

        # Testing topic 2
        # should be subscribed only to test_vvault0, test_vvault2
        for vault in vaults_used:
            self.assertIn(
                dict([('Topic', 'test_topic_2'),
                    ('Subscribe Result', u''),
                    ('Vault Name', vault)]),
                response)

        for vault in vaults:
            self.gw.rmvault(vault)

    def test_with_method(self):
        """
        Configuration

        [SNS:test_topic_1]
        method=email,email.1@example.com;

        [SNS:test_topic_2]
        vaults=test_vvault0,test_vvault2
        method=email,email.1@example.com;email,email.2@example.com
        """
        vaults = ['test_vvault0', 'test_vvault1', 'test_vvault2']
        vaults_used = [vaults[0], vaults[2]]

        sns_options = {'topics': [
            {'topic': 'test_topic_1', 'options':
                {'method': '%s,%s;' % (
                    localsettings.protocol_1,
                    localsettings.endpoint_1
                )}},
            {'topic': 'test_topic_2', 'options':
                {'vaults': 'test_vvault0,test_vvault2',
                 'method': ('%s,%s;'
                            '%s,%s') % (
                                localsettings.protocol_1,
                                localsettings.endpoint_1,
                                localsettings.protocol_2,
                                localsettings.endpoint_2)}}
        ],
            'topics_present': True}

        self.gw = GlacierWrapper(**self.args)

        for vault in vaults:
            self.gw.mkvault(vault)

        response = self.gw.sns_sync(sns_options=sns_options, output="csv")

        for obj in response:
            del obj['Request Id']

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


class TestGlacierSNSManualSubscribe(TestGlacierSNS):
    def test_subscribe_to_existing_topic(self):
        """
        $ glacier-cmd subscribe email endpoint_1 test_topic_1
        """
        self.gw = GlacierWrapper(**self.args)

        topic = 'test_topic_existing_kind_off'

        # sns_subscribe actually creates a topic to "get it"
        response = self.gw.sns_subscribe(protocol="email",
                                         endpoint=localsettings.endpoint_1,
                                         topic=topic,
                                         sns_options={})

        for res in response:
            del res["RequestId"]

        self.assertIn(
            {'SubscribeResult': u'pending confirmation'},
            response)

        all_topics = self.gw.sns_conn.get_all_topics()\
['ListTopicsResponse']\
['ListTopicsResult']\
['Topics']
        topics = [t['TopicArn'].split(":")[-1] for t in all_topics]
        self.assertIn(topic, topics)

    def test_subscribe_create_topic_for_vaults(self):
        """
        $ glacier-cmd
            subscribe email endpoint_1 test_topic --vault test_vvault0,test_vvault
        """
        self.gw = GlacierWrapper(**self.args)

        vaults = ['test_vvault0', 'test_vvault1', 'test_vvault2']
        vaults_used = [vaults[0], vaults[2]]

        topic = 'test_topic_new_for_vaults'

        for vault in vaults:
            self.gw.mkvault(vault)

        response = self.gw.sns_subscribe(protocol="email",
                                         endpoint=localsettings.endpoint_1,
                                         topic=topic,
                                         vault_names=",".join(vaults_used),
                                         sns_options={})
        for res in response:
            del res["RequestId"]

        self.assertIn(
            {'SubscribeResult': u'pending confirmation'},
            response)

        # Lets check that the topic was created
        all_topics = self.gw.sns_conn.get_all_topics()\
['ListTopicsResponse']\
['ListTopicsResult']\
['Topics']

        topics = [t['TopicArn'].split(":")[-1] for t in all_topics]
        self.assertIn(topic, topics)

        for vault in vaults_used:
            notifications = self.gw.glacierconn.get_vault_notifications(vault)
            self.assertIn("ArchiveRetrievalCompleted",
                          notifications['Events'])
            self.assertIn("InventoryRetrievalCompleted",
                          notifications['Events'])
            self.assertEqual(topic,
                             notifications['SNSTopic'].split(":")[-1])

if __name__ == '__main__':
    # Use python -m unittest tests_sns.<test case> to run individual test cases
    # e. g. python -m unittest tests_sns.TestGlacierSNSManualSubscribe
    unittest.main()
