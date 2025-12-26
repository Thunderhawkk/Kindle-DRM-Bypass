"""
KFX Conversion Module

Handles detection of book types and conversion to appropriate formats.
- Fixed-layout/PDF books -> Extract PDF using KFX Input CLI
- Regular ebooks -> Convert to EPUB using Calibre
"""

import os
import subprocess
import shutil
from zipfile import ZipFile


def find_calibre_debug():
    """Find calibre-debug executable."""
    if shutil.which("calibre-debug"):
        return "calibre-debug"
    
    paths = [
        r"C:\Program Files\Calibre2\calibre-debug.exe",
        r"C:\Program Files (x86)\Calibre2\calibre-debug.exe"
    ]
    for p in paths:
        if os.path.exists(p):
            return p
    return None


def find_ebook_convert():
    """Find ebook-convert executable."""
    if shutil.which("ebook-convert"):
        return "ebook-convert"
    
    paths = [
        r"C:\Program Files\Calibre2\ebook-convert.exe",
        r"C:\Program Files (x86)\Calibre2\ebook-convert.exe"
    ]
    for p in paths:
        if os.path.exists(p):
            return p
    return None


def detect_book_type(kfx_file):
    """
    Detect if a KFX file is fixed-layout (PDF-based) or reflowable.
    
    Returns: 'fixed_layout' or 'reflowable'
    """
    calibre_debug = find_calibre_debug()
    if not calibre_debug:
        return 'unknown'
    
    try:
        # Use KFX Input to get metadata
        cmd = [calibre_debug, '--run-plugin', 'KFX Input', '--', '-j', kfx_file]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        output = result.stdout + result.stderr
        
        # Check for fixed-layout indicators
        if 'yj_fixed_layout=1' in output or 'yj_textbook=1' in output or 'PDF content' in output:
            return 'fixed_layout'
        
        return 'reflowable'
    except Exception:
        return 'unknown'


def extract_pdf(kfx_file, output_dir, callback=None):
    """
    Extract PDF from a fixed-layout KFX file using KFX Input CLI.
    
    Returns: (success: bool, output_path: str or error_message: str)
    """
    calibre_debug = find_calibre_debug()
    if not calibre_debug:
        return False, "Calibre not found"
    
    base_name = os.path.splitext(os.path.basename(kfx_file))[0]
    # Remove _nodrm suffix for cleaner output name
    if base_name.endswith('_nodrm'):
        base_name = base_name[:-6]
    
    output_file = os.path.join(output_dir, f"{base_name}.pdf")
    
    if callback:
        callback(f"Extracting PDF from {os.path.basename(kfx_file)}...")
    
    try:
        cmd = [calibre_debug, '--run-plugin', 'KFX Input', '--', '-p', kfx_file, output_file]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        
        if result.returncode == 0 and os.path.exists(output_file):
            return True, output_file
        else:
            error = result.stderr or result.stdout or "Unknown error"
            return False, f"PDF extraction failed: {error[:200]}"
    except subprocess.TimeoutExpired:
        return False, "Timeout during PDF extraction"
    except Exception as e:
        return False, str(e)


def convert_to_epub(kfx_file, output_dir, callback=None):
    """
    Convert KFX file to EPUB using Calibre ebook-convert.
    
    Returns: (success: bool, output_path: str or error_message: str)
    """
    ebook_convert = find_ebook_convert()
    if not ebook_convert:
        return False, "Calibre ebook-convert not found"
    
    base_name = os.path.splitext(os.path.basename(kfx_file))[0]
    if base_name.endswith('_nodrm'):
        base_name = base_name[:-6]
    
    output_file = os.path.join(output_dir, f"{base_name}.epub")
    
    if callback:
        callback(f"Converting {os.path.basename(kfx_file)} to EPUB...")
    
    try:
        cmd = [ebook_convert, kfx_file, output_file]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        
        if result.returncode == 0 and os.path.exists(output_file):
            return True, output_file
        else:
            error = result.stderr or result.stdout or "Unknown error"
            return False, f"EPUB conversion failed: {error[:200]}"
    except subprocess.TimeoutExpired:
        return False, "Timeout during EPUB conversion"
    except Exception as e:
        return False, str(e)


def convert_book(kfx_file, output_dir, format_choice='auto', callback=None):
    """
    Smart conversion router - detects book type and converts to appropriate format.
    
    Args:
        kfx_file: Path to the decrypted .kfx-zip file
        output_dir: Directory to save converted file
        format_choice: 'auto', 'epub', or 'pdf'
        callback: Optional function to receive progress messages
    
    Returns: (success: bool, output_path: str or error_message: str, format_used: str)
    """
    if not os.path.exists(kfx_file):
        return False, f"File not found: {kfx_file}", None
    
    if format_choice == 'auto':
        if callback:
            callback("Detecting book type...")
        book_type = detect_book_type(kfx_file)
        
        if book_type == 'fixed_layout':
            if callback:
                callback("Fixed-layout book detected - extracting PDF...")
            success, result = extract_pdf(kfx_file, output_dir, callback)
            return success, result, 'pdf'
        else:
            if callback:
                callback("Reflowable book detected - converting to EPUB...")
            success, result = convert_to_epub(kfx_file, output_dir, callback)
            return success, result, 'epub'
    
    elif format_choice == 'pdf':
        success, result = extract_pdf(kfx_file, output_dir, callback)
        return success, result, 'pdf'
    
    elif format_choice == 'epub':
        success, result = convert_to_epub(kfx_file, output_dir, callback)
        return success, result, 'epub'
    
    return False, f"Unknown format choice: {format_choice}", None


if __name__ == "__main__":
    # Test
    import sys
    if len(sys.argv) > 1:
        test_file = sys.argv[1]
        print(f"Testing with: {test_file}")
        book_type = detect_book_type(test_file)
        print(f"Detected type: {book_type}")
