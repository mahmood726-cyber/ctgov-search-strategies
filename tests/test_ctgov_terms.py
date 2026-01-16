import json
import os
import tempfile
import unittest

from ctgov_terms import load_synonyms, normalize_condition


class CtgovTermsTests(unittest.TestCase):
    def test_normalize_condition(self):
        self.assertEqual(normalize_condition("Cerebrovascular Accident"), "stroke")
        self.assertEqual(normalize_condition("Type 2 diabetes mellitus"), "diabetes")
        self.assertEqual(normalize_condition("Breast carcinoma"), "breast cancer")
        self.assertEqual(normalize_condition("Autism spectrum disorder"), "autism")
        self.assertEqual(normalize_condition("Plaque psoriasis"), "psoriasis")

    def test_load_synonyms_fallback(self):
        synonyms = load_synonyms("this_file_should_not_exist.json")
        self.assertIn("diabetes", synonyms)

    def test_load_synonyms_custom_file(self):
        payload = {"rare": ["term one", "term two"]}
        fd, path = tempfile.mkstemp(suffix=".json")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(payload, handle)
            synonyms = load_synonyms(path)
            self.assertIn("rare", synonyms)
            self.assertIn("diabetes", synonyms)
        finally:
            os.remove(path)


if __name__ == "__main__":
    unittest.main()
