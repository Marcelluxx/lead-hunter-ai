import unittest
from decimal import Decimal

from src.domain.identity import Permission, Role, role_allows
from src.domain.jobs import InvalidJobTransition, JobState, ensure_job_transition
from src.domain.usage import InvalidCost, normalized_cost


class PlatformDomainTests(unittest.TestCase):
    def test_roles_have_minimum_expected_permissions(self):
        self.assertTrue(role_allows(Role.ADMIN, Permission.MANAGE_SECRETS))
        self.assertTrue(role_allows(Role.OPERATOR, Permission.START_JOB))
        self.assertFalse(role_allows(Role.OPERATOR, Permission.MANAGE_BUDGET))
        self.assertTrue(role_allows(Role.VIEWER, Permission.VIEW_RESULTS))
        self.assertFalse(role_allows(Role.VIEWER, Permission.EXPORT_RESULTS))

    def test_job_state_machine_rejects_terminal_or_skipped_transitions(self):
        ensure_job_transition(JobState.QUEUED, JobState.VALIDATING)
        ensure_job_transition(JobState.RUNNING, JobState.COMPLETED)

        with self.assertRaises(InvalidJobTransition):
            ensure_job_transition(JobState.QUEUED, JobState.COMPLETED)
        with self.assertRaises(InvalidJobTransition):
            ensure_job_transition(JobState.COMPLETED, JobState.RUNNING)

    def test_cost_is_nonnegative_and_fixed_precision(self):
        self.assertEqual(normalized_cost("1.2345674"), Decimal("1.234567"))
        with self.assertRaises(InvalidCost):
            normalized_cost("-0.1")


if __name__ == "__main__":
    unittest.main()
