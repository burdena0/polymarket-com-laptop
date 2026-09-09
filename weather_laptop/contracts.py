from datetime import date
import hashlib,re
STATIONS={"KLAX","KNYC","KSFO","KMIA","KMDW"}

def contract_from_rules(market):
    text = market.get('description', '')
    station = re.findall('\\bK[A-Z]{3}\\b', text)
    station = set(station) & set(STATIONS)
    day = re.search('for (\\d{4}-\\d{2}-\\d{2})', text)
    if len(station) != 1 or not day or 'highest temperature' not in text.lower():
        raise ValueError('Ambiguous weather identity')
    date.fromisoformat(day[1])
    if 'National Weather Service' not in text or 'Climatological Report' not in text:
        raise ValueError('Unverified settlement source')
    between = re.search('between (-?\\d+)F and (-?\\d+)F', text)
    below = re.search('(?:below|less than) (-?\\d+)F', text)
    at_most = re.search('less than or equal to (-?\\d+)F', text)
    above = re.search('(?:at least|greater than or equal to) (-?\\d+)F', text)
    if between:
        (lower, upper) = map(int, between.groups())
        if lower > upper:
            raise ValueError('Inverted bracket')
    elif at_most:
        (lower, upper) = (None, int(at_most[1]))
    elif below:
        (lower, upper) = (None, int(below[1]) - 1)
    elif above:
        (lower, upper) = (int(above[1]), None)
    else:
        raise ValueError('Unsupported textual bracket; manual rule review required')
    return dict(station=station.pop(), date=day[1], lower_f=lower, upper_f=upper, source='NWS_CLI', slug=market['slug'], rules_sha256=hashlib.sha256(text.encode()).hexdigest())
