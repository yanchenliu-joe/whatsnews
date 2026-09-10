import os

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")


def get_connection() -> psycopg2.extensions.connection:
    """
    Open and return a new Postgres connection.
    Rows are returned as plain dicts (RealDictCursor).
    The caller is responsible for closing the connection.
    """
    if not DATABASE_URL:
        raise ValueError(
            "DATABASE_URL is not set. "
            "Copy backend/.env.example to backend/.env and fill in your Supabase URL."
        )
    return psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
