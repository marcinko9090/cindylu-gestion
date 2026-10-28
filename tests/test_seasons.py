import datetime as dt
import unittest
from seasons import events,season_for

class SeasonTests(unittest.TestCase):
    def test_halloween_already_active_in_chile(self):
        s=season_for(dt.date(2026,10,27))
        self.assertEqual(s['key'],'halloween');self.assertEqual(s['days'],4)
        self.assertEqual(s['countdown'],'4 días para Halloween')
    def test_all_event_windows_include_exactly_ten_days_before(self):
        for year in (2026,2027,2028,2029,2030):
            for key,_,day,_ in events(year):
                with self.subTest(year=year,key=key):
                    before=season_for(day-dt.timedelta(days=11))
                    start=season_for(day-dt.timedelta(days=10))
                    self.assertNotEqual(before['key'],key)
                    self.assertEqual(start['key'],key);self.assertEqual(start['days'],10)
                    self.assertEqual(season_for(day)['key'],key)
                    self.assertFalse(season_for(day+dt.timedelta(days=1))['active'])
    def test_joint_birthday_starts_january_29(self):
        s=season_for(dt.date(2027,1,29))
        self.assertEqual(s['key'],'birthday');self.assertEqual(s['event_date'],'2027-02-08')
        self.assertIn('Cindy y Florencia',s['label']);self.assertEqual(s['days'],10)
    def test_mothers_day_is_second_sunday_of_may(self):
        for year,expected in [(2026,'2026-05-10'),(2027,'2027-05-09'),(2028,'2028-05-14')]:
            item=next(e for e in events(year) if e[0]=='mother')
            self.assertEqual(item[2].isoformat(),expected);self.assertEqual(item[2].weekday(),6)
    def test_singular_and_event_day_countdown(self):
        self.assertEqual(season_for(dt.date(2026,10,30))['countdown'],'1 día para Halloween')
        self.assertEqual(season_for(dt.date(2026,10,31))['countdown'],'Hoy · Halloween')
    def test_rollover_and_annual_variation(self):
        self.assertEqual(season_for(dt.date(2026,12,31))['event_date'],'2027-02-08')
        a=season_for(dt.date(2026,10,27));b=season_for(dt.date(2027,10,27))
        self.assertNotEqual(a['seed'],b['seed']);self.assertNotEqual(a['variant'],b['variant'])
        self.assertEqual(a,season_for(dt.date(2026,10,27)))
    def test_timezone_is_continental_chile(self):
        self.assertEqual(season_for()['timezone'],'America/Santiago')
