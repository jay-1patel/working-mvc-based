"""Native MongoDB infrastructure. No SQLite imports or SQL translation."""
from __future__ import annotations

import atexit
import copy
import json
import os
import re
import threading
from datetime import datetime, timezone
from pathlib import Path

from bson import BSON
from pymongo import MongoClient, ReturnDocument, ASCENDING
from pymongo.read_concern import ReadConcern
from pymongo.write_concern import WriteConcern

REGISTRY = json.loads(Path(__file__).with_name('mongo_schema.json').read_text(encoding='utf-8'))
_client = None
_client_pid = None
_lock = threading.Lock()


class MongoConfigurationError(RuntimeError):
    pass


def get_client():
    global _client, _client_pid
    with _lock:
        if _client is None or _client_pid != os.getpid():
            uri = os.environ.get('MONGODB_URI', '').strip()
            if not uri:
                raise MongoConfigurationError('MONGODB_URI is required')
            try:
                _client = MongoClient(uri, appname='send2digital-ai-chatbot',
                    serverSelectionTimeoutMS=5000, connectTimeoutMS=5000, socketTimeoutMS=15000,
                    maxPoolSize=50, retryWrites=True, retryReads=True, tz_aware=True,
                    w='majority')
                _client_pid = os.getpid()
            except Exception:
                raise MongoConfigurationError('Invalid MongoDB configuration; connection details withheld') from None
        return _client


def close_client():
    global _client, _client_pid
    with _lock:
        if _client is not None:
            _client.close()
        _client = None
        _client_pid = None


atexit.register(close_client)


def get_database():
    client = get_client()
    name = os.environ.get('MONGODB_DATABASE', '').strip()
    try:
        return client[name] if name else client.get_default_database()
    except Exception:
        raise MongoConfigurationError('Specify a database in MONGODB_URI or MONGODB_DATABASE') from None


def replica_set_name(database=None):
    database = get_database() if database is None else database
    return database.client.admin.command('hello').get('setName')


def require_replica_set(database, *, require_initialized=False):
    """Prefer rs0. Standalone is allowed for live hosts that are not yet replica-set enabled."""
    set_name = replica_set_name(database)
    if set_name not in (None, 'rs0'):
        raise MongoConfigurationError('MongoDB must be configured as replica set rs0 before migration/cutover')
    if require_initialized:
        state = database['_app_meta'].find_one({'_id': 'schema', 'mode': 'fresh'})
        if not state or state.get('version') != REGISTRY['version']:
            raise MongoConfigurationError('Initialize the fresh MongoDB schema before startup')
    return set_name


def transaction(callback, database=None):
    """Callbacks may retry: keep network sends, file writes and inference outside.

    On a replica set, runs with snapshot + majority. On standalone MongoDB,
    runs the same callback without a session (no multi-doc atomicity).
    """
    database = get_database() if database is None else database
    set_name = require_replica_set(database)
    if not set_name:
        return callback(None)
    with database.client.start_session() as session:
        return session.with_transaction(lambda active: callback(active),
            read_concern=ReadConcern('snapshot'), write_concern=WriteConcern('majority'))


def schema(table):
    if table not in REGISTRY['tables']:
        raise ValueError('Unknown collection')
    return REGISTRY['tables'][table]


def encode_row(table, row):
    """Convert only explicitly registered fields. Never guess from data values."""
    out = dict(row)
    for column in schema(table)['columns']:
        key, kind = column['name'], column['kind']
        value = out.get(key)
        if value is None or value == '':
            continue
        if kind == 'json' and isinstance(value, str):
            try:
                out[key] = json.loads(value)
            except (TypeError, ValueError):
                raise ValueError(f'Invalid JSON in {table}.{key}; value withheld') from None
        elif kind == 'datetime' and isinstance(value, str):
            try:
                date = datetime.fromisoformat(value.replace('Z', '+00:00'))
                out[key] = date.replace(tzinfo=date.tzinfo or timezone.utc).astimezone(timezone.utc)
            except ValueError:
                raise ValueError(f'Invalid timestamp in {table}.{key}; value withheld') from None
    # Only assigned phone numbers participate in the derived unique index.
    if table == 'tenants':
        number = out.get('mobile_number')
        if isinstance(number, str) and number and not number.upper().startswith('UNSET-'):
            out['_unique_mobile_number'] = number
    return out


def public_row(table, row):
    if row is None:
        return None
    out = {key: value for key, value in row.items() if not key.startswith('_')}
    for column in schema(table)['columns']:
        key = column['name']
        if isinstance(out.get(key), datetime):
            value = out[key]
            out[key] = value.replace(tzinfo=value.tzinfo or timezone.utc).astimezone(timezone.utc).isoformat()
    return out




