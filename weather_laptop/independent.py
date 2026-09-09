"""Independent NWS sensitivity research with settlement-source matching."""
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
import time
from urllib.parse import urlencode, urlparse
from .core import json_get, number, quote, Feed
from .contracts import contract_from_rules
from .intraday_weather import day_bounds, summarize_intraday, probability_range


class Independent:
    def __init__(self, fetch=json_get, clock=time.time):
        self.fetch = fetch
        self.clock = clock
        self.cache = {}
        self.offset = 0

    def weather(self, url):
        if urlparse(url).scheme != 'https' or urlparse(url).hostname != 'api.weather.gov':
            raise ValueError('Unexpected weather source host')
        return self.fetch(url)

    def forecast(self, contract):
        station = contract['station']
        cached = self.cache.get(station)
        if cached and 0 <= self.clock() - cached['received'] < 120:
            return cached
        metadata = self.weather('https://api.weather.gov/stations/' + station)
        if metadata['properties']['stationIdentifier'] != station:
            raise ValueError('NWS station identity mismatch')
        lon, lat = metadata['geometry']['coordinates'][:2]
        point = self.weather(f'https://api.weather.gov/points/{lat},{lon}')
        payload = self.weather(point['properties']['forecastHourly'])
        result = dict(station=station, payload=payload, received=self.clock())
        self.cache[station] = result
        return result

    def observations(self, contract):
        start, end = day_bounds(contract['station'], contract['date'])
        now = self.clock()
        if now < start:
            return None
        query = urlencode({'start': datetime.fromtimestamp(start, timezone.utc).isoformat(),
                           'end': datetime.fromtimestamp(min(now, end), timezone.utc).isoformat(), 'limit': 500})
        payload = self.weather(f"https://api.weather.gov/stations/{contract['station']}/observations?{query}")
        # The model rejects a remaining pagination cursor; do not pretend incomplete observations are complete.
        return dict(station=contract['station'], payload=payload, received=self.clock())

    def cycle(self, journal):
        started = self.clock()
        rows = self.fetch('https://gamma-api.polymarket.com/markets?' + urlencode({
            'active': 'true', 'closed': 'false', 'limit': 100, 'offset': self.offset}))
        if not isinstance(rows, list) or len(rows) > 100:
            raise ValueError('Invalid market inventory')
        self.offset = self.offset + 100 if len(rows) == 100 else 0
        decisions = []
        for market in rows:
            if 'highest temperature' not in market.get('question', '').lower():
                continue
            if self.clock() - started > 45:
                break
            record = {'slug': market.get('slug'), 'status': 'rejected'}
            try:
                contract = contract_from_rules(market)
                if market.get('closed') is not False or market.get('acceptingOrders') is not True:
                    raise ValueError('Market not accepting orders')
                summary = summarize_intraday(self.forecast(contract), self.observations(contract), contract, self.clock())
                tokens, outcomes = market['clobTokenIds'], market['outcomes']
                tokens = json.loads(tokens) if isinstance(tokens, str) else tokens
                outcomes = json.loads(outcomes) if isinstance(outcomes, str) else outcomes
                if len(tokens) != 2 or set(outcomes) != {'Yes', 'No'}:
                    raise ValueError('Invalid binary outcome mapping')
                selected = None
                reasons = []
                for token, outcome in zip(tokens, outcomes):
                    low, high = probability_range(summary, contract, outcome.upper())
                    # quote() permits max_price_loss beyond reference price. Offset it
                    # so the worst limit still preserves five cents after allowance.
                    ceiling = number(low) - Decimal('.05') - number(journal.config['allowance_per_share'])
                    event = {'asset': token, 'conditionId': market['conditionId'], 'side': 'BUY',
                             'price': str(ceiling - number(journal.config['max_price_loss'])),
                             'size': '5', 'strategy': 'independent', 'station_day': contract['station']+':'+contract['date']}
                    try:
                        if journal.db.execute('SELECT 1 FROM station_claims WHERE station_day=?', (event['station_day'],)).fetchone():
                            raise ValueError('Station-day already held')
                        feed = Feed(journal.config['source_wallet'], self.fetch)
                        book = feed.book(event)
                        plan = quote(event, book, number(journal.get('cash')), Decimal(0), self.clock(), journal.config)
                        edge = number(low) - number(plan['worst_price']) - number(journal.config['allowance_per_share'])
                        if selected is None or edge > selected[0]:
                            selected = (edge, event, book, plan)
                    except ValueError as exc:
                        reasons.append(outcome + ': ' + str(exc))
                if selected:
                    edge, event, book, plan = selected
                    identity = hashlib.sha256(('independent:'+event['station_day']+event['asset']).encode()).hexdigest()
                    with journal.atomic():
                        journal.db.execute('INSERT OR IGNORE INTO events VALUES(?,?,?,?,?)',
                            (identity, self.clock(), 'observed', '', json.dumps({'event':event,'forecast':summary})))
                    journal.evaluate(identity, event, book, self.clock())
                    record.update(status='paper_evaluated', edge=str(edge), plan=plan)
                else:
                    record['reason'] = ' | '.join(reasons)
            except ValueError as exc:
                record['reason'] = str(exc)
            except Exception as exc:
                record['reason'] = 'Source unavailable: ' + type(exc).__name__
            decisions.append(record)
        return {'at': self.clock(), 'status': 'observing', 'model': 'independent_nws_intraday_v2',
                'model_calibrated': False, 'orders_enabled': False, 'decisions': decisions,
                'inventory_offset_next': self.offset, 'markets_scanned': len(rows),
                'coverage': 'One rotating 100-market page per cycle; NWS CLI settlement rules required.'}
