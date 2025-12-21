import fitz
import re
import os
import tempfile

def mark_preorders(pdf_path):
    """
    Scans the PDF for text matching "Pre-Order" (case-insensitive, various formats)
    and draws a red line through it.
    """
    print(f"Scanning for Pre-Order items in {pdf_path}...")
    temp_file = None
    changes_made = False

    try:
        doc = fitz.open(pdf_path)
        
        # Regex to match "Pre-Order", "Pre Order", "pre order", "preorder"
        # \b ensures word boundaries if needed, but might be safer without to catch "PreOrder"
        # Let's use a flexible pattern.
        pattern = r"pre[- ]?order" 
        
        for page_index, page in enumerate(doc):
            # correct way to search with regex in PyMuPDF is not direct.
            # search_for only supports literal strings.
            # So we get all text and find matches, then search for matching text location?
            # Or simpler: iterate through words/blocks?
            
            # Better approach with PyMuPDF:
            # 1. Get all text blocks
            # 2. Find matches in text
            # 3. Use 'search_for' with the MATCHED STRING to get coordinates. 
            # CAUTION: 'search_for' might find the same string elsewhere that isn't a pre-order match if not careful.
            # But "Pre-Order" is specific enough.
            
            # Even better: Iterate through text instances logic
            
            full_text = page.get_text("text")
            matches = list(re.finditer(pattern, full_text, re.IGNORECASE))
            
            if not matches:
                continue
                
            for match in matches:
                matched_string = match.group()
                # Search for this specific string on the page
                # We limit hit_max to avoid excessive processing if it appears many times, 
                # but we probably want all of them.
                text_instances = page.search_for(matched_string)
                
                for rect in text_instances:
                    # Draw red line through the middle
                    # rect is (x0, y0, x1, y1)
                    # Middle y = (y0 + y1) / 2
                    
                    p1 = fitz.Point(rect.x0, (rect.y0 + rect.y1) / 2)
                    p2 = fitz.Point(rect.x1, (rect.y0 + rect.y1) / 2)
                    
                    shape = page.new_shape()
                    shape.draw_line(p1, p2)
                    # Red color (1, 0, 0), width 2
                    shape.finish(color=(1, 0, 0), width=3, stroke_opacity=0.8) 
                    shape.commit()
                    changes_made = True
                    # Also maybe draw a box? User asked for "red line through the text"
                    
        if changes_made:
            print("  Found and marked 'Pre-Order' items.")
            # Save to temp file
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf").name
            doc.save(temp_file, garbage=3)
            doc.close()
            
            if os.path.exists(temp_file):
                os.replace(temp_file, pdf_path)
        else:
            print("  No 'Pre-Order' items found.")
            doc.close()
            
        return True

    except Exception as e:
        print(f"ERROR marking pre-orders: {e}")
        if temp_file and os.path.exists(temp_file):
            os.remove(temp_file)
        return False
