
import sys
import os
import tempfile
import json
import glob
import shutil
import traceback
from zipfile import ZipFile, ZIP_STORED

# Add DeDRM_tools to sys.path (for package resolution)
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
TOOLS_PATH = os.path.join(PROJECT_ROOT, 'DeDRM_tools')
if TOOLS_PATH not in sys.path:
    sys.path.append(TOOLS_PATH)

PLUGIN_PATH = os.path.join(TOOLS_PATH, 'DeDRM_plugin')

# Shim all modules in DeDRM_plugin to make them available as top-level imports
# This is necessary because the DeDRM scripts are written to run as plugins or standalone scripts
# with specific legacy import behavior (mixed absolute/relative).
try:
    for filename in os.listdir(PLUGIN_PATH):
        if filename.endswith(".py") and not filename.startswith("__"):
            module_name = filename[:-3]
            try:
                # Import via package
                full_module_name = f"DeDRM_plugin.{module_name}"
                __import__(full_module_name)
                # Alias as top-level module
                if module_name not in sys.modules:
                    sys.modules[module_name] = sys.modules[full_module_name]
            except Exception as e:
                # Some modules might fail to import if they have other deps, but we try best effort
                # print(f"Warning: Failed to shim {module_name}: {e}")
                pass

    import DeDRM_plugin.kindlekey as kindlekey
    import DeDRM_plugin.k4mobidedrm as k4mobidedrm

except ImportError as e:
    print("Error importing DeDRM modules.")
    print(f"Details: {e}")
    sys.exit(1)

def get_kindle_content_dir():
    # User specific path or standard default
    # You can modify this path if your content checks are different
    docs_path = os.path.expanduser('~\\Documents\\My Kindle Content')
    if os.path.exists(docs_path):
        return docs_path
    
    # Fallback to checking current directory
    if os.path.exists("My Kindle Content"):
        return os.path.abspath("My Kindle Content")

    return None

