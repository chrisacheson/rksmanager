"""ORM-style database model classes."""


class DbObject:
    def __init__(self, database, id=None):
        self._db = database
        self._new_values = dict()
        self._db_values = dict()
        self._id = id
        for column in self.columns:
            setattr(self, column, DbObjectAttribute(column))
        for collection in self.collections:
            setattr(self, collection.name, collection)
        for join in self.joins:
            for column in join.columns:
                if isinstance(column, str):
                    setattr(self, column, JoinedAttribute(column))
                else:
                    column, alias = column
                    setattr(self, alias, JoinedAttribute(alias))
        if id:
            self._load()

    @property
    def id(self):
        return self._id

    def db_changed(self):
        """
        Reload eager-loaded data and unload lazy-loaded data. Should be called
        whenever the database is changed by external code in a way that would
        affect this object.

        """
        if self._id:
            self._load()
            for collection in self.collections:
                self._db_values.pop(collection.name, None)

    def save(self):
        # Only save changed column values
        column_values = {k: self._new_values[k]
                         for k
                         in self._new_values.keys() & set(self.columns)
                         if self._new_values[k] != self._db_values.get(k)}
        is_new = not self._id
        with self._db._connection:
            if is_new:
                self._id = self._db._dynamic_insert(
                    table=self.table,
                    column_values=column_values,
                )
            else:
                self._db._dynamic_update(table=self.table,
                                         column_values=column_values,
                                         where_conditions={"id": self._id})
            # Update the db values dict without making another query
            self._db_values.update(column_values)
            for collection in self.collections:
                if collection.name not in self._new_values:
                    # This collection was never touched, skip it
                    continue
                else:
                    new_items = self._new_values[collection.name]
                if is_new:
                    old_items = tuple()
                elif collection.name not in self._db_values:
                    old_items = self._load_collection(collection)
                else:
                    # Assume the previously loaded list is still accurate. If
                    # it isn't, db_changed() should be called before saving.
                    old_items = self._db_values[collection.name]
                self._db._update_collection(
                    table=collection.table,
                    filter_column=collection.foreign_key,
                    update_column=collection.columns,
                    filter_value=self._id,
                    old_items=old_items,
                    new_items=new_items,
                )
                if collection.primary_column and new_items:
                    # If the collection has a primary flag column and still has
                    # items, set the first item to primary
                    if old_items:
                        # But first clear any previous primary flags
                        self._db._dynamic_update(
                            table=collection.table,
                            column_values={collection.primary_column: None},
                            where_conditions={
                                collection.foreign_key: self._id
                            },
                        )
                    # Currently the only collection that uses a primary flag
                    # just has single-value items. We can't assume that will
                    # remain the case though, so handle tuple items as well.
                    first_item = new_items[0]
                    if len(collection.columns) == 1:
                        first_item = (first_item,)
                    where_conditions = dict(zip(collection.columns,
                                                first_item))
                    where_conditions[collection.foreign_key] = self._id
                    self._db._dynamic_update(
                        table=collection.table,
                        column_values={collection.primary_column: True},
                        where_conditions=where_conditions,
                    )
                # Make a copy of new_items for change tracking
                self._db_values[collection.name] = new_items.copy()

    def _load(self):
        condition = "{table}.id = :id".format(table=self.table)
        with self._db._connection:
            row = self.__class__._dynamic_select(database=self._db,
                                                 condition=condition,
                                                 parameters={"id": self.id})[0]
            for key in row.keys():
                if key != "id":
                    self._db_values[key] = row[key]

    def _load_collection(self, collection):
        value = self._db._get_collection(
            table=collection.table,
            filter_column=collection.foreign_key,
            get_column=collection.columns,
            filter_value=self._id,
            order_by_column=collection.primary_column,
            order_ascending=False,  # No effect if primary_column is None
        )
        self._db_values[collection.name] = value
        return value

    @classmethod
    def _dynamic_select(cls, database, condition=None, parameters=None):
        column_fmt = "{table}.{column} as {alias}"
        column_strings = [column_fmt.format(table=cls.table,
                                            column=column,
                                            alias=column)
                          for column in cls.columns]
        for join in cls.joins:
            for column, alias in zip(join.columns, join.column_aliases):
                column_strings.append(column_fmt.format(table=join.table,
                                                        column=column,
                                                        alias=alias))
        columns_sql = ",".join(column_strings)

        join_fmt = (
            """
            {join_type} join {join_table}
            on {join_table}.{foreign_key} = {main_table}.id
            {join_condition}
            """
        )
        join_strings = list()
        for join in cls.joins:
            if join.condition:
                condition_sql = " and {}".format(join.condition)
            else:
                condition_sql = ""
            join_strings.append(join_fmt.format(join_type=join.join_type,
                                                join_table=join.table,
                                                foreign_key=join.foreign_key,
                                                main_table=cls.table,
                                                join_condition=condition_sql))
        joins_sql = "".join(join_strings)

        if condition:
            where_sql = "where {}".format(condition)
        else:
            where_sql = ""

        query = (
            """
            select {table}.id as id
                , {columns}
            from {table}
            {joins}
            {where}
            """
        ).format(table=cls.table, columns=columns_sql, joins=joins_sql,
                 where=where_sql)
        return database._connection.execute(query, parameters).fetchall()

    @classmethod
    def load_many(cls, database):
        with database._connection:
            rows = cls._dynamic_select(database)
            db_objects = list()
            for row in rows:
                db_object = cls(database=database)
                for key in row.keys():
                    if key == "id":
                        db_object._id = row[key]
                    else:
                        db_object._db_values[key] = row[key]
                db_objects.append(db_object)
            return db_objects


