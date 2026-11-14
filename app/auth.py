"""Clerk session verification for server-rendered Flask requests."""
import base64
import os
import re
from functools import wraps
from pathlib import Path
from urllib.parse import urlsplit

import httpx
from clerk_backend_api.security import authenticate_request
from clerk_backend_api.security.types import AuthenticateRequestOptions
from dotenv import load_dotenv
from flask import g, redirect, render_template, request, url_for

from db import ConfigurationError

# Separate CLI-managed development keys preserve existing Neon/Flask settings.
load_dotenv(Path(__file__).with_name('.env.clerk'))


def public_config():
    key = os.getenv('CLERK_PUBLISHABLE_KEY', '').strip()
    if not key:
        return {'key': '', 'domain': ''}
    try:
        if not key.startswith(('pk_test_', 'pk_live_')):
            raise ValueError
        encoded = key.split('_', 2)[2]
        domain = base64.b64decode(encoded + '=' * (-len(encoded) % 4), validate=True).decode().removesuffix('$')
        if not re.fullmatch(r'[a-zA-Z0-9](?:[a-zA-Z0-9.-]*[a-zA-Z0-9])?', domain) or '.' not in domain:
            raise ValueError
    except (ValueError, UnicodeError):
        raise ConfigurationError('Clerk publishable key is invalid. Pull development keys again.') from None
    return {'key': key, 'domain': domain}


def authorized_parties():
    value = os.getenv('CLERK_AUTHORIZED_PARTIES', 'http://localhost:5000,http://127.0.0.1:5000')
    parties = [origin.strip().rstrip('/') for origin in value.split(',') if origin.strip()]
    if not parties or any(urlsplit(p).scheme not in ('http', 'https') or not urlsplit(p).netloc for p in parties):
        raise ConfigurationError('Set CLERK_AUTHORIZED_PARTIES to comma-separated application origins.')
    return parties


def current_user_id():
    if hasattr(g, 'clerk_user_id'):
        return g.clerk_user_id
    g.clerk_user_id = None
    # No network request is needed for anonymous browsing.
    if not request.headers.get('Authorization') and not any(name.startswith('__session') for name in request.cookies):
        return None
    secret = os.getenv('CLERK_SECRET_KEY', '')
    config = public_config()
    if not secret or not config['key']:
        raise ConfigurationError('Clerk is not configured. Pull development keys before signing in.')
    try:
        state = authenticate_request(
            httpx.Request(request.method, request.url, headers=dict(request.headers)),
            AuthenticateRequestOptions(secret_key=secret, authorized_parties=authorized_parties(),
                                       accepts_token=['session_token']),
        )
    except ConfigurationError:
        raise
    except Exception:
        raise ConfigurationError('Sign-in verification is temporarily unavailable. Please retry.') from None
    payload = state.payload or {}
    # Bind the verified JWT to this app's configured Frontend API as well.
    if (state.is_signed_in and payload.get('iss') == 'https://' + config['domain']
            and isinstance(payload.get('sub'), str) and payload['sub'].startswith('user_')
            and payload.get('sid') and payload.get('exp')):
        g.clerk_user_id = payload['sub']
    return g.clerk_user_id


def safe_next(value):
    # Never redirect to an external URL or back into an auth loop.
    if (not value or not value.startswith('/') or value.startswith('//') or '\\' in value
            or any(ord(c) < 32 for c in value) or urlsplit(value).path in ('/sign-in', '/sign-up')):
        return '/'
    return value


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not public_config()['key'] or not os.getenv('CLERK_SECRET_KEY'):
            raise ConfigurationError('Clerk is not configured. Pull development keys before signing in.')
        if not current_user_id():
            if request.method == 'GET':
                return redirect(url_for('sign_in', next=safe_next(request.full_path.rstrip('?'))))
            return render_template('error.html', message='Sign in before submitting this form, then retry.'), 401
        return view(*args, **kwargs)
    return wrapped
