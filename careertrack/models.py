from flask_login import UserMixin

from .db import fetch_one


class User(UserMixin):
    def __init__(self, user_id, email, name):
        self.id = user_id
        self.email = email
        self.name = name


def get_user_by_id(user_id):
    row = fetch_one(
        """
        SELECT ID, EMAIL, NAME
        FROM USERS
        WHERE ID = %s
        """,
        (user_id,),
    )
    if not row:
        return None
    return User(row["ID"], row["EMAIL"], row["NAME"])


def get_user_by_email(email):
    return fetch_one(
        """
        SELECT ID, EMAIL, NAME, PASSWORD_HASH
        FROM USERS
        WHERE LOWER(EMAIL) = LOWER(%s)
        """,
        (email,),
    )
