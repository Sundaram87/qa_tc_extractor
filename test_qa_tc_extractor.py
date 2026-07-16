import unittest

from qa_tc_extractor import analyze


class AnalyzeTests(unittest.TestCase):
    def test_returns_stable_impacted_level0_proposal(self):
        payload = {
            "change_requests": [
                {
                    "id": "CR-101",
                    "title": "Checkout payment tax fix",
                    "component": "checkout",
                    "description": "Fix tax total in payment review",
                    "release_notes": "Checkout and payment totals updated",
                }
            ],
            "release_evidence": [
                {
                    "source_type": "emails",
                    "title": "Release note confirms checkout tax fix",
                    "content": "CR-101 updates checkout payment total behavior.",
                },
                {
                    "source_type": "teams",
                    "title": "Teams discussion on payment validation",
                    "content": "Checkout payment regression needs Level 0 validation.",
                },
            ],
            "level0_test_cases": [
                {
                    "id": "L0-200",
                    "title": "User can complete checkout payment review",
                    "level": "L0",
                    "area": "checkout",
                    "keywords": ["payment", "tax"],
                },
                {
                    "id": "L0-100",
                    "title": "Guest can browse catalog",
                    "level": "level_0",
                    "area": "catalog",
                    "keywords": ["browse"],
                },
                {
                    "id": "L1-300",
                    "title": "Admin audit report export",
                    "level": "L1",
                    "area": "reporting",
                    "keywords": ["export"],
                },
            ],
        }

        result = analyze(payload)

        self.assertEqual(result["search_scope"], ["files", "emails", "meetings", "teams"])
        self.assertEqual(result["email_handoff"]["subject"], "QA Level 0 regression proposal")
        impacted = result["impacted_change_requests"][0]
        self.assertEqual(impacted["change_request"]["id"], "CR-101")
        self.assertEqual(impacted["impacted_level0_tests"][0]["test_id"], "L0-200")
        self.assertEqual(impacted["impacted_level0_tests"][0]["coverage_fit"], "strong")
        self.assertEqual(impacted["impacted_level0_tests"][0]["confidence"], "high")
        self.assertNotIn("L1-300", str(result))

    def test_separates_confirmed_facts_from_hypotheses_and_gaps(self):
        payload = {
            "change_requests": [
                {
                    "id": "CR-202",
                    "title": "Profile avatar refresh",
                    "component": "profile",
                    "description": "Avatar CDN refresh tweak",
                }
            ],
            "release_evidence": [],
            "level0_test_cases": [
                {
                    "id": "L0-401",
                    "title": "User can update profile avatar",
                    "level": "0",
                    "area": "profile",
                    "keywords": ["avatar"],
                }
            ],
        }

        result = analyze(payload)

        self.assertEqual(result["confirmed_facts"], [])
        self.assertTrue(any("lacks explicit supporting evidence" in item for item in result["hypotheses"]))
        self.assertTrue(any("No release evidence was provided." == item for item in result["overall_evidence_gaps"]))
        self.assertIn("manual QA triage required", result["qa_sign_off_proposal"][0])


if __name__ == "__main__":
    unittest.main()
