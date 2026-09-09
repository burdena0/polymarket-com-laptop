"""Public evidence and transactional paper simulation. No signing or order API."""
from contextlib import contextmanager
from decimal import Decimal, ROUND_DOWN
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import time
from urllib.parse import urlencode
from urllib.request import Request, urlopen


def number(value):
    if isinstance(value, bool):
        raise ValueError('Boolean is not a number')
    result = Decimal(str(value))
    if not result.is_finite():
        raise ValueError('Nonfinite number')
    return result


def wallet(value):
    if not isinstance(value, str) or not re.fullmatch(r'0x[0-9a-fA-F]{40}', value):
        raise ValueError('A public wallet address is required')
    return value.lower()


def json_get(url):
    with urlopen(Request(url, headers={'User-Agent': 'WeatherLaptop/0.1'}), timeout=8) as response:
        raw = response.read(2_000_001)
    if len(raw) > 2_000_000:
        raise ValueError('Response too large')
    return json.loads(raw)


class Feed:
    def __init__(self, address, fetch=json_get):
        self.address = wallet(address)
        self.fetch = fetch

    def activity(self):
        rows = self.fetch('https://data-api.polymarket.com/activity?' + urlencode({
            'user': self.address, 'type': 'TRADE', 'limit': 100,
            'sortBy': 'TIMESTAMP', 'sortDirection': 'DESC'}))
        if not isinstance(rows, list) or len(rows) > 100:
            raise ValueError('Invalid activity page')
        for row in rows:
            if not isinstance(row, dict) or wallet(row.get('proxyWallet')) != self.address:
                raise ValueError('Activity account mismatch')
        return rows

    def book(self, event):
        book = self.fetch('https://clob.polymarket.com/book?' + urlencode({'token_id': event['asset']}))
        if (book.get('asset_id') != event['asset']
                or book.get('market', '').lower() != event['conditionId'].lower()):
            raise ValueError('Book token or condition mismatch')
        return book

    def market(self, event):
        rows = self.fetch('https://gamma-api.polymarket.com/markets?' + urlencode({
            'condition_ids': event['conditionId'], 'limit': 10}))
        matches = [r for r in rows if r.get('conditionId', '').lower() == event['conditionId'].lower()]
        if len(matches) != 1:
            raise ValueError('Market not uniquely identified')
        row = matches[0]
        tokens = row.get('clobTokenIds')
        tokens = json.loads(tokens) if isinstance(tokens, str) else tokens
        if (not isinstance(tokens, list) or event['asset'] not in tokens
                or row.get('closed') is not False or row.get('acceptingOrders') is not True
                or 'highest temperature' not in row.get('question', '').lower()):
            raise ValueError('Market is not an open highest-temperature market')
        return row


def event_id(row):
    fields = ('transactionHash', 'asset', 'conditionId', 'side', 'size', 'price', 'timestamp')
    return hashlib.sha256(json.dumps({k: row.get(k) for k in fields}, sort_keys=True).encode()).hexdigest()


def validate_event(row, now):
    if row.get('type') != 'TRADE' or row.get('side') not in ('BUY', 'SELL'):
        raise ValueError('Not a trade')
    if 'highest temperature' not in row.get('title', '').lower():
        raise ValueError('Not a weather market')
    if not re.fullmatch(r'0x[0-9a-fA-F]{64}', str(row.get('conditionId'))):
        raise ValueError('Invalid condition ID')
    if not re.fullmatch(r'[0-9]{1,78}', str(row.get('asset'))) or not 0 < int(row['asset']) < 2**256:
        raise ValueError('Invalid token ID')
    if not re.fullmatch(r'0x[0-9a-fA-F]{64}', str(row.get('transactionHash'))):
        raise ValueError('Invalid transaction hash')
    if not 0 <= number(row['timestamp']) <= number(now):
        raise ValueError('Future or invalid activity time')
    if not 0 < number(row['price']) < 1 or number(row['size']) <= 0:
        raise ValueError('Invalid trade amount')


def quote(row, book, cash, owned, now, config):
    stamp = number(book['timestamp']) / 1000
    if not 0 <= number(now) - stamp <= 120:
        raise ValueError('Book timestamp cannot establish a current quote')
    def levels(key):
        result = [(number(r['price']), number(r['size'])) for r in book[key]]
        if not result or any(not 0 < p < 1 or q <= 0 for p, q in result):
            raise ValueError('Empty or malformed book')
        if len({p for p, q in result}) != len(result):
            raise ValueError('Duplicate book level')
        return sorted(result, reverse=key == 'bids')
    bids, asks = levels('bids'), levels('asks')
    if bids[0][0] >= asks[0][0]:
        raise ValueError('Crossed book')
    side = row['side']
    ladder = asks if side == 'BUY' else bids
    allowance = number(config['allowance_per_share'])
    desired = min(number(row['size']), number(config['max_shares']))
    if side == 'BUY':
        budget = min(number(config['per_order_cap']), max(Decimal(0), cash - number(config['cash_reserve'])))
        # Conservative worst-price budget; never exceeds available cash.
        desired = min(desired, budget / (ladder[-1][0] + allowance))
    else:
        desired = min(desired, owned)
    desired = desired.quantize(Decimal('.01'), rounding=ROUND_DOWN)
    minimum = number(book['min_order_size'])
    if minimum <= 0 or desired < minimum:
        raise ValueError('Insufficient cash or owned shares for market minimum')
    left, total, worst = desired, Decimal(0), ladder[0][0]
    for price, size in ladder:
        taken = min(left, size)
        total += taken * price
        left -= taken
        worst = price
        if left == 0:
            break
    if left:
        raise ValueError('Insufficient displayed depth')
    loss = worst - number(row['price']) if side == 'BUY' else number(row['price']) - worst
    if loss > number(config['max_price_loss']):
        raise ValueError('Price moved beyond configured loss allowance')
    modeled_fee = desired * allowance
    if side == 'BUY' and total + modeled_fee > budget:
        raise ValueError('Order exceeds cash budget')
    return {'side': side, 'quantity': str(desired), 'gross': str(total),
            'modeled_fee': str(modeled_fee), 'worst_price': str(worst),
            'execution_eligible': False, 'fill_basis': 'displayed depth simulation, not an actual fill'}


