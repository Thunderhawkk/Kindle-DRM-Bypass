#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Engine to remove drm from Kindle KFX ebooks

#  2.0   - Python 3 for calibre 5.0
#  2.1   - Some fixes for debugging
#  2.1.1 - Whitespace!


import os, sys
import shutil
import traceback
import zipfile

from io import BytesIO


#@@CALIBRE_COMPAT_CODE@@


from ion import DrmIon, DrmIonVoucher



__license__ = 'GPL v3'
__version__ = '2.0'


class KFXZipBook:
    def __init__(self, infile):
        self.infile = infile
        self.voucher = None
        self.decrypted = {}

    def getPIDMetaInfo(self):
        return (None, None)

    def processBook(self, totalpids):
        with zipfile.ZipFile(self.infile, 'r') as zf:
            for filename in zf.namelist():
                with zf.open(filename) as fh:
                    data = fh.read(8)
                    if data != b'\xeaDRMION\xee':
                        continue
                    data += fh.read()
                    if self.voucher is None:
                        self.decrypt_voucher(totalpids)
                    print("Decrypting KFX DRMION: {0}".format(filename))
                    outfile = BytesIO()
                    DrmIon(BytesIO(data[8:-8]), lambda name: self.voucher).parse(outfile)
                    self.decrypted[filename] = outfile.getvalue()

        if not self.decrypted:
            print("The .kfx-zip archive does not contain an encrypted DRMION file")

    def decrypt_voucher(self, totalpids):
        with zipfile.ZipFile(self.infile, 'r') as zf:
            for info in zf.infolist():
                with zf.open(info.filename) as fh:
                    data = fh.read(4)
                    if data != b'\xe0\x01\x00\xea':
                        continue

                    data += fh.read()
                    if b'ProtectedData' in data:
                        break   # found DRM voucher
            else:
                raise Exception("The .kfx-zip archive contains an encrypted DRMION file without a DRM voucher")

        print("Decrypting KFX DRM voucher: {0}".format(info.filename))

        for pid in [''] + totalpids:
            # Belt and braces. PIDs should be unicode strings, but just in case...
            if isinstance(pid, bytes):
                pid = pid.decode('ascii')
            # Check for explicit DSN/Secret delimiter (used in some key extraction tools)
            # --------------------------------------------------------------------------------
            # STANDARD ATTEMPT: Check for combined keys (DSN$secret_key:SECRET) or legacy PIDs
            # --------------------------------------------------------------------------------
            
            # Check for explicit DSN/Secret delimiter
            if "$secret_key:" in pid:
                 raw_dsn, raw_secret = pid.split("$secret_key:", 1)
                 
                 # Prepare list of potential DSNs
                 # 1. Full DSN as provided
                 # 2. Shortened DSN (strip amzn1.drm-voucher.v1. prefix if present)
                 # 3. Uppercase versions of both (DSNs sometimes need to be upper)
                 dsn_candidates = [raw_dsn]
                 if "amzn1.drm-voucher.v1." in raw_dsn:
                     dsn_candidates.append(raw_dsn.replace("amzn1.drm-voucher.v1.", ""))
                 
                 dsns_to_try = []
                 for d in dsn_candidates:
                     dsns_to_try.append(d)
                     dsns_to_try.append(d.upper()) # Add UPPER version
                     
                 # Prepare list of potential Secrets
                 # 1. Hex decoded bytes
                 # 2. Raw string bytes
                 secrets_to_try = []
                 try:
                     import binascii
                     if len(raw_secret) in (32, 40):
                         secrets_to_try.append(binascii.unhexlify(raw_secret))
                 except:
                     pass
                 
                 if isinstance(raw_secret, str):
                     secrets_to_try.append(raw_secret.encode('ascii'))
                 elif isinstance(raw_secret, bytes):
                     secrets_to_try.append(raw_secret)

                 # Try all combinations
                 success = False
                 for d in dsns_to_try:
                     for s in secrets_to_try:
                         try:
                            # print(f"DEBUG: Trying DSN={d!r}, Secret={s[:4].hex() if isinstance(s, bytes) else s[:4]}...")
                            voucher = DrmIonVoucher(BytesIO(data), d, s)
                            voucher.parse()
                            voucher.decryptvoucher()
                            success = True
                            print(f"[DEBUG] Success with DSN: {d}, Secret len: {len(s)}")
                            break 
                         except Exception as e:
                            # print(f"DEBUG: Failed DSN={d} Err={e}")
                            pass
                     if success: break
                 
                 if success:
                     break
                 else:
                     continue

            for dsn_len,secret_len in [(0,0), (16,0), (16,40), (32,0), (32,40), (40,0), (40,40)]:
                if len(pid) == dsn_len + secret_len:
                    break       # split pid into DSN and account secret
            else:
                # If standard splitting failed, don't just "continue". 
                # We might have a situation where the User provided DSN and Secret as SEPARATE items in the 'pids' list.
                # Since we are inside a loop iterating 'pid' over 'totalpids', we can't easily check *other* pids here 
                # efficiently without re-looping, BUT 'kfxdedrm.py' is unstructured enough that we can add a fallback phase 
                # outside this loop? No, this function `decrypt_voucher` tries each PID. 
                #
                # Actually, the best place for "smart pairing" is AFTER the main loop if nothing worked.
                continue

            try:
                voucher = DrmIonVoucher(BytesIO(data), pid[:dsn_len], pid[dsn_len:])
                voucher.parse()
                voucher.decryptvoucher()
                break
            except:
                traceback.print_exc()
                pass
        else:
             # Loop `for pid in pids` finished without breaking (failure).
             # FALLBACK: Try Combinatorial Pairing of ALL provided PIDs
             # This handles cases where User entered DSN as one input and Secret as another.
             print("[DEBUG] Direct key match failed. Attempting smart pairing of separate inputs...")
             print(f"[DEBUG] Total PIDs received: {totalpids}")
             
             # Collect valid-looking DSNs and Secrets from the input list
             potential_dsns = []
             potential_secrets = []
             import binascii
             import re
             
             for p in totalpids:
                 if isinstance(p, bytes): p = p.decode('ascii', errors='ignore')
                 if not p: continue
                 
                 print(f"[DEBUG] Analyzing input: {p!r} (len={len(p)})")
                 
                 # DSN Heuristics - be very aggressive about extracting potential DSNs
                 
                 # Kindle serial numbers: 16 alphanumeric characters, typically start with letter
                 # Examples: G090G10563670ET3, B000000000000000
                 if len(p) == 16 and p.isalnum() and p[0].isalpha():
                     print(f"[DEBUG] Detected Kindle serial number: {p}")
                     potential_dsns.append(p)
                 
                 if "amzn1" in p or len(p) > 20:
                     potential_dsns.append(p)
                     # Strip prefix to get UUID
                     if "amzn1.drm-voucher.v1." in p:
                         uuid_part = p.replace("amzn1.drm-voucher.v1.", "")
                         potential_dsns.append(uuid_part)
                         # Also try without hyphens
                         potential_dsns.append(uuid_part.replace("-", ""))
                 
                 # Also check if it looks like a UUID (with or without hyphens)
                 uuid_pattern = re.compile(r'^[0-9a-fA-F]{8}-?[0-9a-fA-F]{4}-?[0-9a-fA-F]{4}-?[0-9a-fA-F]{4}-?[0-9a-fA-F]{12}$')
                 if uuid_pattern.match(p):
                     potential_dsns.append(p)
                     potential_dsns.append(p.replace("-", ""))
                 
                 # Secret Heuristics (Hex 32/40 chars)
                 if len(p) in (32, 40):
                     try:
                         # Try hex decode
                         s_bytes = binascii.unhexlify(p)
                         potential_secrets.append(s_bytes)
                         print(f"[DEBUG] Added hex-decoded secret: {s_bytes.hex()[:16]}...")
                     except:
                         pass
                     # Always try raw string as well
                     potential_secrets.append(p.encode('ascii'))
                     print(f"[DEBUG] Added raw secret: {p[:16]}...")
                 elif len(p) in (16, 20):
                     # These lengths could be raw secret bytes encoded in some other format
                     potential_secrets.append(p.encode('ascii'))
             
             # Build final DSN list with case variations
             final_dsns = []
             seen_dsns = set()
             for d in potential_dsns:
                 for variant in [d, d.upper(), d.lower()]:
                     if variant not in seen_dsns:
                         seen_dsns.add(variant)
                         final_dsns.append(variant)
             
             print(f"[DEBUG] DSN candidates ({len(final_dsns)}): {final_dsns[:5]}...")
             print(f"[DEBUG] Secret candidates ({len(potential_secrets)})")
             
             success_combo = False
             combo_count = 0
             for d in final_dsns:
                 for s in potential_secrets:
                     combo_count += 1
                     try:
                        voucher = DrmIonVoucher(BytesIO(data), d, s)
                        voucher.parse()
                        voucher.decryptvoucher()
                        success_combo = True
                        s_preview = s.hex()[:8] if isinstance(s, bytes) else s[:8]
                        print(f"[DEBUG] Smart Pairing Success! DSN: {d} + Secret: {s_preview}...")
                        break
                     except:
                        pass
                 if success_combo: break
            
             print(f"[DEBUG] Tried {combo_count} combinations")
             if not success_combo:
                 raise Exception("Failed to decrypt KFX DRM voucher with any key")

        print("KFX DRM voucher successfully decrypted")

        license_type = voucher.getlicensetype()
        if license_type != "Purchase":
            #raise Exception(("This book is licensed as {0}. "
            #        'These tools are intended for use on purchased books.').format(license_type))
            print("Warning: This book is licensed as {0}. "
                    "These tools are intended for use on purchased books. Continuing ...".format(license_type))

        self.voucher = voucher

    def getBookTitle(self):
        return os.path.splitext(os.path.split(self.infile)[1])[0]

    def getBookExtension(self):
        return '.kfx-zip'

    def getBookType(self):
        return 'KFX-ZIP'

    def cleanup(self):
        pass

    def getFile(self, outpath):
        if not self.decrypted:
            shutil.copyfile(self.infile, outpath)
        else:
            with zipfile.ZipFile(self.infile, 'r') as zif:
                with zipfile.ZipFile(outpath, 'w') as zof:
                    for info in zif.infolist():
                        zof.writestr(info, self.decrypted.get(info.filename, zif.read(info.filename)))
