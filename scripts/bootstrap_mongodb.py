"""Initialize an empty native MongoDB application without reading SQLite."""
import json
from pathlib import Path
import sys
import re
from datetime import datetime, timezone
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from backend.db.mongo import REGISTRY, get_database, initialize_indexes

def bootstrap(database):
    known = set(REGISTRY['tables']) | {'_app_meta','_counters'}
    collections = set(database.list_collection_names())
    unexpected = {name for name in collections if name not in known and not name.startswith('system.')}
    if unexpected:
        raise ValueError('Unexpected target collections; no data was removed')
    meta = database['_app_meta'].find_one({'_id':'schema'})
    if not meta:
        if any(database[name].find_one({}) for name in collections if not name.startswith('system.')):
            raise ValueError('Fresh start requires an empty target; existing records were not removed')
    initialize_indexes(database)
    database['_app_meta'].update_one({'_id':'schema'}, {'$setOnInsert': {
        'version':REGISTRY['version'],'mode':'fresh','created_at':datetime.now(timezone.utc),
    }}, upsert=True)
    hello = database.client.admin.command('hello')
    return {'database':database.name,'application_collections':len(REGISTRY['tables']),
            'data_imported':False,'replica_set':hello.get('setName'),
            'runtime_conversion_complete':False}

if __name__ == '__main__':
    load_dotenv(ROOT/'routing'/'.env')
    try:
        print(json.dumps(bootstrap(get_database())))
    except Exception as error:
        details = getattr(error,'details',{}) or {}
        reason = str(error) if isinstance(error,ValueError) else details.get('errmsg',type(error).__name__)
        reason = re.sub(r'(mongodb(?:\+srv)?://)[^\s/]+@',r'\1[REDACTED]@',reason,flags=re.I)
        print(json.dumps({'ok':False,'reason':reason,'code':details.get('code')}),file=sys.stderr)
        raise SystemExit(1)
