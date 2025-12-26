
import os
import glob
import binascii

def inspect_vouchers():
    content_dir = os.path.expanduser('~\\Documents\\My Kindle Content')
    if not os.path.exists(content_dir):
        # Try to find it again recursively or use specific known path from logs
        # The logs showed C:\Users\ThundeR\Documents\My Kindle Content correctly
        pass
    
    print(f"Scanning {content_dir} for vouchers...")
    vouchers = []
    for root, dirs, files in os.walk(content_dir):
        for file in files:
            if 'drm-voucher' in file:
                vouchers.append(os.path.join(root, file))
    
    if not vouchers:
        print("No vouchers found.")
        return

    print(f"Found {len(vouchers)} vouchers. Inspecting first 3:")
    for v in vouchers[:3]:
        print(f"\nFile: {os.path.basename(v)}")
        try:
            with open(v, 'rb') as f:
                header = f.read(32)
                print(f"HEX: {binascii.hexlify(header)}")
                print(f"ASCII: {header}")
        except Exception as e:
            print(f"Error reading: {e}")

if __name__ == "__main__":
    inspect_vouchers()
