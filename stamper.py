import fitz # PyMuPDF
import re
import os
import tempfile

# --- Stamping Offset (Used for placing the text relative to the SKU) ---
OFFSET_Y = 11     # Place 15 points below the SKU
FONT_SIZE = 12
FONT_NAME = "helv" # Helvetica

def extract_all_items(pdf_path):
    """
    Finds ALL SKUs and their coordinates across ALL pages of the PDF.
    Returns: A list of dictionaries: 
             [{'sku': str, 'rect': fitz.Rect, 'page_index': int}, ...]
    """
    items_to_stamp = []
    
    try:
        doc = fitz.open(pdf_path)
        
        # Iterate through every page
        for page_index, page in enumerate(doc):
            full_text = page.get_text("text")

            # Reset search position for each page
            last_size_index = -1
            
            # Loop to find multiple 'Size:' declarations on one page
            while True:
                # 1. Find the next "Size:" text to establish context.
                size_index = full_text.find("Size:", last_size_index + 1)
                
                if size_index == -1:
                    # No more "Size:" instances on this page
                    break 

                # Set the starting point for the next search
                last_size_index = size_index
                
                # Define a context window starting right after 'Size:'
                text_after_size = full_text[size_index:]
                
                # 2. Search for the SKU pattern within the context window
                # RegEx: looks for a standalone alphanumeric code (5 to 15 chars)
                sku_regex = r'([A-Za-z0-9]{5,15})'
                match = re.search(sku_regex, text_after_size, re.IGNORECASE)
                
                if not match:
                    # If no SKU found in this size block (e.g., Page 4 item), skip this block
                    items_to_stamp.append({
                        'sku': "00000", 
                        'rect': None, 
                        'page_index': page_index
                    })
                    continue

                extracted_sku = match.group(1)

                # 3. Find the coordinates for *just the extracted SKU text* on the current page
                # We search from the position where the SKU was found
                sku_only_results = page.search_for(extracted_sku, flags=fitz.TEXT_PRESERVE_WHITESPACE)
                
                if sku_only_results:
                    # Found SKU with coordinates. Add it to the list.
                    items_to_stamp.append({
                        'sku': extracted_sku, 
                        'rect': sku_only_results[0], 
                        'page_index': page_index
                    })
                elif extracted_sku == "00000":
                    # SKU assigned 00000 but no coordinates needed for stamping failure tracking
                     items_to_stamp.append({
                        'sku': "00000", 
                        'rect': None, 
                        'page_index': page_index
                    })
                # If SKU found in text but no coords, we skip stamping for this item.

        return items_to_stamp

    except Exception as e:
        print(f"CRITICAL ERROR during PDF parsing: {e}")
        return []

def write_location_to_pdf(pdf_path, location_text, sku_rect, page_index):
    """
    Opens the PDF, writes the location text on the specified page, and saves the file 
    by saving to a temporary file first, which bypasses common save restrictions.
    """
    temp_file = None
    try:
        doc = fitz.open(pdf_path)
        page = doc[page_index]
        
        # Calculate the new insertion point: 
        x_coord = sku_rect.x0
        y_coord = sku_rect.y1 + OFFSET_Y
        
        point = fitz.Point(x_coord, y_coord)
        
        # Insert the text
        page.insert_text(
            point,                  # Calculated point where text should start
            f"LOCATION: {location_text}", # Text to be inserted
            fontsize=FONT_SIZE,     # Font size
            fontname=FONT_NAME,     # Font type
            color=(0, 0, 1)         # Color (Blue)
        )
        
        # --- Save to temporary file and rename to bypass save restrictions ---
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf").name
        # Use doc.save(..., garbage=3) for maximum cleanup and compatibility
        doc.save(temp_file, incremental=False, encryption=fitz.PDF_ENCRYPT_NONE, garbage=3)
        doc.close()
        
        # Ensure the file is completely closed before attempting to replace it
        if os.path.exists(temp_file):
            os.replace(temp_file, pdf_path)
        # ------------------------------------------------------------------------
        
        return True
    except Exception as e:
        print(f"ERROR writing to PDF on Page {page_index + 1}: {e}")
        if temp_file and os.path.exists(temp_file):
            os.remove(temp_file)
        return False
