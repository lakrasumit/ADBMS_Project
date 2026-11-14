"""Short-lived SSL connections; exceptions leave transactions rolled back."""
import os
from pathlib import Path
import psycopg
from psycopg.rows import dict_row
from psycopg.conninfo import conninfo_to_dict
from dotenv import load_dotenv

load_dotenv(Path(__file__).with_name('.env'))

class ConfigurationError(Exception):
    pass

def connect():
    url = os.getenv('DATABASE_URL', '').strip()
    if not url:
        raise ConfigurationError('Set DATABASE_URL in app/.env, then initialize the database.')
    try:
        options = conninfo_to_dict(url)
    except Exception:
        raise ConfigurationError('DATABASE_URL is not a valid PostgreSQL connection string.') from None
    # Override insecure URL settings; retain stronger certificate verification if supplied.
    sslmode = options.get('sslmode')
    options['sslmode'] = sslmode if sslmode in ('verify-ca', 'verify-full') else 'require'
    options['connect_timeout'] = 10
    return psycopg.connect(**options, row_factory=dict_row)
