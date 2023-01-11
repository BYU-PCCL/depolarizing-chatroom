import os

# from sqlalchemy import create_engine, event
from sqlalchemy.ext.declarative import declarative_base

# from sqlalchemy.orm import sessionmaker

SQLALCHEMY_DATABASE_URL = os.getenv("DB_URI") or "sqlite+aiosqlite:///"

# check_same_thread=False is only needed for sqlite
# engine = create_engine(
#     SQLALCHEMY_DATABASE_URL
#     # SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
# )


# @event.listens_for(engine, "connect")
# def do_connect(dbapi_connection, _connection_record) -> None:
#     # disable pysqlite's emitting of the BEGIN statement entirely.
#     # also stops it from emitting COMMIT before any DDL.
#     dbapi_connection.isolation_level = None
#
#
# @event.listens_for(engine, "begin")
# def do_begin(conn) -> None:
#     # emit our own BEGIN
#     conn.exec_driver_sql("BEGIN")


# SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()