def main():
    print("--- Kindle DRM Removal Tool ---")
    
    # 1. content detection
    content_dir = get_kindle_content_dir()
    if not content_dir:
        # Default fallback for the user if they run it in the folder itself
        print("Could not find 'My Kindle Content' in Documents.")
        print("Please drag and drop your 'My Kindle Content' folder here and press Enter:")
        try:
            inp = input().strip()
            if inp and os.path.exists(inp):
                content_dir = inp.strip('"').strip("'")  # Remove quotes if added by shell
            else:
                print("Invalid folder. Exiting.")
                return
        except EOFError:
            print("No input (non-interactive mode). Exiting.")
            return

    print(f"Target Content Directory: {content_dir}")
    
    # 2. Output setup
    output_dir = os.path.join(PROJECT_ROOT, 'Decrypted_Books')
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    print(f"Output Directory: {output_dir}")

    # 3. Fetch Keys
    print("Retrieving Kindle keys...")
    keys = []
    try:
        keys = kindlekey.kindlekeys()
        print(f"Found {len(keys)} keys.")
    except Exception as e:
        print(f"Error retrieving keys: {e}")

    # Fallback if no keys found
    manual_serials = []
    if not keys:
        print("\n[!] No keys found automatically.")
        print("This can happen if Kindle for PC is not installed or using a newer version preventing key extraction.")
        print("If you have a physical Kindle device, you can enter its Serial Number.")
        print("If you know the path to your 'kindle.info' or '.kinf' file, you can enter that too.")
        
        print("\nEnter Serial Number or Key File Path (or press Enter to skip):")
        inp = input().strip()
        if inp:
            if os.path.exists(inp):
                # It's a file
                try:
                    # Try to use it as a DB file
                    # We need to use kindlekey logic manually if we want to extract from a specific file
                    # But kindlekey.kindlekeys() takes a list of files!
                    print(f"Trying to extract key from: {inp}")
                    new_keys = kindlekey.kindlekeys([inp])
                    if new_keys:
                        keys.extend(new_keys)
                        print(f"Successfully extracted {len(new_keys)} key(s).")
                    else:
                        print("No keys found in that file.")
                except Exception as ex:
                    print(f"Failed to read key file: {ex}")
            else:
                # Assume it's a serial number
                # Serial numbers are just strings passed to decryptBook
                print(f"Using Serial Number: {inp}")
                manual_serials.append(inp)

    if not keys and not manual_serials:
         print("[!] No decryption keys available. Decryption will likely fail.")
    manual_pids = []
    
    print("\n[!] No keys found automatically.")
    print("This can happen if Kindle for PC is not installed or using a newer version preventing key extraction.")
    print("If you have a physical Kindle device, you can enter its Serial Number.")
    print("If you know the path to your 'kindle.info' or '.kinf' file, you can enter that too.")
    print("For KFX books from certain tools, you can enter 'DSN$secret_key:SECRET'.")
    
    manual_input = input("Enter Serial, DSN$secret_key, or Key File (or press Enter to skip):\n").strip()
    if manual_input:
        if os.path.isfile(manual_input):
            # It's a file
            try:
                print(f"Trying to extract key from: {manual_input}")
                new_keys = kindlekey.kindlekeys([manual_input])
                if new_keys:
                    keys.extend(new_keys)
                    print(f"Successfully extracted {len(new_keys)} key(s).")
                else:
                    print("No keys found in that file.")
            except Exception as ex:
                print(f"Failed to read key file: {ex}")
        elif "$secret_key:" in manual_input:
             # It's a KFX specific DSN/Secret pair, must be passed as PID to avoid hashing
             print(f"Using KFX Key: {manual_input}")
             manual_pids = [manual_input.encode('utf-8')]
        else:
            # Assume it's a serial number
            print(f"Using Serial Number: {manual_input}")
            manual_serials.append(manual_input)

    if not keys and not manual_serials and not manual_pids:
         print("[!] No decryption keys or serials/PIDs available. Decryption will likely fail.")
         print("Proceeding anyway just in case...")
    
    # 4. Write keys to temp files
    key_files = []
    temp_dir = tempfile.mkdtemp()
    try:
        for i, key in enumerate(keys):
            key_file_path = os.path.join(temp_dir, f"kindlekey_{i}.k4i")
            with open(key_file_path, 'w') as f:
                f.write(json.dumps(key))
            key_files.append(key_file_path)
        
        # 5. Find and Process Files
        TARGET_DIR = content_dir # Renamed for clarity as per user's snippet
        print(f"Searching for Kindle files in: {TARGET_DIR}")
        kindle_files = []
        for root, dirs, files in os.walk(TARGET_DIR):
            for file in files:
                if file.lower().endswith(('.azw', '.azw3', '.kfx', '.mobi', '.prc')):
                    kindle_files.append(os.path.join(root, file))
        
        if not kindle_files:
            print("No Kindle files found.")
            sys.exit(0)

        print(f"Found {len(kindle_files)} Kindle files.")
        
        success_count = 0
        
        for infile in kindle_files:
            filename = os.path.basename(infile)
            print(f"Processing: {filename}")
            
            # Check for KFX situation (voucher + main file)
            file_dir = os.path.dirname(infile)
            base_name = os.path.splitext(filename)[0]
            
            # Common pattern: B0B4BG83WF_EBOK.azw and amzn1.drm-voucher...
            # The voucher might not share the exact name.
            # Usually strict KFX has files in a folder like "Author_BookName_B0123.../"
            # We can check if there are any .drm-voucher files in the folder.
            vouchers = glob.glob(os.path.join(file_dir, "*.drm-voucher*"))
            
            infile_path = infile
            temp_kfx_zip = None
            is_kfx = infile.lower().endswith('.kfx') or (infile.lower().endswith('.azw') and vouchers) # .azw can be KFX too

            if is_kfx:
                print("  [INFO] KFX Voucher detected. Creating temporary .kfx-zip...")
                try:
                    # Create temp zip
                    fd, temp_kfx_zip = tempfile.mkstemp(suffix=".kfx-zip")
                    os.close(fd)
                    
                    with ZipFile(temp_kfx_zip, 'w', ZIP_STORED) as zf:
                        # Add the main book file
                        zf.write(infile, filename)
                        
                        # Add vouchers
                        for v in vouchers:
                            zf.write(v, os.path.basename(v))
                            
                        # Add other potential KFX parts (.res, .phl, .md)
                        # We iterate files in dir to find related ones
                        for f in os.listdir(file_dir):
                            f_path = os.path.join(file_dir, f)
                            if f_path == infile or f_path in vouchers:
                                continue
                            if f.lower().endswith(('.res', '.phl', '.md', '.mbpv2')):
                                zf.write(f_path, f)
                                
                    infile_path = temp_kfx_zip
                    print(f"  [INFO] Created {os.path.basename(temp_kfx_zip)}")
                except Exception as e:
                    print(f"  [WARN] Failed to create kfx-zip: {e}")
                    if temp_kfx_zip and os.path.exists(temp_kfx_zip):
                        os.remove(temp_kfx_zip)
                    temp_kfx_zip = None

            
            # The decryptBook function signature:
            # decryptBook(infile, outdir, kDatabaseFiles, androidFiles, serials, pids)
            # kDatabaseFiles is list of paths to key files
            
            try:
                # empty lists for android files... pass manual_serials, and now manual_pids
                # decryptBook returns 0 on success, 1 on failure (if it catches exception), or raises Exception
                res = k4mobidedrm.decryptBook(infile_path, output_dir, key_files, [], manual_serials, manual_pids)
                
                # Based on k4mobidedrm.py reading:
                # It catches exceptions and returns 1.
                if res != 0:
                     print(f"  [FAILED] {filename}: Decryption failed inside plugin.")
                     continue
                
                # Check for output file - look for any nodrm files, including temp-named ones
                base_name = os.path.splitext(filename)[0]
                # For KFX files, the output is saved as tmpXXXX_nodrm.kfx-zip 
                all_nodrm_files = glob.glob(os.path.join(output_dir, "*_nodrm*"))
                
                # Find the most recently created one (should be our output)
                if all_nodrm_files:
                    newest_file = max(all_nodrm_files, key=os.path.getmtime)
                    # Rename to original book name if it has a temp name
                    if 'tmp' in os.path.basename(newest_file).lower():
                        ext = os.path.splitext(newest_file)[1]
                        new_name = os.path.join(output_dir, f"{base_name}_nodrm{ext}")
                        if not os.path.exists(new_name):
                            try:
                                os.rename(newest_file, new_name)
                                newest_file = new_name
                            except:
                                pass  # Keep temp name if rename fails
                    print(f"  [OK] Decryption successful: {os.path.basename(newest_file)}")
                    success_count += 1
                    convert_book(newest_file)
                else:
                    print(f"  [FAILED] {filename}: Output file not found even though no error reported?")
                

            except Exception as e:
                print(f"  [FAILED] {filename}: {e}")
                # traceback.print_exc()
            finally:
                if temp_kfx_zip and os.path.exists(temp_kfx_zip):
                    try:
                        os.remove(temp_kfx_zip)
                    except:
                        pass

        print("---------------------------------------------------")
        print(f"Done. Successfully processed {success_count} / {len(kindle_files)} files.")
        print(f"Decrypted books are in: {output_dir}")

    finally:
        # Cleanup temp key files
        shutil.rmtree(temp_dir)

