import pandas as pd
import os
import glob
import sys
from sorter import sort_pdf_pages
from stamper import extract_all_items, write_location_to_pdf
from preorder_marker import mark_preorders

# --- Configuration ---
DATABASE_FILE = "packing_list_database.csv"

# --- User Interaction Functions ---

def select_pdf_file():
    """
    Lists PDF files in the current directory and allows the user to select one.
    """
    pdf_files = sorted(glob.glob("*.pdf"))
    
    if not pdf_files:
        print("No PDF files found in the current directory.")
        return None

    print("\nSelect a PDF file to process:")
    for i, filename in enumerate(pdf_files):
        print(f"  [{i + 1}] {filename}")
        
    while True:
        try:
            choice = input("Enter the number of the PDF to load (or 'q' to quit): ")
            if choice.lower() == 'q':
                return None
            
            index = int(choice) - 1
            
            if 0 <= index < len(pdf_files):
                return pdf_files[index]
            else:
                print("Invalid number. Please select a number from the list.")
        except ValueError:
            print("Invalid input. Please enter a number or 'q'.")

# --- Main Logic ---

def main():
    """Main execution function for the script."""
    
    print("--- PDF Dynamic Batch Stamper (PyMuPDF) ---")
    
    # 1. Load the database
    if not os.path.exists(DATABASE_FILE):
        print(f"ERROR: Database file {DATABASE_FILE} not found. Please create it.")
        sys.exit(1)
    
    print(f"Loading database from {DATABASE_FILE}...")
    try:
        df = pd.read_csv(DATABASE_FILE)
        df['SKU'] = df['SKU'].astype(str)
        df = df.set_index('SKU') 
    except Exception as e:
        print(f"CRITICAL ERROR: Could not load or process CSV. {e}")
        sys.exit(1)
    
    # 2. Get Input and Process PDF
    pdf_path = select_pdf_file()
    
    if pdf_path is None:
        print("Process aborted.")
        return

    print(f"\nProcessing file: {pdf_path}")
    
    # Sort the PDF pages first
    sort_pdf_pages(pdf_path)

    # Mark Pre-Orders
    mark_preorders(pdf_path)

    # Extract ALL SKUs and their coordinates from ALL pages
    items_to_process = extract_all_items(pdf_path)
    
    if not items_to_process:
        print("ERROR: No 'Size:' declarations were found in the PDF. Aborting.")
        return
        
    print(f"Found {len(items_to_process)} potential item(s) to process.")
    
    # 3. Loop through all found items, look up location, and stamp
    stamps_successful = 0
    
    for i, item in enumerate(items_to_process):
        extracted_sku = item['sku']
        sku_rect = item['rect']
        page_index = item['page_index']

        print(f"\n--- Processing Item {i+1} (Page {page_index + 1}) ---")
        print(f"  SKU Extracted: {extracted_sku}")
        
        # Look up Location
        location_to_stamp = None
        try:
            location = df.loc[extracted_sku, 'Location']
            
            if pd.isna(location) or location == "":
                 print("  WARNING: Location field is empty in CSV.")
                 location_to_stamp = "LOCATION NOT DEFINED"
            else:
                location_to_stamp = str(location)
                
        except KeyError:
            print(f"  ERROR: SKU {extracted_sku} was not found in the database.")
            location_to_stamp = "SKU NOT FOUND"
        
        # Stamp PDF
        if location_to_stamp in ["SKU NOT FOUND", "LOCATION NOT DEFINED"]:
            print(f"  Skipped stamping due to lookup failure: {location_to_stamp}.")
            
        else:
            print(f"  Stamping Location {location_to_stamp}...")
            
            if sku_rect is None:
                 print("  Failed to get SKU coordinates. Cannot stamp dynamically.")
                 continue
                 
            if write_location_to_pdf(pdf_path, location_to_stamp, sku_rect, page_index):
                stamps_successful += 1
            # Note: The PDF is saved/overwritten on every successful stamp.

    print("\n--- Batch Processing Complete ---")
    print(f"Total items processed: {len(items_to_process)}")
    print(f"Total stamps successfully applied: {stamps_successful}")

    # 4. Generate Summary Page
    print("\n--- Generating Summary Page ---")
    try:
        from aggregator import process_pdf
        process_pdf(pdf_path)
    except ImportError:
        print("ERROR: Could not import aggregator module. Summary page skipped.")
    except Exception as e:
         print(f"ERROR generating summary page: {e}")


if __name__ == "__main__":
    main()
