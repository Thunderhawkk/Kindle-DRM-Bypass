# Kindle DRM Removal Tool

This tool removes DRM from your Kindle books (`.azw` files) using your installed Kindle for PC keys, and converts them to EPUB, PDF, and TXT formats (requires Calibre).

## Requirements

1.  **Python 3.7+**
2.  **Kindle for PC** installed and authorized.
    *   *Important:* You must be able to open and read the books in Kindle for PC on this computer.
3.  **Calibre** (optional, for conversion to EPUB/PDF).
    *   If installed, the tool will automatically convert the files.

## Installation

1.  Open a terminal in this folder.
2.  Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```

## Usage

Run the script:

```bash
python remove_kindle_drm.py
```

The tool will:
1.  Automatically find your "My Kindle Content" folder (in Documents).
2.  Retrieve your decryption keys from Kindle for PC.
3.  Decrypt all `.azw` and `.azw3` files.
4.  Convert them to EPUB, PDF, and TXT (if Calibre is found).
5.  Save the results in the `Decrypted_Books` folder.

## Troubleshooting

*   **"Found 0 keys"**:
    *   The script will prompt you to enter a **Kindle Serial Number** (if you have a physical device) or the path to a `.kinf` file.
    *   If you don't have a physical Kindle, you may need to downgrade Kindle for PC to version 1.24 or older for key detection to work automatically.
*   **"Calibre not found"**: If you want conversion, install Calibre or add `ebook-convert` to your system PATH.
*   **"Could not find My Kindle Content"**: If your content is in a custom location, drag and drop the folder into the terminal when prompted.