DEFAULTS = {'initial_cash': '50', 'cash_reserve': '40', 'subscription_monthly': '200',
            'per_order_cap': '5', 'max_shares': '5', 'max_price_loss': '0.02',
            'allowance_per_share': '0.04', 'poll_seconds': 30}


class Journal:
    def __init__(self, path, config):
        self.config = dict(config)
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path, isolation_level=None, timeout=5)
        self.db.row_factory = sqlite3.Row
        self.db.executescript('''
          PRAGMA journal_mode=WAL;
          PRAGMA synchronous=FULL;
          CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
          CREATE TABLE IF NOT EXISTS events (id TEXT PRIMARY KEY, at REAL, state TEXT, reason TEXT, evidence TEXT);
          CREATE TABLE IF NOT EXISTS positions (token TEXT PRIMARY KEY, shares TEXT, cost TEXT);
          CREATE TABLE IF NOT EXISTS fills (id TEXT PRIMARY KEY, at REAL, details TEXT);
          CREATE TABLE IF NOT EXISTS station_claims (station_day TEXT PRIMARY KEY, token TEXT);
        ''')
        with self.atomic():
            encoded = json.dumps(config, sort_keys=True)
            old = self.get('config')
            if old and old != encoded:
                raise ValueError('Configuration changed: use a new data directory')
            if not old:
                for key, value in {'config': encoded, 'cash': config['initial_cash'], 'realized': '0', 'fees': '0'}.items():
                    self.set(key, value)

    @contextmanager
    def atomic(self):
        self.db.execute('BEGIN IMMEDIATE')
        try:
            yield
            self.db.execute('COMMIT')
        except BaseException:
            self.db.execute('ROLLBACK')
            raise

    def get(self, key):
        row = self.db.execute('SELECT value FROM metadata WHERE key=?', (key,)).fetchone()
        return row[0] if row else None

    def set(self, key, value):
        self.db.execute('INSERT OR REPLACE INTO metadata VALUES (?,?)', (key, str(value)))

    def observe(self, rows, now):
        fresh = []
        with self.atomic():
            baseline = self.get('baseline') is None
            if baseline:
                self.set('baseline', now)
            for row in sorted(rows, key=lambda r: number(r.get('timestamp', 0))):
                identity = event_id(row)
                state = 'baseline' if baseline or number(row['timestamp']) <= number(self.get('baseline')) else 'observed'
                cursor = self.db.execute('INSERT OR IGNORE INTO events VALUES(?,?,?,?,?)',
                    (identity, now, state, '', json.dumps(row)))
                if cursor.rowcount and state == 'observed':
                    fresh.append((identity, row))
        return fresh

    def evaluate(self, identity, row, book, now):
        with self.atomic():
            current = self.db.execute('SELECT state FROM events WHERE id=?', (identity,)).fetchone()
            if not current or current[0] != 'observed':
                return
            holding = self.db.execute('SELECT shares,cost FROM positions WHERE token=?', (row['asset'],)).fetchone()
            shares, cost = (number(holding[0]), number(holding[1])) if holding else (Decimal(0), Decimal(0))
            if row['side'] == 'BUY' and shares > 0:
                raise ValueError('Already held in shared paper account')
            if row['side'] == 'BUY' and row.get('station_day'):
                self.db.execute('INSERT INTO station_claims VALUES(?,?)', (row['station_day'],row['asset']))
            fill = quote(row, book, number(self.get('cash')), shares, now, self.config)
            qty, gross, fee = map(number, (fill['quantity'], fill['gross'], fill['modeled_fee']))
            if row['side'] == 'BUY':
                shares += qty
                cost += gross + fee
                self.set('cash', number(self.get('cash')) - gross - fee)
            else:
                basis = cost * qty / shares
                shares -= qty
                cost -= basis
                self.set('cash', number(self.get('cash')) + gross - fee)
                self.set('realized', number(self.get('realized')) + gross - fee - basis)
            self.set('fees', number(self.get('fees')) + fee)
            self.db.execute('INSERT OR REPLACE INTO positions VALUES(?,?,?)', (row['asset'], str(shares), str(cost)))
            self.db.execute('INSERT INTO fills VALUES(?,?,?)', (identity, now, json.dumps(fill)))
            self.db.execute("UPDATE events SET state='paper_filled' WHERE id=?", (identity,))

    def reject(self, identity, reason):
        self.db.execute("UPDATE events SET state='rejected',reason=? WHERE id=? AND state='observed'", (reason, identity))

    def snapshot(self):
        return {'cash': self.get('cash'), 'realized_paper_pnl': self.get('realized'),
                'modeled_fees': self.get('fees'), 'monthly_subscription_expense': self.config['subscription_monthly'],
                'positions': [dict(r) for r in self.db.execute("SELECT * FROM positions WHERE CAST(shares AS REAL)>0")],
                'latest_decisions': [dict(r) for r in self.db.execute('SELECT id,at,state,reason FROM events ORDER BY at DESC,rowid DESC LIMIT 30')],
                'paper_fills': self.db.execute('SELECT COUNT(*) FROM fills').fetchone()[0],
                'orders_enabled': False, 'mode': 'paper', 'automatic_settlement': False}
