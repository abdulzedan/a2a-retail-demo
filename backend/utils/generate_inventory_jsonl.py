# generate_inventory_jsonl.py
"""Generate a JSON‑Lines product catalogue **with embeddings** for Vertex AI Vector
Search and (optionally) upload to Cloud Storage.

✨ **What’s new in this revision**
---------------------------------
* Adds `--model` flag (default **text-embedding-005**) so you can pick any
  Vertex AI text‑embedding model that your project has access to (`gemini‑embedding‑001`,
  `text-embedding-gecko@latest`, …).
* Better validation: catches the common `gs:///…` triple‑slash typo *and* exits
  before calling Vertex if the path is bad.
* Clear guidance if the model/region isn’t enabled in your project.

---
Usage
-----
```bash
# Authenticate once per machine
 gcloud auth application-default login
 gcloud config set project <PROJECT_ID>

# Enable APIs (one‑off)
 gcloud services enable aiplatform.googleapis.com

# Generate 100 products using the default model (text‑embedding‑005) and upload
 python generate_inventory_jsonl.py \
        --count 100 \
        --outfile gs://inventory-bucket-demo/inventory.txt \
        --upload gcloud

# Use Gemini embeddings instead
 python generate_inventory_jsonl.py --count 200 --model gemini-embedding-001
```
"""
from __future__ import annotations

import argparse
import json
import os
import random
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List

import vertexai
from vertexai.preview.language_models import TextEmbeddingModel
# vertexai <= 0.0.17 didn’t ship preview.exceptions, so fall back gracefully
try:
    from vertexai.preview.exceptions import VertexAIError
except ImportError:  # older SDK
    class VertexAIError(Exception):
        """Placeholder – upgrade vertexai for richer error details."""
from google.api_core.exceptions import NotFound

# ---------------------------------------------------------------------------
# 1)  Random catalogue generator helpers (unchanged)
# ---------------------------------------------------------------------------
categories = {
    "electronics": [
        "Smartphone", "Tablet", "Laptop", "Smart TV", "Wireless Earbuds",
        "Bluetooth Speaker", "Gaming Console", "Smartwatch", "Drone", "Camera",
    ],
    "clothing": [
        "T‑Shirt", "Jeans", "Hoodie", "Jacket", "Sneakers", "Dress", "Sweater",
        "Shorts", "Socks", "Hat",
    ],
    "home": [
        "Coffee Maker", "Blender", "Vacuum Cleaner", "Air Purifier", "Toaster",
        "Microwave", "Lamp", "Desk Chair", "Curtains", "Rug",
    ],
    "sports": [
        "Yoga Mat", "Dumbbells", "Tennis Racket", "Football", "Basketball",
        "Running Shoes", "Cycling Helmet", "Swim Goggles", "Fitness Tracker",
        "Jump Rope",
    ],
}

brands = [
    "TechVision", "AudioMax", "EcoWear", "BrewMaster", "FitLife", "UrbanTrend",
    "HomeEase", "SportPro", "NextGen", "Zenith",
]
adjectives = [
    "Premium", "Deluxe", "Pro", "Lite", "Ultra", "Plus", "Max", "Eco", "Smart",
    "Compact",
]
descriptors = [
    "high‑performance", "energy‑efficient", "sleek design", "wireless", "portable",
    "eco‑friendly", "water‑resistant", "noise‑cancelling", "lightweight",
    "multi‑functional",
]

def random_product(idx: int) -> Dict[str, Any]:
    cat = random.choice(list(categories.keys()))
    base_name = random.choice(categories[cat])
    adj = random.choice(adjectives)
    name = f"{adj} {base_name}"
    brand = random.choice(brands)
    desc = f"{random.choice(descriptors).capitalize()} {base_name.lower()} by {brand}."
    price = round(random.uniform(10, 999), 2)
    qty = random.randint(0, 200)
    status = "In Stock" if qty > 0 else "Out of Stock"
    sku = f"{base_name[:2].upper()}-{random.randint(100,999)}-{idx:04d}"
    return {
        "id": f"prod_{idx:04d}",
        "name": name,
        "description": desc,
        "category": cat,
        "price": price,
        "stock_quantity": qty,
        "stock_status": status,
        "sku": sku,
        "brand": brand,
    }

