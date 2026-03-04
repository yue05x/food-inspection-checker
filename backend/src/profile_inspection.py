import time
import json
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from app import BASE_DIR, UPLOAD_DIR
from ocr_engine import get_ocr_engine
from pdf_reader import parse_pdf
from field_extractor import (
    extract_food_name,
    extract_gb_standards,
    extract_gb_standards_with_title,
    extract_inspection_items,
    extract_production_date,
)
from gb_verifier import verify_gb_standards
# Try importing ragflow stuff, handle if missing/not configured
try:
    from ragflow_client import get_ragflow_client
    from ragflow_verifier import verify_inspection_compliance
except ImportError:
    print("Warning: RAGFlow modules not found or import error.")

def profile_run(pdf_path):
    print(f"Profiling file: {pdf_path}")
    timings = {}
    
    start_total = time.time()
    
    # 1. Init OCR
    start = time.time()
    ocr_engine = get_ocr_engine()
    timings['init_ocr'] = time.time() - start
    print(f"Init OCR: {timings['init_ocr']:.4f}s")
    
    # 2. Parse PDF (OCR)
    start = time.time()
    report = parse_pdf(str(pdf_path), ocr_engine=ocr_engine)
    timings['parse_pdf'] = time.time() - start
    print(f"Parse PDF: {timings['parse_pdf']:.4f}s")
    
    # 3. Extractions
    start = time.time()
    food_name = extract_food_name(report)
    production_date = extract_production_date(report)
    gb_codes = extract_gb_standards(report)
    gb_detail = extract_gb_standards_with_title(report)
    items = extract_inspection_items(report)
    timings['extraction'] = time.time() - start
    print(f"Extraction: {timings['extraction']:.4f}s")
    
    print(f"Extracted: {food_name}, {production_date}, {len(gb_codes)} GB codes, {len(items)} items")

    # Load Config
    config_path = BASE_DIR / "config.local.json"
    
    # 4. Verify GB Standards
    gb_validation_results = {}
    if production_date and gb_codes:
        print("Starting GB Verification directly...")
        start = time.time()
        try:
            gb_validation_results = verify_gb_standards(
                gb_codes=gb_codes,
                production_date=production_date,
                config_path=str(config_path),
                enable_screenshot=True, 
                enable_download=True 
            )
        except Exception as e:
            print(f"GB Verify Error: {e}")
        timings['gb_verification'] = time.time() - start
        print(f"GB Verification: {timings['gb_verification']:.4f}s")
    else:
        print("Skipping GB Verification (missing date or codes)")
        timings['gb_verification'] = 0

    # 5. Method Standards Verification
    if items:
        method_codes = set()
        import re
        gb_regex = re.compile(r"GB(?:/T)?\s*\d+(?:\.\d+)?\s*[—\-‑–－]\s*\d{4}")
        for item in items:
            method_str = item.get("method", "")
            if method_str:
                matches = gb_regex.findall(method_str)
                for code in matches:
                    method_codes.add(code)
        
        new_codes = [c for c in method_codes if c not in gb_validation_results]
        if new_codes:
            print(f"Verifying Method Standards: {len(new_codes)} codes")
            start = time.time()
            try:
                method_results = verify_gb_standards(
                    gb_codes=new_codes,
                    production_date=production_date,
                    config_path=str(config_path),
                    enable_screenshot=True,
                    enable_download=True
                )
            except Exception as e:
                print(f"Method Verify Error: {e}")
            timings['method_verification'] = time.time() - start
            print(f"Method Verification: {timings['method_verification']:.4f}s")
        else:
            timings['method_verification'] = 0

    # 6. RAGFlow Compliance
    if food_name and items:
        print("Starting RAGFlow Verification...")
        start = time.time()
        try:
            # Need to mock or ensure config is right for this to run
            # Assumes config.local.json has ragflow setup
            config = {}
            if config_path.exists():
                with open(config_path, "r", encoding="utf-8") as f:
                    config = json.load(f)
            
            verify_inspection_compliance(
                food_name=food_name,
                report_items=items,
                report_gb_codes=gb_codes,
                config=config
            )
        except Exception as e:
            print(f"RAGFlow Error: {e}")
        timings['ragflow_verification'] = time.time() - start
        print(f"RAGFlow Verification: {timings['ragflow_verification']:.4f}s")
    else:
        timings['ragflow_verification'] = 0

    timings['total'] = time.time() - start_total
    print("\n--- Summary ---")
    for k, v in timings.items():
        print(f"{k}: {v:.4f}s")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        pdf = sys.argv[1]
    else:
        # Default test file
        pdf = r"C:\Users\Administrator\Desktop\extractionSystem\backend\static\uploads\SP202501824 黄瓜.pdf"
    
    if not Path(pdf).exists():
        print(f"File not found: {pdf}")
        sys.exit(1)
        
    profile_run(pdf)
