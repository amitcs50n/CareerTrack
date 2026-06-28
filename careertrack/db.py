import os

import snowflake.connector
from snowflake.connector import DictCursor


def get_snowflake_connection():
    """Create a Snowflake connection from environment variables."""
    required = [
        "SNOWFLAKE_ACCOUNT",
        "SNOWFLAKE_USER",
        "SNOWFLAKE_PASSWORD",
        "SNOWFLAKE_WAREHOUSE",
        "SNOWFLAKE_DATABASE",
        "SNOWFLAKE_SCHEMA",
    ]
    missing = [key for key in required if not os.getenv(key)]
    if missing:
        raise RuntimeError(
            "Missing Snowflake environment variables: " + ", ".join(missing)
        )

    connection_options = {
        "account": os.getenv("SNOWFLAKE_ACCOUNT"),
        "user": os.getenv("SNOWFLAKE_USER"),
        "password": os.getenv("SNOWFLAKE_PASSWORD"),
        "warehouse": os.getenv("SNOWFLAKE_WAREHOUSE"),
        "database": os.getenv("SNOWFLAKE_DATABASE"),
        "schema": os.getenv("SNOWFLAKE_SCHEMA"),
    }

    role = os.getenv("SNOWFLAKE_ROLE")
    if role:
        connection_options["role"] = role

    return snowflake.connector.connect(**connection_options)


def fetch_one(sql, params=None):
    conn = get_snowflake_connection()
    cursor = conn.cursor(DictCursor)
    try:
        cursor.execute(sql, params or ())
        return cursor.fetchone()
    finally:
        cursor.close()
        conn.close()


def fetch_all(sql, params=None):
    conn = get_snowflake_connection()
    cursor = conn.cursor(DictCursor)
    try:
        cursor.execute(sql, params or ())
        return cursor.fetchall()
    finally:
        cursor.close()
        conn.close()


def execute_write(sql, params=None):
    conn = get_snowflake_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(sql, params or ())
        conn.commit()
    finally:
        cursor.close()
        conn.close()
