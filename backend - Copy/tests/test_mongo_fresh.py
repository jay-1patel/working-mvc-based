import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
import mongomock
from backend.db.mongo import REGISTRY, Repository, initialize_indexes
from scripts.bootstrap_mongodb import bootstrap

class FreshMongoTests(unittest.TestCase):
    def setUp(self):
        self.client=mongomock.MongoClient(tz_aware=True)
        self.database=self.client.test_fresh

    def test_all_collections_created_without_importing_data(self):
        with patch.object(self.client.admin,'command',return_value={'isWritablePrimary':True}):
            report=bootstrap(self.database)
        self.assertEqual(report['application_collections'], len(REGISTRY['tables']))
        self.assertFalse(report['data_imported'])
        self.assertEqual(set(REGISTRY['tables'])-set(self.database.list_collection_names()),set())
        self.assertEqual(sum(self.database[name].count_documents({}) for name in REGISTRY['tables']),0)

    def test_bootstrap_does_not_delete_unrelated_data(self):
        self.database.unrelated.insert_one({'keep':True})
        with self.assertRaises(ValueError):bootstrap(self.database)
        self.assertEqual(self.database.unrelated.count_documents({}),1)

    def test_native_defaults_ids_and_tenant_uniqueness(self):
        initialize_indexes(self.database)
        repo=Repository('customers',self.database)
        first=repo.insert({'tenant_id':'a','wa_id':'123'})
        second=repo.insert({'tenant_id':'b','wa_id':'123'})
        self.assertNotEqual(first['id'],second['id'])
        self.assertNotIn('_id',first)
        from pymongo.errors import DuplicateKeyError
        with self.assertRaises(DuplicateKeyError):repo.insert({'tenant_id':'a','wa_id':'123'})

if __name__=='__main__':unittest.main()
