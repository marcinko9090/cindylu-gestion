import unittest
from statements import payment_display_history

class PaymentDisplayTests(unittest.TestCase):
    def test_cutoff_inclusive_and_unknown_dates_preserved(self):
        history=[{'date':'2026-09-30','amount':1},{'date':'2026-10-01','amount':2},{'date':'2026-10-02','amount':3},{'date':'','amount':4}]
        result=payment_display_history(history,[{'purchased':'2026-10-01'}])
        self.assertEqual([p['amount'] for p in result],[2,3,4])
        self.assertEqual(len(history),4)
    def test_no_dated_purchases_keeps_history(self):
        history=[{'date':'2025-01-01','amount':1}]
        self.assertEqual(payment_display_history(history,[]),history)
    def test_chile_date_and_oldest_purchase(self):
        history=[{'date':'2025-12-30','amount':1},{'date':'2025-12-31','amount':2}]
        self.assertEqual(payment_display_history(history,[{'purchased':'2026-02-01'},{'purchased':'2026-01-01T01:00:00Z'}]),[history[1]])
