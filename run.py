#!/usr/bin/env python3
import sys

import rksmanager.database


# TODO: This file should just start the UI, which will handle opening/creating
# the database and schema version checking/updating
if len(sys.argv) < 2:
    print("Usage: run.py <database filename>")
    sys.exit()
db = rksmanager.database.Database(sys.argv[1])
schema_version = db.get_schema_version()
if schema_version < db.expected_schema_version:
    print("Applying database schema migrations")
    db.apply_migrations()
elif schema_version > db.expected_schema_version:
    print("Database was created with a newer version of this program, please"
          " upgrade")
    sys.exit()
print("Database is at schema version {}".format(db.get_schema_version()))
