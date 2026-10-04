import unittest
from cloud_budget import assess
class BudgetTests(unittest.TestCase):
 def test_shared_overage_and_missing_coverage(self):
  self.assertEqual(assess({"services":[{"service":"workers","month_to_date_usd":"5.00"},{"service":"storage","month_to_date_usd":"0.01"}]})["budget_status"],"over_budget")
  self.assertEqual(assess({"services":[{"service":"workers","month_to_date_usd":None}]})["budget_status"],"unknown")
 def test_even_complete_zero_extra_does_not_authorize_cloud(self):
  r=assess({"complete_account_coverage":True,"services":[{"service":"all","month_to_date_usd":"5.00"}]})
  self.assertEqual(r["budget_status"],"known_within_budget");self.assertEqual(r["optional_cloud_admission"],"deny")
 def test_invalid_counts_and_duplicates(self):
  for val in [True,-1,"NaN","Infinity"]:
   with self.assertRaises(ValueError): assess({"services":[{"service":"all","month_to_date_usd":val}]})
  with self.assertRaises(ValueError): assess({"services":[{"service":"a","month_to_date_usd":"1"},{"service":"a","month_to_date_usd":"1"}]})
