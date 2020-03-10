import unittest

from tests.common import create_temp_db, populate_temp_db, delete_temp_db
from rksmanager.database.models import Person


class TestPersonModel(unittest.TestCase):
    def setUp(self):
        self.db, self.tempdir = create_temp_db()
        populate_temp_db(self.db)

    def tearDown(self):
        delete_temp_db(self.db, self.tempdir)

    def test_empty_person(self):
        person = Person(self.db)
        self.assertIsNone(person.first_name_or_nickname)
        self.assertIsNone(person.pronouns)
        self.assertIsNone(person.notes)
        self.assertEqual(len(person.aliases), 0)
        self.assertEqual(len(person.email_addresses), 0)
        self.assertEqual(len(person.other_contact_info), 0)

    def test_load_person(self):
        person = Person(self.db, id=1)
        self.assertEqual(person.first_name_or_nickname, "Test User 1")
        self.assertEqual(person.pronouns, "they/them")
        self.assertIsNone(person.notes)
        self.assertEqual(len(person.aliases), 2)
        self.assertEqual(len(person.email_addresses), 1)
        self.assertEqual(len(person.other_contact_info), 0)

    def test_create_person(self):
        name = "Newly Created Person"
        person = Person(self.db)
        person.first_name_or_nickname = name
        person.save()
        person_id = person.id
        del person

        person = Person(self.db, id=person_id)
        self.assertEqual(person.first_name_or_nickname, name)
        self.assertIsNone(person.pronouns)
        self.assertIsNone(person.notes)
        self.assertEqual(len(person.aliases), 0)
        self.assertEqual(len(person.email_addresses), 0)
        self.assertEqual(len(person.other_contact_info), 0)
