"""Offline generator tests; no network credentials or database access required."""

import unittest

from generate_supabase_contract import render, ts_type


class ContractTests(unittest.TestCase):
    def test_nullable_and_insert_defaults(self):
        text = render(
            {
                "tables": {
                    "sample": {
                        "required": ["id", "title"],
                        "properties": {
                            "id": {"type": "string", "default": "uuid()"},
                            "title": {"type": "string"},
                            "count": {"type": "integer"},
                        },
                    }
                }
            }
        )
        self.assertIn("count: number | null", text)
        self.assertIn('}, "title">', text)
        self.assertIn("Relationships: []", text)

    def test_types_and_unknown_types_fail_closed(self):
        self.assertEqual(ts_type({"format": "jsonb"}), "Json")
        self.assertEqual(
            ts_type({"type": "array", "items": {"type": "number"}}), "Array<number>"
        )
        self.assertEqual(
            ts_type({"enum": ["active", "archived"]}), '"active" | "archived"'
        )
        with self.assertRaises(ValueError):
            ts_type({"type": "invented"})


if __name__ == "__main__":
    unittest.main()
