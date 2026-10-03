"""Gunicorn settings, read automatically from the directory it starts in.

The default 30-second request limit was too short for a large upload on a
small server: the request was cut off mid-save and the desk saw a bare
"Internal Server Error". Uploads also cap their own processing time (see
apps/applications/compression.py); this is the outer limit.

The number of workers is left to WEB_CONCURRENCY, which the host sets.
"""

timeout = 120
graceful_timeout = 30
keepalive = 5
