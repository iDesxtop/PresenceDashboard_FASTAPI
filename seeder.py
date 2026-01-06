import os
import re
import ast
from datetime import datetime
from bson import ObjectId
from config.configrations import db

# Helper for ISODate
def ISODate(date_string):
    # Handle 'Z' at the end for ISO format
    if date_string.endswith('Z'):
        date_string = date_string[:-1] + '+00:00'
    return datetime.fromisoformat(date_string)

def parse_js_file(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        # Remove comments (single line //)
        content = re.sub(r'//.*', '', content)
        
        # Regex to find collection name and the list
        # Pattern: db.CollectionName.insertMany([ ... ])
        match = re.search(r'db\.(\w+)\.insertMany\(\s*(\[.*\])\s*\)', content, re.DOTALL)
        
        if match:
            collection_name = match.group(1)
            data_str = match.group(2)
        else:
             # Try insertOne
            match = re.search(r'db\.(\w+)\.insertOne\(\s*(\{.*\})\s*\)', content, re.DOTALL)
            if match:
                collection_name = match.group(1)
                data_str = match.group(2)
            else:
                print(f"Could not find matching pattern in {filepath}")
                return None, None

        # Eval context
        eval_context = {
            'ObjectId': ObjectId,
            'ISODate': ISODate,
            'true': True,
            'false': False,
            'null': None
        }
        
        # Eval the list or dict
        data = eval(data_str, eval_context)

        # Normalize to list
        if isinstance(data, dict):
            data = [data]
            
        return collection_name, data
    except Exception as e:
        print(f"Error parsing {filepath}: {e}")
        return None, None

def seed():
    benih_dir = os.path.join(os.path.dirname(__file__), 'Benih')
    if not os.path.exists(benih_dir):
        print(f"Directory {benih_dir} not found.")
        return

    files = [f for f in os.listdir(benih_dir) if f.endswith('.js')]
    files.sort() # Ensure deterministic order if needed

    print(f"Found seed files: {files}")
    
    for filename in files:
        filepath = os.path.join(benih_dir, filename)
        print(f"Processing {filename}...")
        collection_name, data = parse_js_file(filepath)
        
        if collection_name and data:
            collection = db[collection_name]
            
            try:
                # We want to be idempotent or just reset
                # Strategy: Delete documents that match the _id of the seed data
                ids = [d['_id'] for d in data if '_id' in d]
                if ids:
                    result_del = collection.delete_many({'_id': {'$in': ids}})
                    print(f"  Deleted {result_del.deleted_count} existing documents with matching IDs.")
                
                if data:
                    result = collection.insert_many(data)
                    print(f"  Inserted {len(result.inserted_ids)} documents into {collection_name}.")
                else:
                    print("  No data to insert.")
                    
            except Exception as e:
                print(f"  Error operating on {collection_name}: {e}")
        else:
            print(f"  Skipping {filename} (Parse failed or empty)")

if __name__ == '__main__':
    seed()
