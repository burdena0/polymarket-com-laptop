from datetime import datetime

def stamp(text):
    value = datetime.fromisoformat(text.replace('Z', '+00:00'))
    if value.tzinfo is None:
        raise ValueError('Forecast timestamp needs timezone')
    return value
