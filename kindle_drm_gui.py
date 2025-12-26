"""
Kindle DRM Removal GUI

A modern GUI application for bulk DRM removal and format conversion of Kindle books.
Uses CustomTkinter for a sleek dark theme.
"""

import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog, messagebox
import os
import sys
import threading
import queue
import glob
import json
import tempfile
import shutil
from zipfile import ZipFile, ZIP_STORED
from datetime import datetime

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Import our modules
from convert_kfx import convert_book, find_calibre_debug

# Setup DeDRM imports
TOOLS_PATH = os.path.join(PROJECT_ROOT, 'DeDRM_tools')
if TOOLS_PATH not in sys.path:
    sys.path.append(TOOLS_PATH)

PLUGIN_PATH = os.path.join(TOOLS_PATH, 'DeDRM_plugin')

try:
    for filename in os.listdir(PLUGIN_PATH):
        if filename.endswith(".py") and not filename.startswith("__"):
            module_name = filename[:-3]
            try:
                full_module_name = f"DeDRM_plugin.{module_name}"
                __import__(full_module_name)
                if module_name not in sys.modules:
                    sys.modules[module_name] = sys.modules[full_module_name]
            except Exception:
                pass
    
    import DeDRM_plugin.kindlekey as kindlekey
    import DeDRM_plugin.k4mobidedrm as k4mobidedrm
    DEDRM_AVAILABLE = True
except ImportError as e:
    DEDRM_AVAILABLE = False
    DEDRM_ERROR = str(e)


# Configure CustomTkinter
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


class KindleBook:
    """Represents a Kindle book found in the content folder."""
    def __init__(self, main_file, folder):
        self.main_file = main_file
        self.folder = folder
        self.filename = os.path.basename(main_file)
        self.asin = self._extract_asin()
        self.title = self.asin  # Will be updated if metadata found
        self.status = "Ready"
        self.selected = True
        self.output_file = None
        
    def _extract_asin(self):
        """Extract ASIN from filename like B0BBSTYJ73_EBOK.azw"""
        base = os.path.splitext(self.filename)[0]
        if '_' in base:
            return base.split('_')[0]
        return base
    
    def has_voucher(self):
        """Check if this book has DRM voucher files."""
        vouchers = glob.glob(os.path.join(self.folder, "*.drm-voucher*"))
        return len(vouchers) > 0
    
    def get_related_files(self):
        """Get all related files for KFX packaging."""
        files = [self.main_file]
        for f in os.listdir(self.folder):
            f_path = os.path.join(self.folder, f)
            if f_path == self.main_file:
                continue
            if f.endswith(('.res', '.phl', '.md', '.mbpv2')) or 'drm-voucher' in f:
                files.append(f_path)
        return files


class LogRedirector:
    """Redirects print statements to the log queue."""
    def __init__(self, log_queue):
        self.log_queue = log_queue
        self.original_stdout = sys.stdout
        
    def write(self, text):
        if text.strip():
            self.log_queue.put(text.strip())
        self.original_stdout.write(text)
        
    def flush(self):
        self.original_stdout.flush()


class KindleDRMApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        self.title("Kindle DRM Removal Tool")
        self.geometry("900x700")
        self.minsize(800, 600)
        
        # State
        self.books = []
        self.log_queue = queue.Queue()
        self.processing = False
        self.keys = []
        self.key_files = []
        
        # Default paths
        self.content_dir = self._find_kindle_content()
        self.output_dir = os.path.join(PROJECT_ROOT, 'Decrypted_Books')
        
        # Setup UI
        self._create_widgets()
        self._load_keys()
        
        # Start log polling
        self._poll_log_queue()
        
        # Auto-scan if content dir found
        if self.content_dir:
            self.after(500, self._scan_books)
    
    def _find_kindle_content(self):
        """Find the My Kindle Content folder."""
        docs_path = os.path.expanduser('~\\Documents\\My Kindle Content')
        if os.path.exists(docs_path):
            return docs_path
        return None
    
    def _load_keys(self):
        """Load Kindle decryption keys."""
        if not DEDRM_AVAILABLE:
            self._log(f"⚠️ DeDRM not available: {DEDRM_ERROR}")
            return
        
        try:
            self.keys = kindlekey.kindlekeys()
            self._log(f"🔑 Found {len(self.keys)} decryption key(s)")
        except Exception as e:
            self._log(f"⚠️ Error loading keys: {e}")
    
    def _create_widgets(self):
        """Build the UI."""
        # Main container with padding
        self.main_frame = ctk.CTkFrame(self)
        self.main_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # === TOP SECTION: Folder Selection ===
        self.folder_frame = ctk.CTkFrame(self.main_frame)
        self.folder_frame.pack(fill="x", padx=5, pady=5)
        
        # Content folder row
        ctk.CTkLabel(self.folder_frame, text="📁 Kindle Content:", width=120, anchor="w").grid(row=0, column=0, padx=5, pady=5)
        self.content_entry = ctk.CTkEntry(self.folder_frame, width=500)
        self.content_entry.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        if self.content_dir:
            self.content_entry.insert(0, self.content_dir)
        ctk.CTkButton(self.folder_frame, text="Browse", width=80, command=self._browse_content).grid(row=0, column=2, padx=5, pady=5)
        ctk.CTkButton(self.folder_frame, text="Scan", width=60, command=self._scan_books).grid(row=0, column=3, padx=5, pady=5)
        
        # Output folder row
        ctk.CTkLabel(self.folder_frame, text="📂 Output Folder:", width=120, anchor="w").grid(row=1, column=0, padx=5, pady=5)
        self.output_entry = ctk.CTkEntry(self.folder_frame, width=500)
        self.output_entry.grid(row=1, column=1, padx=5, pady=5, sticky="ew")
        self.output_entry.insert(0, self.output_dir)
        ctk.CTkButton(self.folder_frame, text="Browse", width=80, command=self._browse_output).grid(row=1, column=2, padx=5, pady=5)
        ctk.CTkButton(self.folder_frame, text="Open", width=60, command=self._open_output).grid(row=1, column=3, padx=5, pady=5)
        
        self.folder_frame.columnconfigure(1, weight=1)
        
        # === MIDDLE SECTION: Book List ===
        self.list_frame = ctk.CTkFrame(self.main_frame)
        self.list_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        # List header
        header_frame = ctk.CTkFrame(self.list_frame, fg_color="transparent")
        header_frame.pack(fill="x", padx=5, pady=5)
        
        ctk.CTkLabel(header_frame, text="📚 Books Found:", font=("", 14, "bold")).pack(side="left")
        self.book_count_label = ctk.CTkLabel(header_frame, text="0 books")
        self.book_count_label.pack(side="left", padx=10)
        
        ctk.CTkButton(header_frame, text="Select All", width=80, command=self._select_all).pack(side="right", padx=2)
        ctk.CTkButton(header_frame, text="Deselect All", width=80, command=self._deselect_all).pack(side="right", padx=2)
        
        # Scrollable book list
        self.book_list_frame = ctk.CTkScrollableFrame(self.list_frame, height=200)
        self.book_list_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        self.book_checkboxes = []
        self.book_status_labels = []
        
        # === PROGRESS SECTION ===
        self.progress_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.progress_frame.pack(fill="x", padx=5, pady=5)
        
        self.progress_label = ctk.CTkLabel(self.progress_frame, text="Ready")
        self.progress_label.pack(anchor="w")
        
        self.progress_bar = ctk.CTkProgressBar(self.progress_frame, width=400)
        self.progress_bar.pack(fill="x", pady=5)
        self.progress_bar.set(0)
        
        # === LOG SECTION ===
        self.log_frame = ctk.CTkFrame(self.main_frame)
        self.log_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        ctk.CTkLabel(self.log_frame, text="📝 Log:", font=("", 12, "bold")).pack(anchor="w", padx=5, pady=2)
        
        self.log_text = ctk.CTkTextbox(self.log_frame, height=150, state="disabled")
        self.log_text.pack(fill="both", expand=True, padx=5, pady=5)
        
        # === BOTTOM SECTION: Action Buttons ===
        self.action_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.action_frame.pack(fill="x", padx=5, pady=10)
        
        self.start_button = ctk.CTkButton(
            self.action_frame, 
            text="▶️  Start Processing", 
            font=("", 14, "bold"),
            height=40,
            command=self._start_processing
        )
        self.start_button.pack(side="left", padx=5)
        
        self.stop_button = ctk.CTkButton(
            self.action_frame,
            text="⏹️  Stop",
            height=40,
            fg_color="darkred",
            hover_color="red",
            command=self._stop_processing,
            state="disabled"
        )
        self.stop_button.pack(side="left", padx=5)
        
        # Format selector
        ctk.CTkLabel(self.action_frame, text="Format:").pack(side="right", padx=5)
        self.format_var = ctk.StringVar(value="auto")
        self.format_menu = ctk.CTkOptionMenu(
            self.action_frame,
            values=["auto", "epub", "pdf"],
            variable=self.format_var,
            width=100
        )
        self.format_menu.pack(side="right", padx=5)
        
        # Initial log
        self._log("🚀 Kindle DRM Removal Tool ready")
        if not DEDRM_AVAILABLE:
            self._log("⚠️ Warning: DeDRM library not loaded properly")
        
        calibre = find_calibre_debug()
        if calibre:
            self._log(f"✅ Calibre found: {calibre}")
        else:
            self._log("⚠️ Calibre not found - conversion will fail")
    
    def _log(self, message):
        """Add message to log."""
        self.log_text.configure(state="normal")
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.insert("end", f"[{timestamp}] {message}\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")
    
    def _poll_log_queue(self):
        """Poll log queue and update UI."""
        try:
            while True:
                message = self.log_queue.get_nowait()
                self._log(message)
        except queue.Empty:
            pass
        self.after(100, self._poll_log_queue)
    
    def _browse_content(self):
        """Browse for Kindle content folder."""
        folder = filedialog.askdirectory(title="Select Kindle Content Folder")
        if folder:
            self.content_entry.delete(0, "end")
            self.content_entry.insert(0, folder)
            self.content_dir = folder
            self._scan_books()
    
    def _browse_output(self):
        """Browse for output folder."""
        folder = filedialog.askdirectory(title="Select Output Folder")
        if folder:
            self.output_entry.delete(0, "end")
            self.output_entry.insert(0, folder)
            self.output_dir = folder
    
    def _open_output(self):
        """Open output folder in explorer."""
        output = self.output_entry.get()
        if os.path.exists(output):
            os.startfile(output)
        else:
            os.makedirs(output, exist_ok=True)
            os.startfile(output)
    
    def _scan_books(self):
        """Scan for Kindle books."""
        content_dir = self.content_entry.get()
        if not content_dir or not os.path.exists(content_dir):
            self._log("❌ Invalid content folder")
            return
        
        self._log(f"🔍 Scanning {content_dir}...")
        
        # Clear existing
        self.books = []
        for widget in self.book_list_frame.winfo_children():
            widget.destroy()
        self.book_checkboxes = []
        self.book_status_labels = []
        
        # Find books
        for root, dirs, files in os.walk(content_dir):
            for file in files:
                if file.lower().endswith(('.azw', '.azw3', '.kfx')):
                    # Skip if it's a resource file
                    if '.res' in file.lower() or file.startswith('CR!'):
                        continue
                    
                    full_path = os.path.join(root, file)
                    book = KindleBook(full_path, root)
                    
                    # Check if already processed
                    output_dir = self.output_entry.get()
                    possible_outputs = [
                        os.path.join(output_dir, f"{book.asin}_EBOK.epub"),
                        os.path.join(output_dir, f"{book.asin}_EBOK.pdf"),
                        os.path.join(output_dir, f"{book.asin}.epub"),
                        os.path.join(output_dir, f"{book.asin}.pdf"),
                    ]
                    if any(os.path.exists(p) for p in possible_outputs):
                        book.status = "✅ Done"
                        book.selected = False
                    
                    self.books.append(book)
        
        # Update UI
        self._update_book_list()
        self._log(f"📚 Found {len(self.books)} book(s)")
    
    def _update_book_list(self):
        """Update the book list UI."""
        for widget in self.book_list_frame.winfo_children():
            widget.destroy()
        self.book_checkboxes = []
        self.book_status_labels = []
        
        for i, book in enumerate(self.books):
            row_frame = ctk.CTkFrame(self.book_list_frame, fg_color="transparent")
            row_frame.pack(fill="x", pady=2)
            
            var = ctk.BooleanVar(value=book.selected)
            cb = ctk.CTkCheckBox(row_frame, text="", variable=var, width=20,
                                command=lambda idx=i, v=var: self._toggle_book(idx, v))
            cb.pack(side="left", padx=5)
            self.book_checkboxes.append(var)
            
            # Book info
            drm_indicator = "🔒" if book.has_voucher() else "📖"
            info_text = f"{drm_indicator} {book.asin} - {book.filename}"
            ctk.CTkLabel(row_frame, text=info_text, anchor="w").pack(side="left", padx=5, fill="x", expand=True)
            
            # Status
            status_label = ctk.CTkLabel(row_frame, text=book.status, width=100)
            status_label.pack(side="right", padx=5)
            self.book_status_labels.append(status_label)
        
        self.book_count_label.configure(text=f"{len(self.books)} books")
    
    def _toggle_book(self, idx, var):
        """Toggle book selection."""
        self.books[idx].selected = var.get()
    
    def _select_all(self):
        """Select all books."""
        for i, book in enumerate(self.books):
            book.selected = True
            self.book_checkboxes[i].set(True)
    
    def _deselect_all(self):
        """Deselect all books."""
        for i, book in enumerate(self.books):
            book.selected = False
            self.book_checkboxes[i].set(False)
    
    def _start_processing(self):
        """Start processing selected books."""
        selected = [b for b in self.books if b.selected]
        if not selected:
            messagebox.showwarning("No Selection", "Please select at least one book to process.")
            return
        
        self.processing = True
        self.start_button.configure(state="disabled")
        self.stop_button.configure(state="normal")
        
        # Run in thread
        thread = threading.Thread(target=self._process_books, args=(selected,))
        thread.daemon = True
        thread.start()
    
    def _stop_processing(self):
        """Stop processing."""
        self.processing = False
        self._log("⏹️ Stopping...")
    
    def _process_books(self, books):
        """Process books in background thread."""
        output_dir = self.output_entry.get()
        os.makedirs(output_dir, exist_ok=True)
        
        format_choice = self.format_var.get()
        total = len(books)
        success_count = 0
        
        # Prepare key files
        temp_dir = tempfile.mkdtemp()
        key_files = []
        try:
            for i, key in enumerate(self.keys):
                key_file_path = os.path.join(temp_dir, f"kindlekey_{i}.k4i")
                with open(key_file_path, 'w') as f:
                    f.write(json.dumps(key))
                key_files.append(key_file_path)
            
            for i, book in enumerate(books):
                if not self.processing:
                    break
                
                # Update UI
                self.after(0, lambda b=book, idx=i: self._update_book_status(b, idx, "⏳ Processing..."))
                self.after(0, lambda p=(i/total): self.progress_bar.set(p))
                self.after(0, lambda b=book: self.progress_label.configure(text=f"Processing: {b.asin}"))
                
                self._log(f"📖 Processing: {book.filename}")
                
                try:
                    # Step 1: Create KFX-ZIP if needed
                    if book.has_voucher():
                        kfx_zip_path = self._create_kfx_zip(book, temp_dir)
                    else:
                        kfx_zip_path = book.main_file
                    
                    # Step 2: Decrypt
                    decrypted_path = self._decrypt_book(kfx_zip_path, output_dir, key_files)
                    
                    if decrypted_path:
                        self._log(f"  ✅ Decrypted: {os.path.basename(decrypted_path)}")
                        
                        # Step 3: Convert
                        success, result, fmt = convert_book(
                            decrypted_path, 
                            output_dir, 
                            format_choice,
                            callback=lambda msg: self._log(f"  {msg}")
                        )
                        
                        if success:
                            self._log(f"  ✅ Converted to {fmt.upper()}: {os.path.basename(result)}")
                            book.output_file = result
                            book.status = "✅ Done"
                            success_count += 1
                        else:
                            self._log(f"  ❌ Conversion failed: {result}")
                            book.status = "❌ Convert Failed"
                    else:
                        self._log(f"  ❌ Decryption failed")
                        book.status = "❌ Decrypt Failed"
                    
                except Exception as e:
                    self._log(f"  ❌ Error: {e}")
                    book.status = "❌ Error"
                
                self.after(0, lambda b=book, idx=i: self._update_book_status(b, idx, book.status))
            
            # Done
            self.after(0, lambda: self.progress_bar.set(1))
            self.after(0, lambda: self.progress_label.configure(text=f"Done: {success_count}/{total} successful"))
            self._log(f"🎉 Processing complete: {success_count}/{total} books converted successfully")
            
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)
            self.processing = False
            self.after(0, lambda: self.start_button.configure(state="normal"))
            self.after(0, lambda: self.stop_button.configure(state="disabled"))
    
    def _create_kfx_zip(self, book, temp_dir):
        """Create a KFX-ZIP from book files."""
        zip_path = os.path.join(temp_dir, f"{book.asin}.kfx-zip")
        
        with ZipFile(zip_path, 'w', ZIP_STORED) as zf:
            for f_path in book.get_related_files():
                zf.write(f_path, os.path.basename(f_path))
        
        return zip_path
    
    def _decrypt_book(self, input_path, output_dir, key_files):
        """Decrypt a book using DeDRM."""
        if not DEDRM_AVAILABLE:
            return None
        
        try:
            result = k4mobidedrm.decryptBook(input_path, output_dir, key_files, [], [], [])
            
            if result == 0:
                # Find the output file
                base_name = os.path.splitext(os.path.basename(input_path))[0]
                pattern = os.path.join(output_dir, "*_nodrm*")
                files = glob.glob(pattern)
                if files:
                    # Get newest file
                    newest = max(files, key=os.path.getmtime)
                    return newest
            
            return None
        except Exception as e:
            self._log(f"  Decrypt error: {e}")
            return None
    
    def _update_book_status(self, book, idx, status):
        """Update book status in UI."""
        if idx < len(self.book_status_labels):
            self.book_status_labels[idx].configure(text=status)


def main():
    app = KindleDRMApp()
    app.mainloop()


if __name__ == "__main__":
    main()
