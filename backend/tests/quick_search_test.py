#!/usr/bin/env python3
"""
quick_test_search.py
~~~~~~~~~~~~~~~~~~~
Quick test to see what data structure Vertex AI Search is actually returning.
"""

import os
from dotenv import load_dotenv
from google.cloud import discoveryengine_v1beta as de
from google.protobuf.json_format import MessageToDict
import json

load_dotenv()

def test_search():
    serving_config = os.getenv("VERTEX_SEARCH_SERVING_CONFIG")
    if not serving_config:
        print("❌ Set VERTEX_SEARCH_SERVING_CONFIG in your .env file!")
        return
    
    print(f"📍 Config: {serving_config}")
    
    client = de.SearchServiceClient()
    req = de.SearchRequest(
        serving_config=serving_config,
        query="smart tv",
        page_size=1,
    )
    
    print("🔍 Searching for 'smart tv'...")
    
    try:
        resp = client.search(request=req)
        results = list(resp.results)
        
        if not results:
            print("❌ No results! Check if your data was imported correctly.")
            return
        
        print(f"✅ Found {len(results)} result(s)")
        
        # Get first document
        doc = results[0].document
        print(f"\n📄 Document ID: {doc.id}")
        
        # Convert entire document to JSON
        print("\n📦 Full document as JSON:")
        doc_json = MessageToDict(doc)
        print(json.dumps(doc_json, indent=2))
        
        # Show what keys are at the top level
        print(f"\n🔑 Top-level keys: {list(doc_json.keys())}")
        
        # If there's structData, show its structure
        if 'structData' in doc_json:
            print("\n📊 structData contents:")
            print(json.dumps(doc_json['structData'], indent=2))
            
            # Check if metadata is nested
            if 'metadata' in doc_json['structData']:
                print("\n📋 metadata contents:")
                print(json.dumps(doc_json['structData']['metadata'], indent=2))
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_search()