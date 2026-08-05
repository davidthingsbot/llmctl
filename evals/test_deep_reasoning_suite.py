#!/usr/bin/env python3
import importlib.util
import itertools
import json
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).with_name("deep_reasoning_suite.py")
spec = importlib.util.spec_from_file_location("deep_reasoning_suite", MODULE_PATH)
if spec is None or spec.loader is None:
    raise RuntimeError(f"cannot load {MODULE_PATH}")
suite = importlib.util.module_from_spec(spec)
spec.loader.exec_module(suite)


class DeepReasoningSuiteTests(unittest.TestCase):
    def test_weights_total_one_hundred(self):
        self.assertEqual(sum(grader("")[1] for _, _, _, grader in suite.tasks()), 100)

    def test_logic_grid_has_unique_solution(self):
        people = ["Ada", "Ben", "Cara", "Dion"]
        topics = ["Logic", "Biology", "History", "Economics"]
        solutions = []
        for days_tuple in itertools.permutations(range(1, 5)):
            days = dict(zip(people, days_tuple))
            for topics_tuple in itertools.permutations(topics):
                assigned = dict(zip(people, topics_tuple))
                topic_day = {assigned[p]: days[p] for p in people}
                if (
                    assigned["Dion"] == "Logic"
                    and days["Ada"] == topic_day["Economics"] + 1
                    and days["Ben"] < days["Cara"]
                    and topic_day["History"] == 1
                    and assigned["Cara"] != "Biology"
                    and topic_day["Logic"] == days["Ben"] + 1
                ):
                    solutions.append((days, assigned))
        self.assertEqual(len(solutions), 1)
        self.assertEqual(
            solutions[0],
            (
                {"Ada": 4, "Ben": 1, "Cara": 3, "Dion": 2},
                {"Ada": "Biology", "Ben": "History", "Cara": "Economics", "Dion": "Logic"},
            ),
        )

    def test_value_of_information_reference_scores_full(self):
        response = json.dumps(
            {
                "launch_now_ev": 12,
                "positive_probability": 0.44,
                "good_given_positive": 0.7272727,
                "launch_ev_given_positive": 70.9091,
                "launch_ev_given_negative": -34.2857,
                "test_policy_ev_after_cost": 21.2,
                "positive_action": "launch",
                "negative_action": "decline",
                "best_initial_policy": "buy test",
            }
        )
        score, maximum, details = suite.task_value_of_information()[3](response)
        self.assertEqual((score, maximum), (12, 12), details)

    def test_wason_recovers_explicit_cards_from_truncated_json(self):
        response = '''{"turn_cards":["A","7"],"reason":"Turn A because an odd reverse would falsify the rule. Turn 7 because a vowel reverse would violate it. D is a consonant and irrelevant. The explanation for 4 is'''
        score, maximum, details = suite.task_wason_selection()[3](response)
        self.assertEqual(maximum, 10)
        self.assertTrue(details["exact_cards"])
        self.assertGreaterEqual(score, 8)

    def test_epistemology_ignores_markdown_emphasis(self):
        response = (
            "S2 depends on S1 and S4 is derivative, not independent. The rival has motive and bias. "
            "S3 reduces belief, but S3 does *not* prove innocence. The cousin and matched price are weak, "
            "limited evidence. Seek bank receipts and supplier correspondence."
        )
        score, maximum, details = suite.task_adversarial_epistemology()[3](response)
        self.assertEqual(maximum, 14)
        self.assertTrue(details["ledger_not_complete_exoneration"])


if __name__ == "__main__":
    unittest.main()
