from datetime import datetime
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from . import models
from .database import Base, engine


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

    def add_chatroom(self, prompt) -> models.Chatroom:
        """
        Prompt to talk about in chatroom

        returns Chatroom
        """
        self.add_to_db((c := models.Chatroom(prompt=prompt)))
        return c

    def process_login(self, response_id) -> Optional[models.User]:
        """
        If database contains User, log them in
        """
        q = self._session.query(models.User).filter_by(response_id=response_id).first()
        if q is not None:
            # confirm user password
            return q

        return None

    def process_signup(self, response_id, treatment: int) -> bool:
        """
        If database has response_id, return false
        otherwise, add user to Users
        """
        if self._session.query(models.User).filter_by(response_id=response_id).first():
            return False

        user = models.User(response_id=response_id, treatment=treatment)

        # add user to database
        self.add_to_db(user)

        return user


class TestDataAccess(DataAccess):
    def initialize_chat_test(self) -> None:
        if (db_path := Path("chatrooms_test.sqlite3")).exists():
            db_path.unlink()

        # Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)

        oppose = models.User(
            response_id="oppose",
            treatment=4,
        )
        support = models.User(
            response_id="support",
            treatment=1,
        )
        self.add_to_db(oppose)
        self.add_to_db(support)

        # code = self.add_code("chat", "2098-01-01")
        chatroom = self.add_chatroom("Gun Control in America: More or Less?")

        # oppose.code_id = code.id
        oppose.chatroom_id = chatroom.id

        # support.code_id = code.id
        support.chatroom_id = chatroom.id

        self.commit()

    def initialize_waiting_room_test(self) -> None:
        if (db_path := Path("chatrooms_test.sqlite3")).exists():
            db_path.unlink()

        Base.metadata.create_all(bind=engine)

        oppose = models.User(
            response_id="oppose",
            status="chatroom",
            treatment=5,
            view="I oppose increased gun control.",
        )
        support = models.User(
            response_id="support",
            status="chatroom",
            treatment=1,
            view="I support increased gun control.",
        )
        self.add_to_db(oppose)
        self.add_to_db(support)


def build_prod_database(force=False) -> None:
    """
    Build production database
    """
    if (db_path := Path("chatrooms.sqlite3")).exists():
        if force:
            db_path.unlink()
        else:
            raise FileExistsError("Database already exists.")
    Base.metadata.create_all(bind=engine)
