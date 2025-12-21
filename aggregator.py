import fitz
import re
import pandas as pd
import os
import sys

# --- Configuration ---
DATABASE_FILE = "packing_list_database.csv"

def load_database():
    """Loads the SKU -> Location database."""
    if not os.path.exists(DATABASE_FILE):
        print(f"ERROR: Database file {DATABASE_FILE} not found.")
        return {}
    
    try:
        df = pd.read_csv(DATABASE_FILE)
        # Ensure SKU is string and strip whitespace
        df['SKU'] = df['SKU'].astype(str).str.strip()
        # Create a dictionary for fast lookup
        return df.set_index('SKU')['Location'].to_dict()
    except Exception as e:
        print(f"ERROR: Could not load database: {e}")
        return {}

def extract_items_from_pdf(pdf_path):
    """
    Parses the PDF to find items based on the 'X of Y' quantity pattern.
    Returns a list of dictionaries: {'name': str, 'sku': str, 'size': str}
    """
    items = []
    
    try:
        doc = fitz.open(pdf_path)
        
        for page_num, page in enumerate(doc):
            text = page.get_text("text")
            lines = text.split('\n')
            
            # We iterate through lines and look for the quantity pattern "1 of 1"
            # When found, we look backwards to find Name, Size, SKU
            
            for i, line in enumerate(lines):
                # Check for "X of Y" pattern (e.g., "1 of 1")
                # regex: start of line, digits, space, of, space, digits
                # The line might just be "1 of 1" or have spaces
                if re.match(r'^\s*\d+\s+of\s+\d+\s*$', line):
                    
                    # Found an item block end. Now parse backwards.
                    # We expect:
                    # [Item Name] (One or more lines)
                    # [Size: ...] (Optional)
                    # [SKU] (Optional, 5-15 alphanumeric chars)
                    # [Quantity Line] (Current Line)
                    
                    # Let's collect lines backwards until we hit a "safe" boundary 
                    # or a reasonable limit (e.g., 4 lines)
                    
                    # Heuristic:
                    # 1. Look at i-1. Is it a SKU? (Regex check)
                    # 2. Look at i-1 (or i-2 if SKU found). Is it Size? (StartsWith "Size:")
                    # 3. Everything before that (up to previous item or header) is name.
                    
                    current_idx = i - 1
                    extracted_sku = "NO SKU"
                    extracted_size = ""
                    extracted_name_parts = []
                    
                    # 1. Check for SKU
                    if current_idx >= 0:
                        candidate = lines[current_idx].strip()
                        # SKU Regex: 5-15 alphanumeric, no spaces usually
                        if re.match(r'^[A-Za-z0-9]{5,15}$', candidate) and not candidate.startswith("Size:"):
                             extracted_sku = candidate
                             current_idx -= 1
                    
                    # 2. Check for Size
                    if current_idx >= 0:
                        candidate = lines[current_idx].strip()
                        if candidate.startswith("Size:"):
                            extracted_size = candidate
                            current_idx -= 1
                    
                    # 3. Capture Name
                    # We need to be careful not to merge with previous item text.
                    # Text structure usually has headers like "ITEMS" or previous "X of Y"
                    # Simple heuristic: Take the line at current_idx. 
                    # If there are multiple lines for name, it's harder. 
                    # For now, let's take up to 2 lines backwards, stopping if we hit empty line or "QUANTITY"
                    
                    name_lines = []
                    for _ in range(2): # Look back max 2 lines for name
                        if current_idx < 0: break
                        line_content = lines[current_idx].strip()
                        if not line_content: break # Stop at empty line
                        if line_content == "QUANTITY": break # Stop at header
                        if re.match(r'^\s*\d+\s+of\s+\d+\s*$', line_content): break # Stop at previous item
                        if line_content == "ITEMS": break
                        
                        name_lines.insert(0, line_content) # Prepend
                        current_idx -= 1
                        
                    extracted_name = " ".join(name_lines)
                    
                    if extracted_name:
                         items.append({
                             'name': extracted_name,
                             'sku': extracted_sku,
                             'size': extracted_size
                         })

        return items

    except Exception as e:
        print(f"Error parsing PDF: {e}")
        return []

def aggregate_items(items, location_db):
    """
    Aggregates items and counts them. Looks up locations.
    Returns a sorted list of strings for the summary.
    """
    # Key: (Name, SKU, Size) -> Count
    counts = {}
    
    for item in items:
        # Create a unique key for processing
        # We might want to group by SKU if available, otherwise Name+Size
        key = (item['name'], item['sku'], item['size'])
        counts[key] = counts.get(key, 0) + 1
        
    summary_lines = []
    
    for (name, sku, size), count in counts.items():
        # Location Lookup
        location = "No Location"
        if sku in location_db:
            loc_val = location_db[sku]
            if not pd.isna(loc_val) and str(loc_val).strip() != "":
                location = str(loc_val).strip()
        
        # Format: Name (SKU) (Location) xCount
        # User requested: Vietnam Jiu-Jitsu Rashguard (SKU) (Location) x20
        # Incorporating Size if present to distinguish items
        
        display_name = name
        if size:
            display_name += f" ({size})"
            
        line = f"{display_name} ({sku}) ({location}) x{count}"
        summary_lines.append(line)
        
    # Sort for tidiness (maybe by Location, then Name)
    # For now, just sort alphabetically
    summary_lines.sort()
    
    return summary_lines

def create_summary_page(summary_lines):
    """
    Creates a new PDF page with the summary list.
    """
    doc = fitz.open()
    page = doc.new_page()
    
    # Title
    page.insert_text((50, 50), "Packing List Summary", fontsize=18, fontname="helv", color=(0, 0, 0))
    
    # List
    y_pos = 80
    line_height = 15
    
    for line in summary_lines:
        page.insert_text((50, y_pos), line, fontsize=10, fontname="helv", color=(0, 0, 0))
        y_pos += line_height
        
        # Start new page if full (simple check)
        if y_pos > 800:
            page = doc.new_page()
            y_pos = 50
            
    return doc

def process_pdf(pdf_path):
    print(f"Processing {pdf_path}...")
    
    # 1. Load DB
    db = load_database()
    
    # 2. Extract
    items = extract_items_from_pdf(pdf_path)
    print(f"Found {len(items)} items.")
    
    if not items:
        print("No items found. Check file format.")
        return
        
    # 3. Aggregate
    summary_lines = aggregate_items(items, db)
    
    # 4. Create Summary Page
    summary_doc = create_summary_page(summary_lines)
    
    # 5. Merge
    original_doc = fitz.open(pdf_path)
    summary_doc.insert_pdf(original_doc)
    
    # 6. Save
    # Save to a temporary file first
    output_path = pdf_path.replace(".pdf", "_processed.pdf") # For safety during dev, or overwrite
    # User implied overwriting or adding to it. "this script should look... and add up... in a list on the first page"
    # To be safe, I'll overwrite, but maybe I should confirm?
    # The stamper overwrites, so I will overwrite too to keep workflow consistent.
    
    # Actually, let's use a temp name and then rename.
    temp_name = "temp_summary.pdf"
    summary_doc.save(temp_name)
    
    os.replace(temp_name, pdf_path)
    print(f"Updated {pdf_path} with summary page.")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 aggregator.py <pdf_file>")
    else:
        process_pdf(sys.argv[1])
