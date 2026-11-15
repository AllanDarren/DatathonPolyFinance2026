"""Offline tests of rejection paths in the post-merge audit, without an API."""
import copy
import unittest

from verify_after_merge import inspect_explanation, near, audit_api


class AcceptanceAuditTests(unittest.TestCase):
    def setUp(self):
        self.explanation = {'guardian': {'status': 'passed', 'flags': []}, 'claims': [{'text': 'Une valeur sourcée.', 'label': 'fact', 'verified': 'supported', 'evidence_ids': ['ev_1']}]}

    def test_missing_evidence_rejected(self):
        with self.assertRaisesRegex(ValueError, 'inexistante'):
            inspect_explanation(self.explanation, {})

    def test_supported_without_evidence_rejected(self):
        value = copy.deepcopy(self.explanation)
        value['claims'][0]['evidence_ids'] = []
        with self.assertRaisesRegex(ValueError, 'sans preuve'):
            inspect_explanation(value, {})

    def test_guardian_must_not_pass_unsupported_claim(self):
        value = copy.deepcopy(self.explanation)
        value['claims'][0]['verified'] = 'unsupported'
        with self.assertRaisesRegex(ValueError, 'passed'):
            inspect_explanation(value, {'ev_1': {}})

    def test_unrendered_placeholder_rejected(self):
        value = copy.deepcopy(self.explanation)
        value['claims'][0]['text'] = '{{ev_1}}'
        with self.assertRaisesRegex(ValueError, 'non rendu'):
            inspect_explanation(value, {'ev_1': {}})

    def test_invalid_numeric_values_rejected(self):
        for value in [True, float('nan'), float('inf'), None, '0.20']:
            with self.subTest(value=value), self.assertRaises(ValueError):
                near(value, .20)

    def test_valid_trace_allowed(self):
        inspect_explanation(self.explanation, {'ev_1': {}})

    def test_unavailable_api_never_creates_success(self):
        def offline(*args):
            raise ValueError('API indisponible pour ce test.')
        report = audit_api(offline, 'CAD')
        self.assertFalse(report['passed'])
        self.assertTrue(all(r['status'] == 'failed' for r in report['checks']))
        self.assertEqual(len(report['checks']), 10)


if __name__ == '__main__':
    unittest.main()