# ---------------------------------------------------------------------------
# 2)  Embedding helpers – lazily loaded after vertexai.init()
# ---------------------------------------------------------------------------
_embed_model: TextEmbeddingModel | None = None


def init_vertex(model: str, project: str | None, location: str | None) -> None:
    """Initialise Vertex AI SDK and load chosen embedding model."""
    vertexai.init(project=project, location=location)
    global _embed_model
    try:
        _embed_model = TextEmbeddingModel.from_pretrained(model)
    except NotFound as nf:
        sys.exit(
            f"\n❌ Model '{model}' not found or not enabled for project '{project}'.\n"
            "Make sure (1) Vertex AI API is enabled, (2) the model is available "
            "in your region, and (3) your org has access.\n"
            "Common public options: text-embedding-005, text-embedding-gecko@latest, "
            "gemini-embedding-001."
        )


def embed(text: str) -> List[float]:
    if _embed_model is None:
        raise RuntimeError("Vertex AI not initialised – call init_vertex() first")
    return list(_embed_model.get_embeddings([text])[0].values)

# ---------------------------------------------------------------------------
# 3)  JSONL writer (unchanged)
# ---------------------------------------------------------------------------

def write_jsonl(products: List[Dict[str, Any]], dest: Path) -> None:
    with dest.open("w", encoding="utf-8") as fh:
        for p in products:
            vec = embed(
                f"{p['name']}. {p['description']} Brand: {p['brand']}. Category: {p['category']}"
            )
            fh.write(
                json.dumps({
                    "id": p["id"],
                    "embedding": vec,
                    "metadata": {k: v for k, v in p.items() if k != "id"},
                })
                + "\n"
            )
    print(f"Wrote {len(products)} products → {dest}")

# ---------------------------------------------------------------------------
# 4)  Upload helper (unchanged)
# ---------------------------------------------------------------------------

def run_upload(cli: str, src: Path, dest: str) -> None:
    if cli == "gsutil":
        cmd = ["gsutil", "cp", str(src), dest]
    elif cli == "gcloud":
        cmd = ["gcloud", "storage", "cp", str(src), dest]
    else:
        raise ValueError("--upload must be 'gsutil' or 'gcloud'")
    print("Uploading via:", " ".join(cmd))
    subprocess.run(cmd, check=True)
    src.unlink()
    print("Upload done →", dest)

# ---------------------------------------------------------------------------
# 5)  CLI entrypoint
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Generate + optionally upload a Vertex AI JSONL catalogue.")
    parser.add_argument("--count", type=int, default=100, help="Number of products to generate")
    parser.add_argument("--outfile", default="inventory.txt", help="Local path or gs://bucket/path")
    parser.add_argument("--model", default="text-embedding-005", help="Vertex embedding model name")
    parser.add_argument("--project", help="GCP project ID (overrides env var)")
    parser.add_argument("--location", default=os.getenv("GOOGLE_CLOUD_REGION", "us-central1"), help="GCP region")
    parser.add_argument("--upload", choices=["gsutil", "gcloud"], help="Upload to Cloud Storage after write")
    args = parser.parse_args()

    # Path sanity check
    if args.outfile.startswith("gs:///"):
        sys.exit("Error: 'gs:///' has three slashes – should be gs://bucket/path")

    # Vertex AI initialisation & model load
    try:
        init_vertex(model=args.model, project=args.project or os.getenv("GOOGLE_CLOUD_PROJECT"), location=args.location)
    except VertexAIError as e:
        sys.exit("Vertex AI auth failed – run 'gcloud auth application-default login' and check project.")

    # Generate + write
    prods = [random_product(i) for i in range(1, args.count + 1)]
    local_path = Path("temp_inventory.txt") if args.outfile.startswith("gs://") else Path(args.outfile)
    write_jsonl(prods, local_path)

    # Optional upload
    if args.outfile.startswith("gs://"):
        if args.upload:
            run_upload(args.upload, local_path, args.outfile)
        else:
            print("Local file saved; copy manually with gsutil/gcloud storage cp:", local_path, args.outfile)


if __name__ == "__main__":
    main()
