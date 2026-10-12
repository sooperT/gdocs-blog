"""Pick the database by environment, never by hand.

Every script that wipes or writes a TomBot database calls resolve_db() first.
It reads `--env staging|production` from the command line, loads the matching
env file (`.env.staging` or `.env`), and refuses to continue unless the database
name in NILEDB_URL belongs to that environment. There is nothing to type and no
default: a script run without --env does nothing.

    python3 scripts/load_content_v3.py --env staging
    python3 scripts/load_content_v3.py --env production

Rule (PRD v3 section 8, R1012-3): staging code only ever talks to a database
whose name contains "staging"; production is the one database named "niledb".
"""
import os
import sys
from urllib.parse import urlparse

from dotenv import load_dotenv

ENVS = {
    "staging": {"file": ".env.staging", "ok": lambda name: "staging" in name},
    "production": {"file": ".env", "ok": lambda name: name == "niledb"},
}


def resolve_db(action="write to"):
    """Return NILEDB_URL for the --env given on the command line, or exit."""
    args = sys.argv[1:]
    env = None
    for i, a in enumerate(args):
        if a == "--env" and i + 1 < len(args):
            env = args[i + 1]
        elif a.startswith("--env="):
            env = a.split("=", 1)[1]
    if env not in ENVS:
        sys.exit("Usage: %s --env staging|production   (no default: nothing was changed)" % os.path.basename(sys.argv[0]))
    spec = ENVS[env]
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(root, spec["file"])
    if not os.path.exists(path):
        sys.exit("%s not found. Nothing was changed." % spec["file"])
    load_dotenv(os.path.join(root, ".env"))          # API keys live here for every environment
    load_dotenv(path, override=True)                 # the env file decides the database
    url = os.environ.get("NILEDB_URL", "")
    name = (urlparse(url).path or "/").lstrip("/")
    host = urlparse(url).hostname or "?"
    if not url or not spec["ok"](name):
        sys.exit("NILEDB_URL in %s points at '%s', which is not a %s database. Nothing was changed."
                 % (spec["file"], name or "(empty)", env))
    print("%s: %s database '%s' on %s" % (env.upper(), action, name, host))
    return url
