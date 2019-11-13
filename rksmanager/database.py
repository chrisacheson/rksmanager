"""
Database access module. Contains the main database handler class. All SQL
queries belong in this module.

"""
import sqlite3
import decimal
import datetime
import pathlib
import re
import itertools


class Database:
    """Passes data to and from the database."""
    sqlite_application_id = 0x4ab3c62d
    expected_sqlite_user_version = 1

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

        connection = sqlite3.connect(
            db_filename,
            detect_types=sqlite3.PARSE_DECLTYPES,
        )
        self._connection = connection
        connection.row_factory = sqlite3.Row
        # Enable foreign key enforcement
        connection.execute("pragma foreign_keys = on;")

        # Check if this is a newly-created database
        if self.get_sqlite_schema_version() == 0:
            # Mark database as ours
            connection.execute("pragma application_id = {:d};"
                               .format(self.sqlite_application_id))
            self.apply_migrations()

        # Make sure this is actually our database
        app_id = connection.execute("pragma application_id;").fetchone()[0]
        if app_id != self.sqlite_application_id:
            self.close()
            raise Exception("Not an RKS Manager database")

    def close(self):
        """
        Close the database connection. No other methods of this Database object
        should be called after calling close().

        """
        self._connection.close()
        del self._connection

    def get_sqlite_user_version(self):
        """
        Retrieve the current user_version value from the database. We increment
        this ourselves whenever a new schema migration is applied.

        Returns:
            The user_version value as an integer.

        """
        return self._connection.execute("pragma user_version;").fetchone()[0]

    def get_sqlite_schema_version(self):
        """
        Retrieve the current schema_version value from the database. Newly
        created SQLite databases have a schema_version of 0, and the value is
        incremented each time the schema is modified.

        Returns:
            The schema_version value as an integer.

        """
        return self._connection.execute("pragma schema_version;").fetchone()[0]

    def apply_migrations(self):
        """
        Check the current database user_version and run any migration scripts
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

        expected_version = self.expected_sqlite_user_version

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
                current_version = self.get_sqlite_user_version()
                if script_version <= current_version:
                    continue
                # Each script version should be exactly 1 greater than the
                # previous, and none of them should be higher than what the
                # software expects
                too_high = (script_version > expected_version
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
            if self.get_sqlite_user_version() < expected_version:
                raise Exception("SQLite user_version lower than expected after"
                                " running migration scripts.")
        except Exception:
            self._connection.rollback()
            raise

        self._connection.commit()

    def save_person(self, data, person_id=None):
        """
        Insert a new person into the database or update the specified person.

        Args:
            data: A dictionary of values to be inserted/updated.
            person_id: Optional ID of the person to update. If unspecified, a
                new person will be inserted.

        Returns:
            The id of the person as an integer.

        """
        with self._connection:
            if person_id:
                data["id"] = person_id
                self._connection.execute(
                    """
                    update people
                    set first_name_or_nickname = :first_name_or_nickname
                        , pronouns = :pronouns
                        , notes = :notes
                    where id = :id
                    """,
                    data,
                )
                old_aliases = self._get_collection(table="people_aliases",
                                                   filter_column="person_id",
                                                   get_column="alias",
                                                   filter_value=person_id)
                old_email_addresses = self._get_collection(
                    table="people_email_addresses",
                    filter_column="person_id",
                    get_column="email_address",
                    filter_value=person_id,
                    order_by_column="primary_email",
                    order_ascending=False,
                )
            else:
                person_id = self._connection.execute(
                    """
                    insert into people (
                        first_name_or_nickname
                        , pronouns
                        , notes
                    ) values (
                        :first_name_or_nickname
                        , :pronouns
                        , :notes
                    )
                    """,
                    data,
                ).lastrowid
                old_aliases = ()
                old_email_addresses = ()

            new_aliases = data["aliases"]
            self._update_collection(table="people_aliases",
                                    filter_column="person_id",
                                    update_column="alias",
                                    filter_value=person_id,
                                    old_items=old_aliases,
                                    new_items=new_aliases)
            new_email_addresses = data["email_addresses"]
            self._update_collection(table="people_email_addresses",
                                    filter_column="person_id",
                                    update_column="email_address",
                                    filter_value=person_id,
                                    old_items=old_email_addresses,
                                    new_items=new_email_addresses)
            if new_email_addresses:
                # If the person has any email addresses, set the first one as
                # primary
                if old_email_addresses:
                    # But first clear any primary flags on email addresses that
                    # they had before
                    self._connection.execute(
                        """
                        update people_email_addresses
                        set primary_email = null
                        where person_id = ?
                        """,
                        (person_id,),
                    )
                self._connection.execute(
                    """
                    update people_email_addresses
                    set primary_email = 1
                    where person_id = :id
                    and email_address = :email_address
                    """,
                    {"id": person_id, "email_address": new_email_addresses[0]},
                )
            return person_id

    # Update the items of a simple collection associated with a record, such as
    # the aliases associated with a person.
    #
    # This function uses dynamic queries. DO NOT pass any unsanitized data to
    # it for the table, filter_column, or update_column arguments.
    #
    # Args:
    #   table: Name of the table to update, such as people_aliases.
    #   filter_column: Column to filter by, such as person_id.
    #   update_column: Column to update, such as alias.
    #   filter_value: The value to filter for, such as the ID of a person.
    #   old_items: A sequence consisting of the items currently in the
    #       collection.
    #   new_items: A sequence consisting of the items that will be added to or
    #       kept in the collection.
    def _update_collection(self, table, filter_column, update_column,
                           filter_value, old_items, new_items):
                old_items = set(old_items)
                new_items = set(new_items)
                remove_items = old_items - new_items
                add_items = new_items - old_items
                for old, new in itertools.zip_longest(remove_items, add_items):
                    if old and new:
                        # We have both new and old items left, so swap an old
                        # one for a new one
                        query = (
                            """
                            update {table}
                            set {update_column} = :new
                            where {filter_column} = :filter_value
                            and {update_column} = :old
                            """
                        ).format(table=table,
                                 filter_column=filter_column,
                                 update_column=update_column)
                        parameters = {"old": old, "new": new,
                                      "filter_value": filter_value}
                    elif old:
                        # We've run out of new items and only have old ones
                        # left, so delete this one
                        query = (
                            """
                            delete from {table}
                            where {filter_column} = :filter_value
                            and {update_column} = :old
                            """
                        ).format(table=table,
                                 filter_column=filter_column,
                                 update_column=update_column)
                        parameters = {"old": old, "filter_value": filter_value}
                    elif new:
                        # We've run out of old items and only have new ones
                        # left, so insert this one
                        query = (
                            """
                            insert into {table} (
                                {filter_column}
                                , {update_column}
                            ) values (
                                :filter_value
                                , :new
                            )
                            """
                        ).format(table=table,
                                 filter_column=filter_column,
                                 update_column=update_column)
                        parameters = {"new": new, "filter_value": filter_value}

                    self._connection.execute(query, parameters)

    # Get the items of a simple collection associated with a record, such as
    # the aliases associated with a person.
    #
    # This function uses dynamic queries. DO NOT pass any unsanitized data to
    # it for the table, filter_column, get_column, or order_by_column
    # arguments.
    #
    # Args:
    #   table: Name of the table to query, such as people_aliases.
    #   filter_column: Column to filter by, such as person_id.
    #   get_column: Column to get data from, such as alias.
    #   filter_value: The value to filter for, such as the ID of a person.
    #   order_by_column: Optional column to order results by.
    #   order_ascending: Optional direction to order results by. Defaults to
    #       True. Has no effect if order_by_column is unspecified.
    #
    # Returns:
    #   A list containing the collection's items.
    def _get_collection(self, table, filter_column, get_column, filter_value,
                        order_by_column=None, order_ascending=True):
        if order_by_column:
            order_by_sql = "order by {order_by_column} {direction}".format(
                order_by_column=order_by_column,
                direction="asc" if order_ascending else "desc",
            )
        else:
            order_by_sql = ""
        query = (
            """
            select {get_column}
            from {table}
            where {filter_column} = ?
            {order_by_sql}
            """
        ).format(table=table,
                 filter_column=filter_column,
                 get_column=get_column,
                 order_by_sql=order_by_sql)
        rows = self._connection.execute(query, (filter_value,)).fetchall()
        return [row[get_column] for row in rows]

    def get_person(self, person_id):
        """
        Retrieve the specified person from the database.

        Args:
            person_id: The ID of the person.

        Returns:
            The a dictionary of the person's data.

        """
        with self._connection:
            row = self._connection.execute(
                """
                select id
                    , first_name_or_nickname
                    , pronouns
                    , notes
                from people
                where id = ?
                """,
                (person_id,),
            ).fetchone()
            person = {}
            for key in row.keys():
                person[key] = row[key]
            person["aliases"] = self._get_collection(table="people_aliases",
                                                     filter_column="person_id",
                                                     get_column="alias",
                                                     filter_value=person_id)
            person["email_addresses"] = self._get_collection(
                table="people_email_addresses",
                filter_column="person_id",
                get_column="email_address",
                filter_value=person_id,
                order_by_column="primary_email",
                order_ascending=False,
            )
            return person

    def get_people(self):
        """
        Get all people from the database.

        Returns:
            A list of sqlite3.Row objects.

        """
        with self._connection:
            return self._connection.execute(
                """
                select people.id as id
                    , first_name_or_nickname
                    , email_address
                    , pronouns
                    , notes
                from people
                left join people_email_addresses
                on people.id = people_email_addresses.person_id
                and primary_email = 1
                """
            ).fetchall()

    def get_other_contact_info_types(self):
        """
        Get all "other" contact info types from the database.

        Returns:
            A list of sqlite3.Row objects.

        """
        with self._connection:
            return self._connection.execute(
                """
                select t.id as id
                    , name
                    , count(i.id) as usage_count
                from other_contact_info_types t
                left join people_other_contact_info i
                on t.id = i.other_contact_info_type_id
                group by t.id
                """
            ).fetchall()

    def create_other_contact_info_type(self, name):
        """
        Create a new "other" contact info type with the specified name.

        Args:
            name: Name of the new contact info type.

        Returns:
            The id of the new contact info type as an integer.

        """
        with self._connection:
            return self._connection.execute(
                """
                insert into other_contact_info_types (
                    name
                ) values (
                    ?
                )
                """,
                (name,),
            ).lastrowid

    def count_email_addresses(self):
        """
        Get the number of email address records in the database.

        Returns:
            The number of email addresses as an integer.

        """
        with self._connection:
            return self._connection.execute(
                """
                select count(*)
                from people_email_addresses
                """
            ).fetchone()[0]

    def count_phone_numbers(self):
        """
        Get the number of phone number records in the database.

        Returns:
            The number of phone numbers as an integer.

        """
        with self._connection:
            return self._connection.execute(
                """
                select count(*)
                from people_phone_numbers
                """
            ).fetchone()[0]