class DbObjectAttribute:
    def __init__(self, name):
        self.name = name

    def __get__(self, obj, objtype):
        return obj._new_values.get(self.name, obj._db_values.get(self.name))

    def __set__(self, obj, value):
        obj._new_values[self.name] = value


class Collection(DbObjectAttribute):
    def __init__(self, name, table, columns, foreign_key, primary_column=None):
        super().__init__(name)
        self.table = table
        if isinstance(columns, str):
            columns = (columns,)
        self.columns = columns
        self.foreign_key = foreign_key
        self.primary_column = primary_column

    def __get__(self, obj, objtype):
        if self.name not in obj._new_values:
            if obj.id:
                with obj._db._connection:
                    # Make a copy of the list so that external code can't
                    # modify the original and screw up our change tracking
                    value = obj._load_collection(self)
                    obj._new_values[self.name] = value.copy()
            else:
                obj._new_values[self.name] = list()
        return obj._new_values[self.name]


class JoinedAttribute(DbObjectAttribute):
    def __get__(self, obj, objtype):
        return obj._db_values.get(self.name)

    def __set__(self, obj, value):
        raise AttributeError("can't set attribute")


class Join:
    def __init__(self, table, columns, foreign_key, join_type="left",
                 condition=None):
        self.table = table
        if isinstance(columns, str):
            columns = (columns,)
        self.columns = columns
        self.foreign_key = foreign_key
        self.join_type = join_type
        self.condition = condition

    @property
    def column_aliases(self):
        """
        A list of column aliases (or column names where no alias is specified)
        associated with this join. Can be used with zip() to get a list of
        (column, alias) tuples.

        """
        aliases = list()
        for column in self.columns:
            if isinstance(column, str):
                alias = column
            else:
                column, alias = column
            aliases.append(alias)
        return aliases


class Person(DbObject):
    table = "people"
    columns = (
        "first_name_or_nickname",
        "pronouns",
        "notes",
    )
    collections = (
        Collection("aliases",
                   table="people_aliases",
                   columns="alias",
                   foreign_key="person_id"),
        Collection("email_addresses",
                   table="people_email_addresses",
                   columns="email_address",
                   foreign_key="person_id",
                   primary_column="primary_email"),
        Collection("other_contact_info",
                   table="people_other_contact_info",
                   columns=("other_contact_info_type_id", "contact_info"),
                   foreign_key="person_id"),
    )
    joins = (
        Join(table="people_email_addresses",
             columns="email_address",
             foreign_key="person_id",
             condition="people_email_addresses.primary_email = 1"),
    )
