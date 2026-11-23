"""Opt-in, real replica-set tests. Creates/drops ONLY run-specific collections.

Run with MONGODB_INTEGRATION=1 and private MONGODB_URI in the environment.
The application database is never cleared and no provider calls are made.
"""
import os
from pathlib import Path
import sys
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from backend.db.mongo import Repository, get_database, require_replica_set, transaction


@unittest.skipUnless(os.environ.get('MONGODB_INTEGRATION') == '1', 'Requires explicit opt-in and a real rs0 replica set')
class ReplicaIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from dotenv import load_dotenv
        load_dotenv(ROOT / 'routing' / '.env')
        cls.database = get_database()
        require_replica_set(cls.database)
        cls.prefix = 'qa_' + uuid.uuid4().hex + '__'

    def setUp(self):
        outer = self
        class ScopedDatabase:
            client = outer.database.client
            def __getitem__(self, name):
                return outer.database[outer.prefix + name]
        self.scoped = ScopedDatabase()
        # Create outside transactions; older MongoDB versions disallow lazy DDL
        # while a transactional insert is running.
        for name in ('customers', '_counters'):
            if self.prefix + name not in self.database.list_collection_names():
                self.database.create_collection(self.prefix + name)
        self.repository = Repository('customers', self.scoped)

    def tearDown(self):
        for name in self.database.list_collection_names():
            if name.startswith(self.prefix):
                self.database.drop_collection(name)

    def test_transaction_rollback_keeps_counter_and_record_atomic(self):
        def write(session):
            self.repository.insert({'tenant_id':'isolated','wa_id':'123'}, session)
            raise ValueError('Intentional rollback')
        with self.assertRaises(ValueError):
            transaction(write, self.scoped)
        self.assertEqual(self.scoped['customers'].count_documents({}), 0)
        self.assertEqual(self.scoped['_counters'].count_documents({}), 0)

    def test_concurrent_ids_are_distinct(self):
        with ThreadPoolExecutor(max_workers=4) as executor:
            rows = list(executor.map(lambda index: self.repository.insert(
                {'tenant_id':'isolated','wa_id':str(index)}), range(12)))
        self.assertEqual(len({row['id'] for row in rows}), 12)


if __name__ == '__main__':
    unittest.main()
