import fitz  # PyMuPDF
import re
import os
import tempfile

def sort_shipping_labels(pdf_path):
    """
    Sorts the pages of a shipping labels PDF based on 'Order #' in ascending numerical order.
    Modifies the PDF file in-place.
    
    Args:
        pdf_path: Path to the shipping labels PDF file.
    
    Returns:
        True if sorting was successful, False otherwise.
    """
    print(f"Sorting shipping labels in {pdf_path}...")
    temp_file = None
    
    try:
        doc = fitz.open(pdf_path)
        page_metadata = []

        for page_index, page in enumerate(doc):
            text = page.get_text("text")
            
            # Extract Order Number from "Order #XXXXX" pattern
            order_match = re.search(r'Order #(\d+)', text)
            order_num = int(order_match.group(1)) if order_match else float('inf')
            
            page_metadata.append({
                'index': page_index,
                'order_num': order_num
            })
            
            if order_match:
                print(f"  Page {page_index + 1}: Order #{order_num}")
            else:
                print(f"  Page {page_index + 1}: No order number found")

        # Sort based on Order Number (ascending)
        page_metadata.sort(key=lambda x: x['order_num'])
        
        # Check if sorting is actually needed
        sorted_indices = [x['index'] for x in page_metadata]
        if sorted_indices == list(range(len(sorted_indices))):
            print("  Labels are already in correct order.")
            doc.close()
            return True

        print("  Reordering pages...")
        
        # Reorder pages in the document
        doc.select(sorted_indices)
        
        # Save to temp file first
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf").name
        doc.save(temp_file, garbage=3)
        doc.close()
        
        # Replace original file
        if os.path.exists(temp_file):
            os.replace(temp_file, pdf_path)
            
        print("  Sorting complete.")
        
        # Print the new order
        print("  New order:")
        for i, meta in enumerate(page_metadata):
            print(f"    Position {i + 1}: Order #{meta['order_num']}")
            
        return True

    except Exception as e:
        print(f"ERROR sorting shipping labels: {e}")
        if temp_file and os.path.exists(temp_file):
            os.remove(temp_file)
        return False


if __name__ == "__main__":
    # For standalone testing
    import sys
    if len(sys.argv) > 1:
        sort_shipping_labels(sys.argv[1])
    else:
        print("Usage: python label_sorter.py <pdf_path>")
