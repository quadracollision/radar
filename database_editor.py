import tkinter as tk
from tkinter import ttk, messagebox
import pandas as pd
import os

DATABASE_FILE = "packing_list_database.csv"

class DatabaseEditorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Database Editor")
        self.root.geometry("600x400")
        
        self.df = pd.DataFrame(columns=["SKU", "Location", "Description"])
        
        self.create_widgets()
        self.load_database()

    def create_widgets(self):
        # Frame for inputs
        input_frame = ttk.LabelFrame(self.root, text="Edit Entry")
        input_frame.pack(fill="x", padx=10, pady=5)
        
        # SKU
        ttk.Label(input_frame, text="SKU:").grid(row=0, column=0, padx=5, pady=5, sticky="e")
        self.sku_var = tk.StringVar()
        self.sku_entry = ttk.Entry(input_frame, textvariable=self.sku_var)
        self.sku_entry.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        
        # Location
        ttk.Label(input_frame, text="Location:").grid(row=0, column=2, padx=5, pady=5, sticky="e")
        self.location_var = tk.StringVar()
        self.location_entry = ttk.Entry(input_frame, textvariable=self.location_var)
        self.location_entry.grid(row=0, column=3, padx=5, pady=5, sticky="ew")
        
        # Description
        ttk.Label(input_frame, text="Description:").grid(row=1, column=0, padx=5, pady=5, sticky="e")
        self.description_var = tk.StringVar()
        self.description_entry = ttk.Entry(input_frame, textvariable=self.description_var)
        self.description_entry.grid(row=1, column=1, columnspan=3, padx=5, pady=5, sticky="ew")
        
        input_frame.columnconfigure(1, weight=1)
        input_frame.columnconfigure(3, weight=1)

        # Buttons
        btn_frame = ttk.Frame(input_frame)
        btn_frame.grid(row=2, column=0, columnspan=4, pady=5)
        
        ttk.Button(btn_frame, text="Save / Update", command=self.save_entry).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Delete", command=self.delete_entry).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Clear", command=self.clear_inputs).pack(side="left", padx=5)

        # Treeview for listing
        list_frame = ttk.Frame(self.root)
        list_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        columns = ("SKU", "Location", "Description")
        self.tree = ttk.Treeview(list_frame, columns=columns, show="headings")
        self.tree.heading("SKU", text="SKU")
        self.tree.heading("Location", text="Location")
        self.tree.heading("Description", text="Description")
        
        self.tree.column("SKU", width=100)
        self.tree.column("Location", width=100)
        self.tree.column("Description", width=300)
        
        self.tree.pack(side="left", fill="both", expand=True)
        
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.tree.yview)
        scrollbar.pack(side="right", fill="y")
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        self.tree.bind("<<TreeviewSelect>>", self.on_select)

    def load_database(self):
        if os.path.exists(DATABASE_FILE):
            try:
                # Read CSV, ensure all columns exist
                self.df = pd.read_csv(DATABASE_FILE, dtype=str)
                if "Description" not in self.df.columns:
                    self.df["Description"] = ""
                
                # Fill NaN with empty string
                self.df = self.df.fillna("")
                
                self.refresh_list()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load database: {e}")
        else:
            # Create if not exists
            self.df = pd.DataFrame(columns=["SKU", "Location", "Description"])
            self.save_database()

    def refresh_list(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
            
        for index, row in self.df.iterrows():
            self.tree.insert("", "end", values=(row["SKU"], row["Location"], row["Description"]))

    def on_select(self, event):
        selected_item = self.tree.selection()
        if selected_item:
            values = self.tree.item(selected_item[0])["values"]
            if values:
                self.sku_var.set(values[0])
                self.location_var.set(values[1])
                # Description might be missing if older format, handle safely
                desc = values[2] if len(values) > 2 else ""
                self.description_var.set(desc)

    def save_entry(self):
        sku = self.sku_var.get().strip()
        location = self.location_var.get().strip()
        description = self.description_var.get().strip()
        
        if not sku:
            messagebox.showwarning("Warning", "SKU cannot be empty.")
            return

        # Check if SKU exists
        if sku in self.df["SKU"].values:
            # Update
            self.df.loc[self.df["SKU"] == sku, ["Location", "Description"]] = [location, description]
        else:
            # Add new
            new_row = pd.DataFrame([{"SKU": sku, "Location": location, "Description": description}])
            self.df = pd.concat([self.df, new_row], ignore_index=True)
            
        self.save_database()
        self.refresh_list()
        self.clear_inputs()
        messagebox.showinfo("Success", f"SKU {sku} saved.")

    def delete_entry(self):
        sku = self.sku_var.get().strip()
        if not sku:
            return
            
        if sku in self.df["SKU"].values:
            if messagebox.askyesno("Confirm", f"Delete SKU {sku}?"):
                self.df = self.df[self.df["SKU"] != sku]
                self.save_database()
                self.refresh_list()
                self.clear_inputs()

    def clear_inputs(self):
        self.sku_var.set("")
        self.location_var.set("")
        self.description_var.set("")

    def save_database(self):
        try:
            self.df.to_csv(DATABASE_FILE, index=False)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save database: {e}")

if __name__ == "__main__":
    root = tk.Tk()
    app = DatabaseEditorApp(root)
    root.mainloop()
