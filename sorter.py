import fitz # PyMuPDF
import re
import os
import tempfile

def sort_pdf_pages(pdf_path):
    """
    Sorts the pages of the PDF based on 'Order #' and sequence 'X of Y'.
    Sorts in ascending order of Order #, then by sequence number.
    """
    print(f"Sorting pages in {pdf_path}...")
    temp_file = None
    try:
        doc = fitz.open(pdf_path)
        page_metadata = []

        for page_index, page in enumerate(doc):
            text = page.get_text("text") # Fast text extraction
            
            # Extract Order Number
            order_match = re.search(r'Order #(\d+)', text)
            order_num = int(order_match.group(1)) if order_match else float('inf') # Put missing orders at the end

            # Extract Sequence Number (e.g., "1 of 1")
            seq_match = re.search(r'(\d+) of (\d+)', text)
            seq_num = int(seq_match.group(1)) if seq_match else 0
            
            page_metadata.append({
                'index': page_index,
                'order_num': order_num,
                'seq_num': seq_num
            })

        # Sort based on Order Number then Sequence Number
        # Tuple comparison works element-wise: (order, seq)
        page_metadata.sort(key=lambda x: (x['order_num'], x['seq_num']))
        
        # Check if sorting is actually needed (optimization)
        sorted_indices = [x['index'] for x in page_metadata]
        if sorted_indices == list(range(len(sorted_indices))):
             print("  Pages are already in correct order.")
             return True

        print("  Reordering pages...")
        # Create a new document with sorted pages
        doc.select(sorted_indices)
        
        # Save to temp file
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf").name
        doc.save(temp_file, garbage=3)
        doc.close()
        
        # Replace original
        if os.path.exists(temp_file):
            os.replace(temp_file, pdf_path)
            
        print("  Sorting complete.")
        return True

    except Exception as e:
        print(f"ERROR sorting PDF: {e}")
        if temp_file and os.path.exists(temp_file):
            os.remove(temp_file)
        return False
