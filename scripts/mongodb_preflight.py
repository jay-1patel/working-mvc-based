"""Read-only native MongoDB diagnostics. Does not read the old database."""
import json
import sys
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from backend.db.mongo import REGISTRY, get_database

def main():
    load_dotenv(ROOT/'routing'/'.env')
    try:
        database = get_database()
        database.client.admin.command('ping')
        hello = database.client.admin.command('hello')
        existing = set(database.list_collection_names())
        counts = {name:database[name].count_documents({}) for name in REGISTRY['tables'] if name in existing}
        print(json.dumps({'connected':True,'database':database.name,
            'replica_set':hello.get('setName'),'application_collections':len(counts),
            'application_records':sum(counts.values()),'admin_accounts':counts.get('admins',0)}))
        return 0
    except Exception as error:
        print(json.dumps({'connected':False,'error_type':type(error).__name__}))
        return 1

if __name__ == '__main__':
    raise SystemExit(main())
