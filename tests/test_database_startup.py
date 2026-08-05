import unittest
from unittest.mock import Mock, patch

from sqlalchemy.exc import OperationalError

from database import initialize_database, is_database_ready


class ContextManager:
    def __init__(self, value):
        self.value = value

    def __enter__(self):
        return self.value

    def __exit__(self, exc_type, exc_value, traceback):
        return False


class DatabaseStartupTests(unittest.TestCase):
    @patch("database.Base.metadata.create_all")
    def test_postgres_schema_creation_takes_advisory_lock(self, create_all):
        connection = Mock()
        db_engine = Mock()
        db_engine.dialect.name = "postgresql"
        db_engine.begin.return_value = ContextManager(connection)

        initialize_database(db_engine=db_engine, max_attempts=1)

        connection.execute.assert_called_once()
        create_all.assert_called_once_with(bind=connection)

    @patch("database.time.sleep")
    @patch("database.Base.metadata.create_all")
    def test_temporary_connection_failure_is_retried(self, create_all, sleep):
        connection = Mock()
        db_engine = Mock()
        db_engine.dialect.name = "sqlite"
        db_engine.begin.side_effect = [
            OperationalError("connect", {}, Exception("unavailable")),
            ContextManager(connection),
        ]

        initialize_database(
            db_engine=db_engine,
            max_attempts=2,
            initial_delay_seconds=0.25,
        )

        sleep.assert_called_once_with(0.25)
        create_all.assert_called_once_with(bind=connection)

    def test_readiness_returns_false_when_database_is_unavailable(self):
        db_engine = Mock()
        db_engine.connect.side_effect = OperationalError(
            "connect",
            {},
            Exception("unavailable"),
        )

        self.assertFalse(is_database_ready(db_engine=db_engine))


if __name__ == "__main__":
    unittest.main()
