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
        connection.row_factory = Row
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
                old_other_contact_info = self._get_collection(
                    table="people_other_contact_info",
                    filter_column="person_id",
                    get_column=("other_contact_info_type_id", "contact_info"),
                    filter_value=person_id,
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
                old_other_contact_info = ()

            self._update_collection(table="people_aliases",
                                    filter_column="person_id",
                                    update_column="alias",
                                    filter_value=person_id,
                                    old_items=old_aliases,
                                    new_items=data["aliases"])
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
            self._update_collection(
                table="people_other_contact_info",
                filter_column="person_id",
                update_column=("other_contact_info_type_id", "contact_info"),
                filter_value=person_id,
                old_items=old_other_contact_info,
                new_items=data["other_contact_info"])
            return person_id

    # Update the items of a simple collection associated with a record, such as
    # the aliases associated with a person.
    #
    # This function uses dynamic queries. DO NOT pass any unsanitized data to
    # it for the table, filter_column, or update_column arguments.
    #
    # Args:
    #   table: Name of the table to update, such as "people_aliases".
    #   filter_column: Column to filter by, such as "person_id".
    #   update_column: Column or tuple of columns to update, such as "alias" or
    #       ("other_contact_info_type_id","contact_info"). If multiple columns
    #       are specified, the each item in old_items and new_items should be a
    #       tuple of the appropriate size.
    #   filter_value: The value to filter for, such as the ID of a person.
    #   old_items: A sequence consisting of the items currently in the
    #       collection.
    #   new_items: A sequence consisting of the items that will be added to or
    #       kept in the collection.
    def _update_collection(self, table, filter_column, update_column,
                           filter_value, old_items, new_items):
        if isinstance(update_column, str):
            update_columns = (update_column,)
            new_tuples = [(new,) for new in new_items]
            old_tuples = [(old,) for old in old_items]
        else:
            update_columns = update_column
            new_tuples = new_items
            old_tuples = old_items
        old_tuples = set(old_tuples)
        new_tuples = set(new_tuples)
        remove_tuples = old_tuples - new_tuples
        add_tuples = new_tuples - old_tuples
        for old, new in itertools.zip_longest(remove_tuples, add_tuples):
            if old is not None and new is not None:
                # We have both new and old items left, so swap an old
                # one for a new one
                column_values = dict(zip(update_columns, new))
                where_conditions = dict(zip(update_columns, old))
                where_conditions[filter_column] = filter_value
                self._dynamic_update(table=table,
                                     column_values=column_values,
                                     where_conditions=where_conditions)
            elif old is not None:
                # We've run out of new items and only have old ones
                # left, so delete this one
                where_conditions = dict(zip(update_columns, old))
                where_conditions[filter_column] = filter_value
                self._dynamic_delete(table=table,
                                     where_conditions=where_conditions)
            elif new is not None:
                # We've run out of old items and only have new ones
                # left, so insert this one
                column_values = dict(zip(update_columns, new))
                column_values[filter_column] = filter_value
                self._dynamic_insert(table=table, column_values=column_values)

    # Get the items of a simple collection associated with a record, such as
    # the aliases associated with a person.
    #
    # This function uses dynamic queries. DO NOT pass any unsanitized data to
    # it for the table, filter_column, get_column, or order_by_column
    # arguments.
    #
    # Args:
    #   table: Name of the table to query, such as "people_aliases".
    #   filter_column: Column to filter by, such as "person_id".
    #   get_column: Column or tuple of columns to get data from, such
    #       as "alias" or ("other_contact_info_type_id","contact_info").
    #   filter_value: The value to filter for, such as the ID of a person.
    #   order_by_column: Optional column to order results by.
    #   order_ascending: Optional direction to order results by. Defaults to
    #       True. Has no effect if order_by_column is unspecified.
    #
    # Returns:
    #   A list containing the collection's items. If multiple columns were
    #   specified for the get_column argument, this will be a list of tuples.
    #   Otherwise it will be a list of single values.
    def _get_collection(self, table, filter_column, get_column, filter_value,
                        order_by_column=None, order_ascending=True):
        if isinstance(get_column, str):
            get_columns_sql = get_column
        else:
            get_columns_sql = ",".join(get_column)
        if order_by_column:
            order_by_sql = "order by {order_by_column} {direction}".format(
                order_by_column=order_by_column,
                direction="asc" if order_ascending else "desc",
            )
        else:
            order_by_sql = ""
        query = (
            """
            select {get_columns_sql}
            from {table}
            where {filter_column} = ?
            {order_by_sql}
            """
        ).format(table=table,
                 filter_column=filter_column,
                 get_columns_sql=get_columns_sql,
                 order_by_sql=order_by_sql)
        rows = self._connection.execute(query, (filter_value,)).fetchall()
        if rows and len(rows[0]) > 1:
            return [tuple(row) for row in rows]
        else:
            return [row[0] for row in rows]

    # Build and execute a dynamic SQL insert statement.
    #
    # DO NOT pass any unsanitized data for the table argument or any of the
    # column names in the column_values dictionary.
    #
    # Args:
    #   table: Name of the table to insert into.
    #   column_values: A dictionary of column names and corresponding values to
    #       insert.
    def _dynamic_insert(self, table, column_values):
        column_names = column_values.keys()
        column_names_sql = ",".join(column_names)
        insert_params = [":{}".format(col) for col in column_names]
        insert_params_sql = ",".join(insert_params)
        query = (
            """
            insert into {table} (
                {column_names_sql}
            ) values (
                {insert_params_sql}
            )
            """
        ).format(table=table,
                 column_names_sql=column_names_sql,
                 insert_params_sql=insert_params_sql)
        self._connection.execute(query, column_values)

    # Build and execute a dynamic SQL delete statement.
    #
    # DO NOT pass any unsanitized data for the table argument or any of the
    # column names in the where_conditions dictionary.
    #
    # Args:
    #   table: Name of the table to insert into.
    #   where_conditions: A dictionary of column names and corresponding values
    #       which must match in order for a row to be deleted.
    def _dynamic_delete(self, table, where_conditions):
        column_names = where_conditions.keys()
        comparisons = ["{c}=:{c}".format(c=c) for c in column_names]
        where_conditions_sql = " and ".join(comparisons)
        query = (
            """
            delete from {table}
            where {where_conditions_sql}
            """
        ).format(table=table,
                 where_conditions_sql=where_conditions_sql)
        self._connection.execute(query, where_conditions)

    # Build and execute a dynamic SQL update statement.
    #
    # DO NOT pass any unsanitized data for the table argument or any of the
    # column names in the column_values or where_conditions dictionaries.
    #
    # Args:
    #   table: Name of the table to insert into.
    #   column_values: A dictionary of column names and corresponding values to
    #       set.
    #   where_conditions: A dictionary of column names and corresponding values
    #       which must match in order for a row to be updated.
    def _dynamic_update(self, table, column_values, where_conditions):
        parameters = {}
        assignments = []
        for column_name, set_value in column_values.items():
            param = "{column_name}_set".format(column_name=column_name)
            parameters[param] = set_value
            assignments.append(
                "{column_name}=:{param}".format(column_name=column_name,
                                                param=param)
            )
        conditions = []
        for column_name, where_value in where_conditions.items():
            param = "{column_name}_where".format(column_name=column_name)
            parameters[param] = where_value
            conditions.append(
                "{column_name}=:{param}".format(column_name=column_name,
                                                param=param)
            )
        assignments_sql = ",".join(assignments)
        conditions_sql = " and ".join(conditions)
        query = (
            """
            update {table}
            set {assignments_sql}
            where {conditions_sql}
            """
        ).format(table=table,
                 assignments_sql=assignments_sql,
                 conditions_sql=conditions_sql)
        self._connection.execute(query, parameters)

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
            person["other_contact_info"] = self._get_collection(
                table="people_other_contact_info",
                filter_column="person_id",
                get_column=("other_contact_info_type_id", "contact_info"),
                filter_value=person_id,
            )
            return person

    def get_people(self):
        """
        Get all people from the database.

        Returns:
            A list of Row objects.

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
            A list of Row objects.

        """
        with self._connection:
            return self._connection.execute(
                """
                select id
                    , name
                from other_contact_info_types
                """
            ).fetchall()

    def get_other_contact_info_types_usage(self):
        """
        Get all "other" contact info types and the usage count for each type.

        Returns:
            A list of Row objects.

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

    def get_membership_types(self):
        """
        Get all membership types from the database.

        Returns:
            A list of Row objects.

        """
        with self._connection:
            return self._connection.execute(
                """
                select t.id as id
                    , name
                    , count(m.id) as active_count
                from membership_types t
                left join people_memberships m
                on t.id = m.membership_type_id
                and m.begin_date <= date('now')
                and (
                    date('now') <= m.end_date
                    or m.end_date is null
                    )
                group by t.id
                """
            ).fetchall()

    def create_membership_type(self, name):
        """
        Create a new membership type with the specified name.

        Args:
            name: Name of the new membership type.

        Returns:
            The id of the new membership type as an integer.

        """
        with self._connection:
            return self._connection.execute(
                """
                insert into membership_types (
                    name
                ) values (
                    ?
                )
                """,
                (name,),
            ).lastrowid

    def get_membership_type(self, membership_type_id):
        """
        Get the specified membership type from the database.

        Args:
            membership_type_id: The ID of the membership type.

        Returns:
            A Row object.

        """
        with self._connection:
            return self._connection.execute(
                """
                select id
                    , name
                from membership_types
                where id = ?
                """,
                (membership_type_id,),
            ).fetchone()

    def get_membership_type_pricing_options(self, membership_type_id):
        """
        Get all pricing options for the specified membership type from the
        database.

        Args:
            membership_type_id: The ID of the membership type.

        Returns:
            A list of Row objects.

        """
        with self._connection:
            return self._connection.execute(
                """
                select id
                    , length_months
                    , price
                from membership_type_pricing_options
                where membership_type_id = ?
                """,
                (membership_type_id,),
            ).fetchall()

    def get_membership_type_pricing_option(self, pricing_option_id):
        """
        Get the specified pricing option from the database.

        Args:
            pricing_option_id: The ID of the pricing option.

        Returns:
            A Row object.

        """
        with self._connection:
            return self._connection.execute(
                """
                select p.id as id
                    , membership_type_id
                    , t.name as membership_type_name
                    , length_months
                    , price
                from membership_type_pricing_options p
                inner join membership_types t
                on t.id = p.membership_type_id
                where p.id = ?
                """,
                (pricing_option_id,),
            ).fetchone()

    def save_membership_type_pricing_option(self, data,
                                            pricing_option_id=None):
        """
        Insert a new pricing option into the database or update the specified
        pricing option.

        Args:
            data: A dictionary of values to be inserted/updated.
            pricing_option_id: Optional ID of the pricing option to update. If
                unspecified, a new pricing option will be inserted.

        Returns:
            The id of the pricing option as an integer.

        """
        with self._connection:
            if pricing_option_id:
                data["id"] = pricing_option_id
                self._connection.execute(
                    """
                    update membership_type_pricing_options
                    set length_months = :length_months
                        , price = :price
                    where id = :id
                    """,
                    data,
                )
            else:
                pricing_option_id = self._connection.execute(
                    """
                    insert into membership_type_pricing_options (
                        membership_type_id
                        , length_months
                        , price
                    ) values (
                        :membership_type_id
                        , :length_months
                        , :price
                    )
                    """,
                    data,
                ).lastrowid
            return pricing_option_id

    def get_event_types(self):
        """
        Get all event types from the database.

        Returns:
            A list of Row objects.

        """
        with self._connection:
            return self._connection.execute(
                """
                select id
                    , name
                    , default_start_time
                    , default_duration_minutes
                from event_types
                """
            ).fetchall()

    def get_event_type(self, event_type_id):
        """
        Get the specified event type from the database.

        Args:
            event_type_id: The ID of the event type.

        Returns:
            A Row object.

        """
        with self._connection:
            return self._connection.execute(
                """
                select id
                    , name
                    , default_start_time
                    , default_duration_minutes
                from event_types
                where id = ?
                """,
                (event_type_id,),
            ).fetchone()

    def save_event_type(self, data, event_type_id=None):
        """
        Insert a new event type into the database or update the specified event
        type.

        Args:
            data: A dictionary of values to be inserted/updated.
            event_type_id: Optional ID of the event type to update. If
                unspecified, a new event type will be inserted.

        Returns:
            The id of the event type as an integer.

        """
        with self._connection:
            if event_type_id:
                data["id"] = event_type_id
                self._connection.execute(
                    """
                    update event_types
                    set name = :name
                        , default_start_time = :default_start_time
                        , default_duration_minutes = :default_duration_minutes
                    where id = :id
                    """,
                    data,
                )
            else:
                event_type_id = self._connection.execute(
                    """
                    insert into event_types (
                        name
                        , default_start_time
                        , default_duration_minutes
                    ) values (
                        :name
                        , :default_start_time
                        , :default_duration_minutes
                    )
                    """,
                    data,
                ).lastrowid
            return event_type_id


class Row(sqlite3.Row):
    """sqlite3.Row class with some extra methods."""
    def get(self, key, default=None):
        """
        Dictionary-like get() method.

        Args:
            key: The key corresponding to the desired value.
            default: Optional value to return if key doesn't exist. Defaults to
                None.

        Returns:
            The value corresponding to key if it exists, or the default value
                otherwise.

        """
        if key in self:
            return self[key]
        else:
            return default
