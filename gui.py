#!/usr/bin/env python3
"""
PDF Processing Tool - Graphical User Interface

A user-friendly tkinter GUI for processing packing slips and shipping labels.
"""

import tkinter as tk
from tkinter import ttk, scrolledtext
import pandas as pd
import os
import glob
import sys
import threading
from io import StringIO

# Import processing functions from existing modules
from sorter import sort_pdf_pages
from stamper import extract_all_items, write_location_to_pdf
from preorder_marker import mark_preorders
from label_sorter import sort_shipping_labels

# --- Configuration ---
DATABASE_FILE = "packing_list_database.csv"


class TextRedirector:
    """Redirects stdout/stderr to a tkinter Text widget."""
    def __init__(self, text_widget, tag="stdout"):
        self.text_widget = text_widget
        self.tag = tag

    def write(self, text):
        self.text_widget.configure(state='normal')
        self.text_widget.insert(tk.END, text, (self.tag,))
        self.text_widget.see(tk.END)
        self.text_widget.configure(state='disabled')

    def flush(self):
        pass


class PDFProcessorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("PDF Processing Tool")
        self.root.geometry("600x500")
        self.root.minsize(500, 400)
        
        # Configure grid weights for resizing
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(3, weight=1)
        
        # Store original stdout
        self.original_stdout = sys.stdout
        self.original_stderr = sys.stderr
        
        # Database
        self.df = None
        
        self.create_widgets()
        self.load_database()
        self.refresh_pdf_list()

    def create_widgets(self):
        """Create all GUI widgets."""
        
        # --- Header ---
        header = ttk.Label(
            self.root, 
            text="PDF Processing Tool", 
            font=('Helvetica', 16, 'bold')
        )
        header.grid(row=0, column=0, pady=(15, 10), padx=20, sticky='w')
        
        # --- PDF Selection Frame ---
        select_frame = ttk.Frame(self.root)
        select_frame.grid(row=1, column=0, padx=20, pady=10, sticky='ew')
        select_frame.columnconfigure(1, weight=1)
        
        ttk.Label(select_frame, text="Select PDF:").grid(row=0, column=0, padx=(0, 10))
        
        self.pdf_var = tk.StringVar()
        self.pdf_dropdown = ttk.Combobox(
            select_frame, 
            textvariable=self.pdf_var, 
            state='readonly',
            width=40
        )
        self.pdf_dropdown.grid(row=0, column=1, sticky='ew', padx=(0, 10))
        
        self.refresh_btn = ttk.Button(
            select_frame, 
            text="Refresh", 
            command=self.refresh_pdf_list,
            width=10
        )
        self.refresh_btn.grid(row=0, column=2)
        
        self.edit_db_btn = ttk.Button(
            select_frame, 
            text="Edit DB", 
            command=self.open_database_editor,
            width=10
        )
        self.edit_db_btn.grid(row=0, column=3, padx=(5, 0))
        
        # --- Process Button ---
        self.process_btn = ttk.Button(
            self.root, 
            text="Process Selected PDF", 
            command=self.start_processing,
            style='Accent.TButton'
        )
        self.process_btn.grid(row=2, column=0, pady=15, padx=20, sticky='ew')
        
        # --- Log Output Frame ---
        log_frame = ttk.LabelFrame(self.root, text="Log Output")
        log_frame.grid(row=3, column=0, padx=20, pady=(0, 15), sticky='nsew')
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        
        self.log_text = scrolledtext.ScrolledText(
            log_frame,
            wrap=tk.WORD,
            font=('Consolas', 10),
            state='disabled',
            bg='#1e1e1e',
            fg='#d4d4d4',
            insertbackground='white'
        )
        self.log_text.grid(row=0, column=0, sticky='nsew', padx=5, pady=5)
        
        # Configure text tags for coloring
        self.log_text.tag_config('stdout', foreground='#d4d4d4')
        self.log_text.tag_config('stderr', foreground='#f44747')
        self.log_text.tag_config('success', foreground='#4ec9b0')
        self.log_text.tag_config('info', foreground='#569cd6')
        
        # --- Status Bar ---
        self.status_var = tk.StringVar(value="Ready")
        self.status_bar = ttk.Label(
            self.root, 
            textvariable=self.status_var, 
            relief=tk.SUNKEN, 
            anchor=tk.W
        )
        self.status_bar.grid(row=4, column=0, sticky='ew', padx=0, pady=0)

    def log(self, message, tag="stdout"):
        """Add a message to the log with optional coloring."""
        self.log_text.configure(state='normal')
        self.log_text.insert(tk.END, message + "\n", (tag,))
        self.log_text.see(tk.END)
        self.log_text.configure(state='disabled')

    def clear_log(self):
        """Clear the log output."""
        self.log_text.configure(state='normal')
        self.log_text.delete(1.0, tk.END)
        self.log_text.configure(state='disabled')

    def load_database(self):
        """Load the packing list database."""
        if not os.path.exists(DATABASE_FILE):
            self.log(f"ERROR: Database file {DATABASE_FILE} not found!", "stderr")
            self.status_var.set("Error: Database not found")
            return False
        
        try:
            self.df = pd.read_csv(DATABASE_FILE)
            self.df['SKU'] = self.df['SKU'].astype(str)
            self.df = self.df.set_index('SKU')
            self.log(f"Loaded database from {DATABASE_FILE}", "info")
            return True
        except Exception as e:
            self.log(f"ERROR loading database: {e}", "stderr")
            self.status_var.set("Error: Could not load database")
            return False

    def refresh_pdf_list(self):
        """Refresh the list of PDF files in the dropdown."""
        pdf_files = sorted(glob.glob("*.pdf"))
        self.pdf_dropdown['values'] = pdf_files
        
        if pdf_files:
            self.pdf_dropdown.current(0)
            self.log(f"Found {len(pdf_files)} PDF file(s)", "info")
        else:
            self.pdf_var.set("")
            self.log("No PDF files found in directory", "stderr")
        
        self.status_var.set(f"Found {len(pdf_files)} PDF files")

    def start_processing(self):
        """Start processing in a separate thread to keep GUI responsive."""
        pdf_path = self.pdf_var.get()
        
        if not pdf_path:
            self.log("Please select a PDF file first!", "stderr")
            return
        
        if not os.path.exists(pdf_path):
            self.log(f"File not found: {pdf_path}", "stderr")
            return
        
        # Disable button during processing
        self.process_btn.configure(state='disabled')
        self.refresh_btn.configure(state='disabled')
        self.status_var.set("Processing...")
        
        # Clear previous log
        self.clear_log()
        
        # Run processing in a thread
        thread = threading.Thread(target=self.process_pdf, args=(pdf_path,))
        thread.daemon = True
        thread.start()

    def process_pdf(self, pdf_path):
        """Process the selected PDF file."""
        try:
            # Redirect stdout to capture print statements
            sys.stdout = TextRedirector(self.log_text, "stdout")
            sys.stderr = TextRedirector(self.log_text, "stderr")
            
            print(f"--- PDF Processing Started ---")
            print(f"Processing file: {pdf_path}")
            
            # Check if this is shipping labels
            if "shipping" in pdf_path.lower() and "label" in pdf_path.lower():
                print("\n--- Detected Shipping Labels PDF ---")
                sort_shipping_labels(pdf_path)
                self.root.after(0, lambda: self.log("\n✓ Shipping labels sorted successfully!", "success"))
            else:
                # Process as packing slips
                self._process_packing_slips(pdf_path)
            
            self.root.after(0, lambda: self.status_var.set("Done!"))
            
        except Exception as e:
            self.root.after(0, lambda: self.log(f"\nERROR: {e}", "stderr"))
            self.root.after(0, lambda: self.status_var.set("Error occurred"))
        finally:
            # Restore stdout
            sys.stdout = self.original_stdout
            sys.stderr = self.original_stderr
            
            # Re-enable buttons
            self.root.after(0, lambda: self.process_btn.configure(state='normal'))
            self.root.after(0, lambda: self.refresh_btn.configure(state='normal'))

    def _process_packing_slips(self, pdf_path):
        """Process packing slip PDFs."""
        if self.df is None:
            print("ERROR: Database not loaded!")
            return
        
        # Sort pages
        sort_pdf_pages(pdf_path)
        
        # Mark pre-orders
        mark_preorders(pdf_path)
        
        # Extract items
        items_to_process = extract_all_items(pdf_path)
        
        if not items_to_process:
            print("ERROR: No items found in the PDF.")
            return
        
        print(f"Found {len(items_to_process)} item(s) to process.")
        
        # Process each item
        stamps_successful = 0
        
        for i, item in enumerate(items_to_process):
            extracted_sku = item['sku']
            sku_rect = item['rect']
            page_index = item['page_index']
            
            print(f"\n--- Processing Item {i+1} (Page {page_index + 1}) ---")
            print(f"  SKU: {extracted_sku}")
            
            # Look up location
            location_to_stamp = None
            try:
                location = self.df.loc[extracted_sku, 'Location']
                
                if pd.isna(location) or location == "":
                    print("  WARNING: Location field is empty in CSV.")
                    location_to_stamp = "LOCATION NOT DEFINED"
                else:
                    location_to_stamp = str(location)
                    
            except KeyError:
                print(f"  ERROR: SKU {extracted_sku} not found in database.")
                location_to_stamp = "SKU NOT FOUND"
            
            # Stamp PDF
            if location_to_stamp in ["SKU NOT FOUND", "LOCATION NOT DEFINED"]:
                print(f"  Skipped: {location_to_stamp}")
            else:
                print(f"  Stamping Location: {location_to_stamp}")
                
                if sku_rect is None:
                    print("  Failed: No SKU coordinates.")
                    continue
                
                if write_location_to_pdf(pdf_path, location_to_stamp, sku_rect, page_index):
                    stamps_successful += 1
        
        print(f"\n--- Processing Complete ---")
        print(f"Total items: {len(items_to_process)}")
        print(f"Stamps applied: {stamps_successful}")
        
        # Generate summary page
        print("\n--- Generating Summary Page ---")
        try:
            from aggregator import process_pdf
            process_pdf(pdf_path)
        except ImportError:
            print("ERROR: Could not import aggregator module.")
        except Exception as e:
            print(f"ERROR generating summary: {e}")
        
        self.root.after(0, lambda: self.log(f"\n✓ Processing complete! {stamps_successful} stamps applied.", "success"))


    def open_database_editor(self):
        """Open the database editor window."""
        try:
            import database_editor
            editor_window = tk.Toplevel(self.root)
            app = database_editor.DatabaseEditorApp(editor_window)
        except ImportError:
            self.log("ERROR: Could not import database_editor module.", "stderr")
        except Exception as e:
            self.log(f"ERROR launching editor: {e}", "stderr")


def main():
    root = tk.Tk()
    
    # Try to use a modern theme
    try:
        style = ttk.Style()
        available_themes = style.theme_names()
        if 'clam' in available_themes:
            style.theme_use('clam')
    except:
        pass
    
    app = PDFProcessorApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
