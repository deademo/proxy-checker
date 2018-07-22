import datetime
import random

import session_sets


def random_session():
    return random.choice(session_sets.sessions)

def serializer(obj):
    """JSON encoder function for SQLAlchemy special classes."""
    if isinstance(obj, datetime.date):
        return obj.isoformat()
    elif isinstance(obj, decimal.Decimal):
        return float(obj)
