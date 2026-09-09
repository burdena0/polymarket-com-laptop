from datetime import datetime,timezone
import json
from pathlib import Path
import tempfile
import unittest
from weather_laptop.core import Journal,DEFAULTS
from weather_laptop.independent import Independent
from weather_laptop.intraday_weather import day_bounds


class IndependentTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.j=Journal(Path(self.temp.name)/'paper.sqlite',dict(DEFAULTS,source_wallet='0x'+'c'*40))
        self.start,self.end=day_bounds('KNYC','2026-09-10')
        self.now=self.start-3600
        self.market={'slug':'test','question':'Highest temperature in NYC?',
            'description':'Will the highest temperature at KNYC for 2026-09-10 be less than 80F? National Weather Service Climatological Report.',
            'closed':False,'acceptingOrders':True,'conditionId':'0x'+'a'*64,
            'clobTokenIds':json.dumps(['123','124']),'outcomes':json.dumps(['Yes','No'])}
        iso=lambda t:datetime.fromtimestamp(t,timezone.utc).isoformat()
        self.forecast={'station':'KNYC','received':self.now,'payload':{'properties':{'updateTime':iso(self.now-60),'periods':[
            {'startTime':iso(t),'endTime':iso(t+3600),'temperature':70,'temperatureUnit':'F'} for t in range(int(self.start),int(self.end),3600)]}}}
        def fetch(url):
            if 'gamma-api' in url:return [self.market]
            token='123' if '123' in url else '124'
            return {'asset_id':token,'market':self.market['conditionId'],'timestamp':str(int(self.now*1000)),
                    'min_order_size':'1','asks':[{'price':'.30','size':'10'}],'bids':[{'price':'.29','size':'10'}]}
        self.s=Independent(fetch,lambda:self.now)
        self.s.forecast=lambda c:self.forecast

    def tearDown(self):
        self.j.db.close();self.temp.cleanup()

    def test_independent_fills_without_source_trade(self):
        report=self.s.cycle(self.j)
        self.assertEqual(report['decisions'][0]['status'],'paper_evaluated')
        self.assertEqual(self.j.snapshot()['paper_fills'],1)
        self.assertFalse(report['orders_enabled'])
        self.s.cycle(self.j)
        self.assertEqual(self.j.snapshot()['paper_fills'],1)

    def test_source_mismatch_never_fills(self):
        self.market['description']=self.market['description'].replace('National Weather Service','Weather Underground')
        report=self.s.cycle(self.j)
        self.assertIn('Unverified settlement source',report['decisions'][0]['reason'])
        self.assertEqual(self.j.snapshot()['paper_fills'],0)

    def test_stale_forecast_never_fills(self):
        self.forecast['received']=self.now-301
        report=self.s.cycle(self.j)
        self.assertIn('Stale forecast',report['decisions'][0]['reason'])
        self.assertEqual(self.j.snapshot()['paper_fills'],0)

    def test_shared_reserve(self):
        self.j.set('cash','40')
        self.s.cycle(self.j)
        self.assertEqual(self.j.snapshot()['paper_fills'],0)


if __name__=='__main__':unittest.main()