def find_calibre_convert():
    # Check PATH
    if shutil.which("ebook-convert"):
        return "ebook-convert"
    
    # Check standard Windows paths
    paths = [
        r"C:\Program Files\Calibre2\ebook-convert.exe",
        r"C:\Program Files (x86)\Calibre2\ebook-convert.exe"
    ]
    for p in paths:
        if os.path.exists(p):
            return p
    return None

def convert_book(input_file):
    converter = find_calibre_convert()
    if not converter:
        print("  [WARN] Calibre's ebook-convert not found. Skipping conversion.")
        return

    formats = ['epub', 'pdf', 'txt']
    base_name = os.path.splitext(input_file)[0]
    
    for fmt in formats:
        output_file = f"{base_name}.{fmt}"
        if os.path.exists(output_file):
            continue
            
        print(f"  Converting to {fmt.upper()}...")
        try:
            # Run ebook-convert
            # cmd: ebook-convert input_file output_file
            import subprocess
            cmd = [converter, input_file, output_file]
            # Suppress output unless error
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                print(f"  [OK] Created {os.path.basename(output_file)}")
            else:
                print(f"  [FAIL] Conversion to {fmt} failed.")
                # print(result.stderr) # Uncomment for debug
        except Exception as e:
            print(f"  [ERROR] converting to {fmt}: {e}")

if __name__ == "__main__":
    main()
