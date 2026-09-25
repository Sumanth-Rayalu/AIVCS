import os
from contextlib import contextmanager
from typing import Iterator

import mysql.connector
from dotenv import load_dotenv

load_dotenv()
from mysql.connector import MySQLConnection


SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INT PRIMARY KEY AUTO_INCREMENT,
    username VARCHAR(64) NOT NULL UNIQUE,
    name VARCHAR(120) NOT NULL,
    email VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS repositories (
    id INT PRIMARY KEY AUTO_INCREMENT,
    owner_id INT NOT NULL,
    name VARCHAR(64) NOT NULL,
    description TEXT NOT NULL,
    path VARCHAR(1024) NOT NULL,
    visibility ENUM('private', 'public') NOT NULL DEFAULT 'private',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY owner_repository_name (owner_id, name),
    CONSTRAINT repositories_owner_fk
        FOREIGN KEY (owner_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS follows (
    follower_id INT NOT NULL,
    followed_id INT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (follower_id, followed_id),
    CONSTRAINT follows_follower_fk
        FOREIGN KEY (follower_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT follows_followed_fk
        FOREIGN KEY (followed_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS issues (
    id INT PRIMARY KEY AUTO_INCREMENT,
    repository_id INT NOT NULL,
    author_id INT NOT NULL,
    title VARCHAR(255) NOT NULL,
    body TEXT NOT NULL,
    state ENUM('open', 'closed') NOT NULL DEFAULT 'open',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT issues_repository_fk
        FOREIGN KEY (repository_id) REFERENCES repositories(id) ON DELETE CASCADE,
    CONSTRAINT issues_author_fk
        FOREIGN KEY (author_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB;
"""


def config() -> dict[str, object]:
    required = ("DB_HOST", "DB_PORT", "DB_USER", "DB_PASSWORD", "DB_NAME")
    missing = [key for key in required if os.environ.get(key) is None]
    if missing:
        raise RuntimeError("Missing database environment variables: " + ", ".join(missing))
    return {
        "host": os.environ["DB_HOST"],
        "port": int(os.environ["DB_PORT"]),
        "user": os.environ["DB_USER"],
        "password": os.environ["DB_PASSWORD"],
        "database": os.environ["DB_NAME"],
    }


@contextmanager
def connection(*, database: bool = True) -> Iterator[MySQLConnection]:
    settings = config()
    if not database:
        settings.pop("database")
    db = mysql.connector.connect(**settings)
    try:
        yield db
    finally:
        db.close()


def initialize() -> None:
    settings = config()
    database_name = str(settings.pop("database"))
    with connection(database=False) as db:
        cursor = db.cursor()
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{database_name}`")
        cursor.close()
    with connection() as db:
        cursor = db.cursor()
        for statement in SCHEMA.split(";"):
            if statement.strip():
                cursor.execute(statement)
        db.commit()
        cursor.close()


def user_row(row: tuple | None) -> dict | None:
    if row is None:
        return None
    return {"id": row[0], "username": row[1], "name": row[2], "email": row[3], "created_at": row[4].isoformat()}