def initialize_indexes(database):
    for table, definition in REGISTRY['tables'].items():
        if table not in database.list_collection_names():
            database.create_collection(table)
        collection = database[table]
        seen = set()
        for index in definition['indexes']:
            signature = json.dumps({'keys':index['keys'], 'options':{
                key:value for key,value in index['options'].items() if key != 'name'}}, sort_keys=True)
            if signature in seen:
                continue
            seen.add(signature)
            collection.create_index([tuple(key) for key in index['keys']], **index['options'])
        if any(c['name'] == 'tenant_id' for c in definition['columns']) and not any(
            list(index['key'].items()) == [('tenant_id', 1)] and not index.get('partialFilterExpression')
            for index in collection.list_indexes()
        ):
            collection.create_index([('tenant_id', 1)], name='mongo_tenant_lookup')


class Repository:
    """Native CRUD with API-safe IDs and optional shared transaction sessions."""
    def __init__(self, table, database=None):
        self.table = table
        schema(table)
        self.database = get_database() if database is None else database
        self.collection = self.database[table]

    def next_id(self, session=None):
        counter = self.database['_counters'].find_one_and_update(
            {'_id': self.table}, {'$inc': {'seq': 1}}, upsert=True,
            return_document=ReturnDocument.AFTER, session=session)
        return counter['seq']

    def insert(self, values, session=None):
        values = copy.deepcopy(values)
        primary = schema(self.table)['primary_key']
        columns = {column['name']: column for column in schema(self.table)['columns']}
        for name, column in columns.items():
            if name not in values and column.get('default') is not None:
                default = column['default']
                values[name] = datetime.now(timezone.utc) if default == {'factory':'utcnow'} else copy.deepcopy(default)
        if primary == ['id'] and columns['id']['integer'] and values.get('id') is None:
            values['id'] = self.next_id(session)
        document = encode_row(self.table, values)
        BSON.encode(document)  # Validate before writing anything.
        self.collection.insert_one(document, session=session)
        return public_row(self.table, document)

    def find(self, filters=None, *, sort=None, limit=100, offset=0, session=None):
        cursor = self.collection.find(filters or {}, session=session)
        if sort:
            cursor = cursor.sort(sort)
        return [public_row(self.table, row) for row in cursor.skip(max(0, offset)).limit(max(1, min(limit, 500)))]

    def find_one(self, filters, session=None):
        return public_row(self.table, self.collection.find_one(filters, session=session))

    def update(self, filters, changes, session=None):
        values = encode_row(self.table, changes)
        # Updating an ineligible phone number must also remove its unique key.
        update = {'$set': values}
        if self.table == 'tenants' and 'mobile_number' in changes and '_unique_mobile_number' not in values:
            update['$unset'] = {'_unique_mobile_number': ''}
        return self.collection.update_one(filters, update, session=session).modified_count

    def update_many(self, filters, changes, session=None):
        values = encode_row(self.table, changes)
        update = {'$set': values}
        if self.table == 'tenants' and 'mobile_number' in changes and '_unique_mobile_number' not in values:
            update['$unset'] = {'_unique_mobile_number': ''}
        return self.collection.update_many(filters or {}, update, session=session).modified_count

    def upsert(self, filters, values, session=None):
        """Insert or replace by primary/unique filters. Preserves existing `id` when present."""
        existing = self.collection.find_one(filters or {}, session=session)
        payload = copy.deepcopy(values)
        if existing is not None:
            primary = schema(self.table)['primary_key']
            if 'id' in existing and 'id' not in payload and primary == ['id']:
                payload['id'] = existing['id']
            # Keep counter-stable public ids; replace other fields.
            encoded = encode_row(self.table, payload)
            unset = {}
            if self.table == 'tenants' and 'mobile_number' in payload and '_unique_mobile_number' not in encoded:
                unset['_unique_mobile_number'] = ''
            update = {'$set': encoded}
            if unset:
                update['$unset'] = unset
            self.collection.update_one({'_id': existing['_id']}, update, session=session)
            merged = dict(existing)
            merged.update(encoded)
            for key in unset:
                merged.pop(key, None)
            return public_row(self.table, merged)
        return self.insert(payload, session=session)

    def delete_one(self, filters, session=None):
        return self.collection.delete_one(filters or {}, session=session).deleted_count

    def delete_many(self, filters, session=None):
        return self.collection.delete_many(filters or {}, session=session).deleted_count

    def count(self, filters=None, session=None):
        return self.collection.count_documents(filters or {}, session=session)

    def find_all(self, filters=None, *, sort=None, limit=None, offset=0, session=None):
        """Like find(), but allows uncapped reads for admin/export paths."""
        cursor = self.collection.find(filters or {}, session=session)
        if sort:
            cursor = cursor.sort(sort)
        if offset:
            cursor = cursor.skip(max(0, offset))
        if limit is not None:
            cursor = cursor.limit(max(0, limit))
        return [public_row(self.table, row) for row in cursor]

    def inc(self, filters, field, amount=1, session=None, extra=None):
        update = {'$inc': {field: amount}}
        if extra:
            update['$set'] = encode_row(self.table, extra)
        return self.collection.update_one(filters, update, session=session).modified_count
