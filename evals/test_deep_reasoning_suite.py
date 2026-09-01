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



class ExtendedReasoningTest(unittest.TestCase):
    """Exactly-graded tasks: a correct answer scores full, the classic trap scores 0."""

    def test_kv_sizing_correct_answer_scores_full(self):
        _, _, _, grade = suite.task_kv_sizing()
        per = 12 * 8 * 128 * 2 * 1.0625
        gib = per * 262144 / (2 ** 30)
        answer = json.dumps({
            "kv_bytes_per_token": int(per),
            "kv_gib_at_262144": round(gib, 3),
            "max_context_tokens_in_25gib": int(25 * (2 ** 30) // per),
            "weights_87gib_and_262144_fits_in_112gib": (87 + gib) <= 112,
        })
        score, maximum, _ = grade(answer)
        self.assertEqual(score, maximum)

    def test_kv_sizing_flags_the_all_layers_trap(self):
        _, _, _, grade = suite.task_kv_sizing()
        per = 12 * 8 * 128 * 2 * 1.0625
        answer = json.dumps({"kv_bytes_per_token": int(per * 4),
                             "kv_gib_at_262144": 25.5,
                             "max_context_tokens_in_25gib": 257003,
                             "weights_87gib_and_262144_fits_in_112gib": False})
        score, _, details = grade(answer)
        self.assertEqual(score, 0)
        self.assertTrue(details["counted_all_48_layers"])

    def test_causal_identification_correct_answer_scores_full(self):
        _, _, _, grade = suite.task_causal_identification()
        answer = json.dumps({"adjustment_set": ["C"], "conditioning_on_M": "direct",
                             "z_is_collider": True, "conditioning_on_Z": "introduces_bias",
                             "i_is_instrument": True})
        score, maximum, _ = grade(answer)
        self.assertEqual(score, maximum)

    def test_causal_identification_penalises_adjusting_for_everything(self):
        _, _, _, grade = suite.task_causal_identification()
        answer = json.dumps({"adjustment_set": ["C", "M", "Z"], "conditioning_on_M": "total",
                             "z_is_collider": False, "conditioning_on_Z": "removes_bias",
                             "i_is_instrument": False})
        score, _, details = grade(answer)
        self.assertEqual(score, 0)
        self.assertTrue(details["included_mediator_or_collider"])

    def test_extended_tasks_are_opt_in(self):
        default = {t[0] for t in suite.tasks()}
        extended = {t[0] for t in suite.tasks(True)}
        self.assertNotIn("kv_sizing", default)
        self.assertIn("kv_sizing", extended)
        self.assertIn("causal_identification", extended)
        self.assertTrue(default < extended)



class DomainReasoningTest(unittest.TestCase):
    def test_optimization_correct_answer_scores_full(self):
        _, _, _, grade = suite.task_resource_optimization()
        answer = json.dumps({"selection": ["borealis", "cinder"], "total_value": 120,
                             "total_size_gib": 112,
                             "greedy_by_value_density_total": 114})
        score, maximum, _ = grade(answer)
        self.assertEqual(score, maximum)

    def test_optimization_greedy_is_strictly_suboptimal(self):
        # The item set is chosen so density-greedy scores 114 against 120; a task
        # where greedy happens to be optimal would not discriminate at all.
        _, _, _, grade = suite.task_resource_optimization()
        answer = json.dumps({"selection": ["atlas", "dunlin", "ember"],
                             "total_value": 114, "total_size_gib": 107,
                             "greedy_by_value_density_total": 114})
        score, maximum, details = grade(answer)
        self.assertLess(score, maximum)
        self.assertTrue(details["reported_greedy_as_optimal"])

    def test_physics_correct_answer_scores_full(self):
        _, _, _, grade = suite.task_thermal_physics()
        answer = json.dumps({"steady_state_junction_c": 89.2, "tau_seconds": 252.0,
                             "power_for_85c_limit_w": 225.0,
                             "junction_after_one_tau_c": 64.48})
        score, maximum, _ = grade(answer)
        self.assertEqual(score, maximum)

    def test_physics_flags_rise_reported_as_temperature(self):
        _, _, _, grade = suite.task_thermal_physics()
        answer = json.dumps({"steady_state_junction_c": 89.2, "tau_seconds": 252.0,
                             "power_for_85c_limit_w": 225.0,
                             "junction_after_one_tau_c": 42.48})
        score, maximum, details = grade(answer)
        self.assertLess(score, maximum)
        self.assertTrue(details["gave_rise_not_temperature"])


if __name__ == "__main__":
    unittest.main()
