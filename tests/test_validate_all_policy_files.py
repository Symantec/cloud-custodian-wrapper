import argparse
import os
import sys
import unittest

from custodian_wrapper.utils import get_all_custodian_yaml_files
from c7n.commands import validate as cc_validate_yaml

sys.path.append(os.path.abspath('..'))


class ValidateAllPolicies(unittest.TestCase):

    def test_validate_all_policies(self):
        custodian_yaml_files = get_all_custodian_yaml_files('./policies/*')
        cc_validate_options = argparse.Namespace(
            command = 'c7n.commands.validate',
            config  = None,
            configs = custodian_yaml_files,
            debug=False,
            subparser='validate',
            verbose=False
        )
        self.assertEqual(cc_validate_yaml(cc_validate_options), None)

    def test_validate_bad_policy(self):
        custodian_yaml_files = get_all_custodian_yaml_files('./tests/*yml')
        cc_validate_options = argparse.Namespace(
            command = 'c7n.commands.validate',
            config  = None,
            configs = custodian_yaml_files,
            debug=False,
            subparser='validate',
            verbose=False
        )
        with self.assertRaises(SystemExit) as exit:
            cc_validate_yaml(cc_validate_options)
            self.assertEqual(exit.exception.code, 1)
