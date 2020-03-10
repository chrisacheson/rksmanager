import tempfile
import pathlib

import rksmanager.database


def create_temp_db():
    """
    Create a temporary database for tests to use.

    Returns:
        A tuple consisting of the database object and an instance of
        TemporaryDirectory where the database file is stored. Both should be
        passed to delete_temp_db() for cleanup after testing.

    """
    tempdir = tempfile.TemporaryDirectory(prefix="temp_testing_dir.")
    temp_db_path = pathlib.Path(tempdir.name) / "temp.rksm"
    db = rksmanager.database.Database(str(temp_db_path))
    return db, tempdir


def delete_temp_db(db, tempdir):
    """
    Close and delete the temporary database.

    Args:
        db: The database object.
        tempdir: The TemporaryDirectory where the database file is stored.

    """
    db.close()
    tempdir.cleanup()


def populate_temp_db(db):
    # TODO: These database methods will eventually be removed
    db.save_person({
        "first_name_or_nickname": "Test User 1",
        "aliases": ["Tester", "Teletha 'Tessa' Testarossa"],
        "email_addresses": ["test@example.com"],
        "other_contact_info": [],
        "pronouns": "they/them",
        "notes": None,
    })
    db.save_person({
        "first_name_or_nickname": "Test User 2",
        "aliases": [],
        "email_addresses": [],
        "other_contact_info": [],
        "pronouns": None,
        "notes": "Some notes about Test User 2",
    })
