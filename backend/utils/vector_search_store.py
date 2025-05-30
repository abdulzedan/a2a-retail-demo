"""
vertex_search_store.py
~~~~~~~~~~~~~~~~~~~~~~
Thin helper around the Vertex AI *Search* (Discovery Engine) API.

Given the full `servingConfig` resource name for your Search-App data-store,
`search(query, top_k)` returns a list of flattened product dictionaries.

Requires:
    pip install --upgrade google-cloud-discoveryengine
Environment:
    GOOGLE_APPLICATION_CREDENTIALS  or  gcloud auth application-default login
"""

from __future__ import annotations
from typing import List, Dict, Any

from google.cloud import discoveryengine_v1beta as de


class VertexSearchStore:
    def __init__(self, *, serving_config: str) -> None:
        self.serving_config = serving_config
        self._client = de.SearchServiceClient()

    def search(self, query: str, *, top_k: int = 5) -> List[Dict]:
        """Hybrid (text + vector) search of the data-store."""
        req = de.SearchRequest(
            serving_config=self.serving_config,
            query=query,
            page_size=top_k,
        )
        resp = self._client.search(request=req)

        hits: List[Dict] = []
        for r in resp.results:
            doc = r.document
            
            # Start with basic info
            result = {
                "id": doc.id,
                "similarity_score": 1.0
            }
            
            # For proto-plus messages, we can use __dict__ or to_dict()
            try:
                # Try to convert using proto-plus's to_dict() method
                if hasattr(doc, '__class__') and hasattr(doc.__class__, 'to_dict'):
                    doc_dict = doc.__class__.to_dict(doc)
                    
                    # Extract struct_data if it exists
                    if 'struct_data' in doc_dict:
                        struct_data = doc_dict['struct_data']
                        # struct_data should be a dict with the actual data
                        if isinstance(struct_data, dict):
                            result.update(struct_data)
                    
                    # Also check for derived_struct_data
                    if 'derived_struct_data' in doc_dict:
                        derived_data = doc_dict['derived_struct_data']
                        if isinstance(derived_data, dict):
                            result.update(derived_data)
                            
                elif hasattr(doc, 'struct_data'):
                    # Direct access to struct_data
                    struct_data = doc.struct_data
                    
                    # If struct_data is a proto-plus MapComposite
                    if hasattr(struct_data, '__class__') and 'MapComposite' in str(type(struct_data)):
                        # Proto-plus MapComposite can be accessed like a dict
                        for key in struct_data:
                            value = struct_data[key]
                            result[key] = self._extract_proto_value(value)
                    
                    # If it's already a dict
                    elif isinstance(struct_data, dict):
                        result.update(struct_data)
                        
            except Exception as e:
                print(f"Warning: Could not parse document {doc.id}: {e}")
                # Try fallback method - direct attribute access
                try:
                    if hasattr(doc, 'struct_data') and doc.struct_data:
                        # Try to access as a dict-like object
                        for key in ['name', 'description', 'price', 'category', 'brand', 
                                   'stock_quantity', 'stock_status', 'sku', 'metadata']:
                            try:
                                if key in doc.struct_data:
                                    result[key] = self._extract_proto_value(doc.struct_data[key])
                            except:
                                pass
                except Exception as e2:
                    print(f"Fallback also failed: {e2}")
            
            hits.append(result)
        
        return hits
    
    def get_by_id(self, product_id: str) -> Optional[Dict]:
        """Get a product by exact ID match."""
        # Get many products and filter for exact match
        results = self.search(query="", top_k=200)
        
        for result in results:
            if result.get("id") == product_id:
                return result
        
        return None    
    def _extract_proto_value(self, value: Any) -> Any:
        """Extract a simple value from a proto-plus Value or any proto object."""
        if value is None:
            return None
        
        # If it's already a simple type, return it
        if isinstance(value, (str, int, float, bool, list)):
            return value
        
        # If it's a dict, return it
        if isinstance(value, dict):
            return value
        
        # Handle proto-plus Value types
        value_type = type(value).__name__
        
        if 'Value' in value_type:
            # Proto Value objects have different fields for different types
            if hasattr(value, 'string_value') and value.string_value:
                return value.string_value
            elif hasattr(value, 'number_value'):
                return value.number_value
            elif hasattr(value, 'bool_value') is not None:
                return value.bool_value
            elif hasattr(value, 'struct_value'):
                # Nested struct
                return self._extract_proto_struct(value.struct_value)
            elif hasattr(value, 'list_value'):
                # List of values
                return [self._extract_proto_value(v) for v in value.list_value.values]
        
        # Handle MapComposite (dict-like proto objects)
        if 'MapComposite' in value_type:
            result = {}
            try:
                for key in value:
                    result[key] = self._extract_proto_value(value[key])
                return result
            except:
                pass
        
        # Handle Struct objects
        if 'Struct' in value_type:
            return self._extract_proto_struct(value)
        
        # Last resort: convert to string
        return str(value)
    
    def _extract_proto_struct(self, struct: Any) -> Dict:
        """Extract a dict from a proto Struct object."""
        result = {}
        
        # Try different ways to access struct fields
        if hasattr(struct, 'fields'):
            # Standard protobuf Struct
            for key, value in struct.fields.items():
                result[key] = self._extract_proto_value(value)
        elif hasattr(struct, '__iter__'):
            # MapComposite or dict-like
            try:
                for key in struct:
                    result[key] = self._extract_proto_value(struct[key])
            except:
                pass
        
        return result