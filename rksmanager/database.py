import sqlite3
import decimal
import datetime
import pathlib
import re


class Database:
    """Passes data to and from the database."""
    expected_schema_version = 1

    def __init__(self, db_filename):
        """
        Set up the database connection.

        Args:
            db_filename: Name of the sqlite3 database file to open. Will be
                created if it doesn't already exist.

        """
        # Convert values stored in boolean_integer columns to and from Python's
        # bool type
        sqlite3.register_adapter(bool, int)
        sqlite3.register_converter("boolean_integer", lambda v: v != b"0")

        # Convert values stored in decimal_text columns to and from Python's
        # Decimal type
        sqlite3.register_adapter(decimal.Decimal, str)
        sqlite3.register_converter("decimal_text",
                                   lambda v: decimal.Decimal(v.decode()))

        # Convert values stored in timeofday_text columns to and from Python's
        # time type. Converter code adapted from the sqlite3 module's datetime
        # converter. Doesn't support time zones, in case we care about that in
        # the future.
        def convert_timeofday(val):
            timepart_full = val.split(b".")
            hours, minutes, seconds = map(int, timepart_full[0].split(b":"))
            if len(timepart_full) == 2:
                microseconds = int('{:0<6.6}'.format(timepart_full[1]
                                                     .decode()))
            else:
                microseconds = 0
            return datetime.time(hours, minutes, seconds, microseconds)
        sqlite3.register_adapter(datetime.time, str)
        sqlite3.register_converter("timeofday_text", convert_timeofday)

        self._connection = sqlite3.connect(
            db_filename,
            detect_types=sqlite3.PARSE_DECLTYPES,
        )
        self._connection.row_factory = sqlite3.Row
        # Enable foreign key enforcement
        self._connection.execute("pragma foreign_keys = on;")

    def close(self):
        """
        Close the database connection. No other methods of this Database object
        should be called after calling close().

        """
        self._connection.close()
        del self._connection

    def get_schema_version(self):
        """
        Retrieve the current schema version from the database.

        Returns:
            The schema version as an integer.

        """
        return self._connection.execute("pragma user_version;").fetchone()[0]

    def apply_migrations(self):
        """
        Check the current database schema version and run any migration scripts
        that haven't been run yet.

        """
        migration_name_regex = re.compile(r"0*([0-9]+)-.*\.sql")

        # rks_manager/rksmanager/database.py
        this_file = pathlib.Path(__file__)
        # rks_manager/rksmanager/
        this_file_dir = this_file.parent
        # rks_manager/
        base_project_dir = this_file_dir.parent
        # rks_manager/migrations/
        migrations_dir = base_project_dir / "migrations"

        try:
            # Without an explicit begin transaction, python's sqlite3 driver
            # will autocommit DDL statements
            self._connection.execute("begin transaction")
            for migration_file in migrations_dir.iterdir():
                if not migration_file.is_file():
                    continue
                match = migration_name_regex.fullmatch(migration_file.name)
                if not match:
                    continue
                script_version = int(match.group(1))
                current_version = self.get_schema_version()
                if script_version <= current_version:
                    continue
                # Each script version should be exactly 1 greater than the
                # previous, and none of them should be higher than what the
                # software expects
                too_high = (script_version > self.expected_schema_version
                            or script_version != current_version + 1)
                if too_high:
                    raise Exception(
                        "Migration script {} version higher than expected."
                        .format(str(migration_file.resolve()))
                    )
                script = migration_file.read_text()
                # We can't use executescript because it forces a commit, and we
                # don't want to commit anything until all the migrations have
                # run
                for statement in script.split(";"):
                    self._connection.execute(statement)
                # HACK: Normally we shouldn't use string formatting to pass
                # parameters to the database, because that's how you get
                # injection attacks. Pragma statements don't allow us to use
                # proper parameterization though, so we don't have a choice. We
                # at least specify the value should be an integer in the format
                # string.
                self._connection.execute("pragma user_version = {:d};"
                                         .format(script_version))
            if self.get_schema_version() < self.expected_schema_version:
                raise Exception("Schema version lower than expected after"
                                " running migration scripts.")
        except Exception:
            self._connection.rollback()
            raise

        self._connection.commit()
