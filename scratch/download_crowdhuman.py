import os
import sys
import time
import requests
import zipfile
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
CROWDHUMAN_RAW_DIR = BASE_DIR / "data" / "training" / "raw" / "crowdhuman"
CROWDHUMAN_RAW_DIR.mkdir(parents=True, exist_ok=True)
IMG_DIR = CROWDHUMAN_RAW_DIR / "images"
IMG_DIR.mkdir(parents=True, exist_ok=True)

ANN_PATH = CROWDHUMAN_RAW_DIR / "annotation_val.odgt"
ZIP_PATH = CROWDHUMAN_RAW_DIR / "CrowdHuman_val.zip"

def download_file(url, target_path):
    print(f"[*] Downloading {url} -> {target_path}")
    r = requests.get(url, stream=True)
    r.raise_for_status()
    total = int(r.headers.get('content-length', 0))
    downloaded = 0
    t0 = time.time()
    
    with open(target_path, 'wb') as f:
        for chunk in r.iter_content(chunk_size=1024*1024):
            if chunk:
                f.write(chunk)
                downloaded += len(chunk)
                done = int(50 * downloaded / max(1, total))
                speed = downloaded / (1024*1024 * max(0.1, time.time() - t0))
                sys.stdout.write(f"\r[{'=' * done}{' ' * (50-done)}] {downloaded//(1024*1024)}MB / {total//(1024*1024)}MB ({speed:.1f} MB/s)")
                sys.stdout.flush()
    print("\n[OK] Download complete.")

def main():
    # 1. Download annotation file if missing
    if not ANN_PATH.exists() or ANN_PATH.stat().st_size == 0:
        url_ann = "https://huggingface.co/datasets/Funtion/CrowdHuman/resolve/main/annotation_val.odgt"
        download_file(url_ann, ANN_PATH)
    else:
        print(f"[OK] Annotations already present at {ANN_PATH} ({ANN_PATH.stat().st_size//(1024*1024)} MB)")
        
    # 2. Download CrowdHuman_val.zip if images are missing
    existing = list(IMG_DIR.glob("*.jpg"))
    if len(existing) < 500:
        if not ZIP_PATH.exists() or ZIP_PATH.stat().st_size < 100 * 1024 * 1024:
            url_zip = "https://huggingface.co/datasets/Funtion/CrowdHuman/resolve/main/CrowdHuman_val.zip"
            download_file(url_zip, ZIP_PATH)
        else:
            print(f"[OK] Zip file already present at {ZIP_PATH} ({ZIP_PATH.stat().st_size//(1024*1024)} MB)")
            
        print(f"[*] Extracting images from {ZIP_PATH} to {IMG_DIR}...")
        t0 = time.time()
        with zipfile.ZipFile(ZIP_PATH, 'r') as z:
            z.extractall(path=str(IMG_DIR))
        print(f"[OK] Extracted images in {time.time()-t0:.2f}s.")
    else:
        print(f"[OK] Found {len(existing)} existing images in {IMG_DIR}")

if __name__ == "__main__":
    main()
