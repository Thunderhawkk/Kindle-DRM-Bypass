
import os
import glob

def find_kindle_keys():
    user_profile = os.environ['USERPROFILE']
    local_appdata = os.environ['LOCALAPPDATA']
    roaming_appdata = os.environ['APPDATA']
    
    search_roots = [
        os.path.join(local_appdata, 'Amazon'),
        os.path.join(roaming_appdata, 'Amazon'),
        os.path.join(local_appdata, 'Packages'), # Windows Store apps
        os.path.join(user_profile, 'Documents', 'My Kindle Content'), 
    ]
    
    print("Searching for Kindle key files (.kinf, .kinf2011, .kinf2018, *.voucher)...")
    
    found_files = []
    
    for root_dir in search_roots:
        if not os.path.exists(root_dir):
            continue
            
        print(f"Scanning: {root_dir}")
        for root, dirs, files in os.walk(root_dir):
            for file in files:
                if 'kinf' in file.lower() or 'voucher' in file.lower() or 'kindle.info' in file.lower():
                    full_path = os.path.join(root, file)
                    print(f"  FOUND: {full_path}")
                    found_files.append(full_path)

    if not found_files:
        print("No Kindle key files found.")
    else:
        print(f"Total found: {len(found_files)}")

if __name__ == "__main__":
    find_kindle_keys()
