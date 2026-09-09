import tempfile
from pathlib import Path
import unittest
from weather_laptop.core import DEFAULTS, Feed, Journal, event_id, quote, validate_event, number


def event(timestamp=101, side='BUY'):
    return dict(type='TRADE', title='Highest temperature in NYC?', asset='123',
                conditionId='0x'+'a'*64, transactionHash='0x'+'b'*64,
                timestamp=timestamp, side=side, size='5', price='.30')


def book():
    return dict(timestamp='101000', min_order_size='1',
                bids=[dict(price='.29', size='10')], asks=[dict(price='.30', size='10')])


class Checks(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.journal = Journal(Path(self.temp.name)/'paper.sqlite', DEFAULTS)
        self.journal.observe([], 100)

    def tearDown(self):
        self.journal.db.close()
        self.temp.cleanup()

    def test_no_historical_replay(self):
        self.assertEqual(self.journal.observe([event(99)], 101), [])

    def test_no_duplicate_fill(self):
        e = event()
        key = self.journal.observe([e], 101)[0][0]
        self.journal.evaluate(key, e, book(), 101)
        self.journal.evaluate(key, e, book(), 101)
        self.assertEqual(self.journal.snapshot()['paper_fills'], 1)
        self.assertEqual(number(self.journal.get('cash')), number('48.30'))
        self.assertEqual(self.journal.observe([e], 102), [])

    def test_sell_only_owned(self):
        with self.assertRaisesRegex(ValueError, 'owned shares'):
            quote(event(side='SELL'), book(), number(50), number(0), 101, DEFAULTS)

    def test_cash_reserve(self):
        with self.assertRaisesRegex(ValueError, 'Insufficient cash'):
            quote(event(), book(), number(40), number(0), 101, DEFAULTS)

    def test_price_loss(self):
        b = book(); b['asks'][0]['price'] = '.40'
        with self.assertRaisesRegex(ValueError, 'Price moved'):
            quote(event(), b, number(50), number(0), 101, DEFAULTS)

    def test_bad_books(self):
        for key, value in [('timestamp','-200000'), ('asks',[]), ('bids',[dict(price='.31',size='5')])]:
            with self.subTest(key=key):
                b=book(); b[key]=value
                with self.assertRaises(ValueError):
                    quote(event(), b, number(50), number(0), 101, DEFAULTS)

    def test_invalid_event(self):
        for key, value in [('timestamp',102),('price','NaN'),('asset','0'),('transactionHash','invalid')]:
            e=event(); e[key]=value
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate_event(e,101)

    def test_configuration_immutable(self):
        with self.assertRaisesRegex(ValueError, 'Configuration changed'):
            Journal(Path(self.temp.name)/'paper.sqlite', dict(DEFAULTS, cash_reserve='20'))

    def test_identity_match(self):
        feed=Feed('0x'+'c'*40, lambda url:dict(book(),asset_id='321',market='0x'+'a'*64))
        with self.assertRaisesRegex(ValueError, 'mismatch'):
            feed.book(event())

    def test_sale_realized(self):
        e=event(); key=self.journal.observe([e],101)[0][0]
        self.journal.evaluate(key,e,book(),101)
        e=event(102,'SELL');e['price']='.29'
        key=self.journal.observe([e],102)[0][0]
        self.journal.evaluate(key,e,book(),102)
        self.assertEqual(number(self.journal.get('realized')), number('-.45'))
        self.assertEqual(self.journal.snapshot()['positions'], [])


if __name__ == '__main__':
    unittest.main()
