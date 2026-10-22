import unittest
from scripts.product_text import GB, RAM, STORAGE, condition_hint, query_terms, storage_values, tokens


class ProductTextTests(unittest.TestCase):
    def test_source_language_storage_and_ram(self):
        title = f"A55 {STORAGE} 256 {RAM} 8 {GB}"
        self.assertEqual(storage_values(title), {256})
        self.assertIn("gb", tokens(title))

    def test_ram_and_camera_are_not_storage(self):
        self.assertEqual(storage_values("A55 RAM 256GB camera 256MP"), set())
        self.assertEqual(storage_values("A55 256MP"), set())

    def test_tb_and_ambiguous_capacity(self):
        self.assertEqual(storage_values("Phone 1TB"), {1024})
        self.assertEqual(storage_values("Phone 128GB or 256GB"), {128,256})

    def test_model_numbers_survive_query_processing(self):
        self.assertEqual(query_terms("iPhone 14 256GB"), {"iphone","14"})
        self.assertEqual(query_terms("S24 1TB"), {"s24"})

    def test_absence_of_used_is_unknown(self):
        self.assertEqual(condition_hint("A55"), "unknown")
        self.assertEqual(condition_hint("A55 used"), "used_or_refurbished_mentioned")
