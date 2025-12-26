# Kindle DRM Removal Tool

A tool to remove DRM from your Kindle books and convert them to EPUB or PDF format.

![Python](https://img.shields.io/badge/Python-3.7+-blue)
![Platform](https://img.shields.io/badge/Platform-Windows-lightgrey)

## ⚠️ Important: Kindle Version Requirement

> **You MUST use Kindle for PC version 1.26 Build 55076**
> 
> This is the only tested version that works for automatic key extraction. Newer versions of Kindle for PC use different encryption that prevents key extraction.
>
> [Download Kindle 1.26.55076](https://archive.org/details/kindle-for-pc-1-26-55076) (Archive.org)

---

## Features

- 🖥️ **GUI Application** - Easy-to-use graphical interface
- 📚 **Bulk Processing** - Process multiple books at once
- 🔍 **Smart Format Detection** - Automatically chooses best output format
  - Fixed-layout books → **PDF** (extracted directly)
  - Regular ebooks → **EPUB**
- ✅ **Progress Tracking** - Real-time status and logging

---

## Requirements

| Requirement | Details |
|-------------|---------|
| **Python** | 3.7 or higher |
| **Kindle for PC** | Version **1.26 Build 55076** (see note above) |
| **Calibre** | Required for format conversion |
| **KFX Input Plugin** | Install in Calibre for KFX support |

---

## Installation

### 1. Install Python Dependencies

```bash
pip install -r requirements.txt
```

### 2. Install Calibre

Download from [calibre-ebook.com](https://calibre-ebook.com/download)

### 3. Install KFX Input Plugin (in Calibre)

1. Open Calibre → Preferences → Plugins
2. Click "Get new plugins"
3. Search for "KFX Input" and install it
4. Restart Calibre

### 4. Setup Kindle for PC

1. Install **Kindle for PC version 1.26.55076**
2. Sign in with your Amazon account
3. Download the books you want to convert
4. Open each book at least once (this creates the decryption keys)

---

## Usage

### GUI Mode (Recommended)

```bash
python kindle_drm_gui.py
```

**Steps:**
1. The tool auto-detects your `My Kindle Content` folder
2. Click **Scan** to find all Kindle books
3. Select the books you want to process
4. Choose format: `auto` (recommended), `epub`, or `pdf`
5. Click **Start Processing**
6. Find converted files in the `Decrypted_Books` folder

### Command Line Mode

```bash
python remove_kindle_drm.py
```

This runs in interactive mode and processes all books automatically.

---

## Output Formats

| Book Type | Output | Method |
|-----------|--------|--------|
| Fixed-layout (textbooks, PDFs) | `.pdf` | Extracted using KFX Input CLI |
| Regular ebooks | `.epub` | Converted via Calibre |

---

## Troubleshooting

### "Found 0 keys"
- Make sure you're using **Kindle for PC version 1.26.55076**
- Open each book in Kindle at least once before running the tool
- Try entering a Kindle Serial Number if you have a physical Kindle device

### "DeDRM not available: No module named 'Crypto'"
```bash
pip install pycryptodome
```

### "Calibre not found"
- Install Calibre from [calibre-ebook.com](https://calibre-ebook.com/)
- Or add `C:\Program Files\Calibre2` to your system PATH

### "Decryption failed" for all books
- Verify Kindle version is exactly 1.26.55076
- Reinstall Kindle and re-download your books
- Check that you can read the books in the Kindle app

### Books convert to empty files
- Fixed-layout books (textbooks) cannot be converted to TXT
- Use PDF output for these books (the GUI does this automatically with `auto` format)

---

## Project Structure

```
E-Book DRM/
├── kindle_drm_gui.py      # GUI application
├── remove_kindle_drm.py   # Command-line tool
├── convert_kfx.py         # Format conversion module
├── DeDRM_tools/           # DeDRM library
├── Decrypted_Books/       # Output folder
└── README.md
```

---

## Legal Notice

This tool is for personal backup purposes only. Only use it with books you have legally purchased.
