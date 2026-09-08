"""Publication boundary checks use invented identities only."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from check_publication import privacy_issues


class PrivacyBoundary(unittest.TestCase):
    def test_email_contacts_and_account_identifiers_are_rejected(self):
        for domain in ('gmail.com', 'users.noreply.github.com'):
            with self.subTest(domain=domain):
                self.assertIn('personal or operational email address',
                              privacy_issues('invented-person@' + domain))

    def test_only_generic_device_labels_are_allowed(self):
        self.assertEqual([], privacy_issues('KVM02 KVM03 TR2 kvm-connected kvm-lab SOURCE-B'))
        for suffix in ('kvm02', 'rack03'):
            self.assertIn('prefixed internal device name',
                          privacy_issues('inventedsite' + suffix))

    def test_synthetic_attribution_and_documentation_examples_are_allowed(self):
        self.assertEqual([], privacy_issues(
            'contributors@cometx.invalid example@example.com user@lab.test'))


if __name__ == '__main__':
    unittest.main()
