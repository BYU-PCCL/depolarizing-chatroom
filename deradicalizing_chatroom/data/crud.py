from datetime import datetime
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from . import models
from .database import Base, engine
from ..util import hash_pw, sec, random_color


class DataAccess:
    def __init__(self, session: Session):
        self._session = session

    @property
    def session(self) -> Session:
        return self._session

    def commit(self) -> None:
        """
        Commit changes to database
        """
        self._session.commit()

    def add_to_db(self, obj: Base) -> None:
        """
        Add object to database
        """
        self._session.add(obj)
        self.commit()

    def add_code(self, code, expiry, fmt="%Y-%m-%d") -> models.Code:
        """
        code: str
        expiry: datetime (default format YYYY-MM-DD)

        returns Code
        """
        self.add_to_db(
            (c := models.Code(code=code, expiry=datetime.strptime(expiry, fmt)))
        )
        return c

    def add_chatroom(self, prompt) -> models.Chatroom:
        """
        Prompt to talk about in chatroom

        returns Chatroom
        """

        self.add_to_db((c := models.Chatroom(prompt=prompt)))
        return c

    def process_login(self, email, pw) -> Optional[models.User]:
        # TODO: HANDLE SESSION CHANGES IN THE CALLING METHOD
        # TODO: HANDLE SESSION CHANGES IN THE CALLING METHOD
        # TODO: HANDLE SESSION CHANGES IN THE CALLING METHOD
        # TODO: HANDLE SESSION CHANGES IN THE CALLING METHOD
        """
        If database contains User, log them in
        """
        q = self._session.query(models.User).filter_by(email=email).first()
        if q is not None:
            # confirm user password
            if hash_pw(pw, q.salt) != q.password:
                return None
            # TODO: HANDLE SESSION CHANGES IN THE CALLING METHOD
            # TODO: HANDLE SESSION CHANGES IN THE CALLING METHOD
            # TODO: HANDLE SESSION CHANGES IN THE CALLING METHOD
            # TODO: HANDLE SESSION CHANGES IN THE CALLING METHOD
            return q

        return None

    def process_signup(self, email, username, affiliation, pw) -> bool:
        """
        If database has email or username, return false
        otherwise, add user to Users
        """
        # if contains email or username
        if (
            self._session.query(models.User).filter_by(email=email).first()
            or self._session.query(models.User).filter_by(username=username).first()
        ):
            return False

        # add user to database
        salt = sec(7)
        self.add_to_db(
            models.User(
                email=email,
                username=username,
                affiliation=affiliation,
                password=hash_pw(pw, salt),
                salt=salt,
                color=random_color(),
            )
        )

        # add user to session
        # TODO: HANDLE SESSION CHANGES IN THE CALLING METHOD
        # TODO: HANDLE SESSION CHANGES IN THE CALLING METHOD
        # TODO: HANDLE SESSION CHANGES IN THE CALLING METHOD
        # TODO: HANDLE SESSION CHANGES IN THE CALLING METHOD
        # TODO: HANDLE SESSION CHANGES IN THE CALLING METHOD
        # TODO: HANDLE SESSION CHANGES IN THE CALLING METHOD
        # TODO: HANDLE SESSION CHANGES IN THE CALLING METHOD
        # TODO: HANDLE SESSION CHANGES IN THE CALLING METHOD
        # TODO: HANDLE SESSION CHANGES IN THE CALLING METHOD
        # TODO: HANDLE SESSION CHANGES IN THE CALLING METHOD
        # TODO: HANDLE SESSION CHANGES IN THE CALLING METHOD
        # TODO: HANDLE SESSION CHANGES IN THE CALLING METHOD
        # session["user"] = {"email": email, "username": username}

        return True


class TestDataAccess(DataAccess):
    def initialize_test(self, nusers=8, ncodes=2, nchats=2):
        """
        nusers: int, number of users to test with
        ncodes: int, number of codes (will be divided evenly amongst users)
        nchats: int, number of chats (per code)
        WARNING: wipes test database
        """
        assert nusers // (nchats * ncodes) == nusers / (
            nchats * ncodes
        ), "Chats or codes do not evenly distribute amongst users."

        # reset test database
        if (db_path := Path("../chatrooms_test.sqlite3")).exists():
            db_path.unlink()
            Base.metadata.create_all(bind=engine)

        # populate database with nusers users
        users = []
        for nu in range(nusers):
            u = models.User(
                email=f"{nu}@email.com", username=f"user{nu}", color=random_color()
            )
            users.append(u)
            self.add_to_db(u)

        # populate database with ncodes codes and, for each code, nchats chatrooms
        codes = []
        chats = []
        for nco in range(ncodes):
            codes.append(self.add_code(f"code_{nco}", "2021-09-01"))
            # add chats
            for nch in range(nchats):
                chats.append(self.add_chatroom(f"Chatroom {nch}"))

        # assign codes and chats to users
        for u, co, ch in zip(
            users, codes * (nusers // ncodes), chats * (nusers // (ncodes * nchats))
        ):
            u.code_id = co.id
            u.chatroom_id = ch.id

        # commit changes
        self.commit()

    def initialize_chat_test(self) -> None:
        if (db_path := Path("chatrooms_test.sqlite3")).exists():
            db_path.unlink()

        # Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)

        salt = sec(7)
        republican = models.User(
            # TODO(vinhowe): Why do we have colors???
            email=f"republican@a.com",
            username=f"republican",
            password=hash_pw("a", salt),
            salt=salt,
            status="chatroom",
            affiliation="Republican",
            color=random_color(),
        )
        democrat = models.User(
            email=f"democrat@a.com",
            username=f"democrat",
            password=hash_pw("a", salt),
            salt=salt,
            status="chatroom",
            affiliation="Democrat",
            color=random_color(),
        )
        self.add_to_db(republican)
        self.add_to_db(democrat)

        code = self.add_code("chat", "2098-01-01")
        chatroom = self.add_chatroom("Gun control in America: More or Less?")

        republican.code_id = code.id
        republican.chatroom_id = chatroom.id

        democrat.code_id = code.id
        democrat.chatroom_id = chatroom.id

        self.commit()
