import unittest
import test_app as base
import app as a
from shopify_clients import incorporate_review_pending
class ReviewPendingDebtTests(unittest.TestCase):
    def setUp(self):
        base.FinanceTests.setUp(self)
        self.records=[{'shopify_id':'gid/review/new','number':'#review-new','client_id':self.cid,'fingerprint':'current','financial_status':'PENDING','total':75000,'outstanding':75000,'purchased':'2026-10-28','items':[{'title':'Producto prueba','quantity':1}]}]
        self.reviews=[{'shopify_id':'gid/review/new','kind':'new','fingerprint':'current','status':'pending'}]
    def test_add_pending_to_existing_client_once(self):
        with a.db(True) as c:
            self.assertEqual(incorporate_review_pending(c,self.records,self.reviews,a.amount,a.now()),1)
            oid=c.execute('SELECT id FROM orders WHERE shopify_id=?',('gid/review/new',)).fetchone()[0]
            self.assertEqual(a.balance(c,oid),75000)
            self.assertEqual(a.balance(c,self.oid),100001)
            self.assertEqual(self.reviews[0]['status'],'reviewed')
            a.pay(c,{'order_id':oid,'amount':10000,'operation':'review-pending-payment-001','date':'2026-10-29'})
            self.assertEqual(incorporate_review_pending(c,self.records,self.reviews,a.amount,a.now()),0)
            self.assertEqual(a.balance(c,oid),65000)
    def test_paid_conflicting_and_stale_do_not_add_debt(self):
        with a.db(True) as c:
            for field,value in [('financial_status','PAID'),('client_id',None)]:
                old=self.records[0][field];self.records[0][field]=value
                self.assertEqual(incorporate_review_pending(c,self.records,self.reviews,a.amount,a.now()),0)
                self.records[0][field]=old
            self.reviews[0]['fingerprint']='stale'
            self.assertEqual(incorporate_review_pending(c,self.records,self.reviews,a.amount,a.now()),0)
            self.reviews[0]['fingerprint']='current';self.reviews[0]['kind']='difference'
            self.assertEqual(incorporate_review_pending(c,self.records,self.reviews,a.amount,a.now()),0)
    def test_existing_number_never_adds_again(self):
        with a.db(True) as c:
            c.execute('UPDATE orders SET number=? WHERE id=?',('#review-new',self.oid))
            self.assertEqual(incorporate_review_pending(c,self.records,self.reviews,a.amount,a.now()),0)
