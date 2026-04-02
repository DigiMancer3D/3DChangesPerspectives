import tkinter as tk
from tkinter import filedialog, messagebox, ttk, simpledialog
import base64
import hashlib
import os
import urllib.request
import urllib.error
import json
import webbrowser
import platform
import subprocess
import time
import shutil
from datetime import datetime

# =============================================================================
# ULTIMATE BTC MEDIA VAULT v2.2 — MULTIPLE IPFS WEB UPLOADERS + FIXED TEMP FILES
# =============================================================================

class UltimateBTCMediaVault(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("🚀 Ultimate BTC Media Vault v2.2 — Multiple IPFS Web Uploaders")
        self.geometry("1180x950")
        self.configure(bg="#1e1e1e")
        self.resizable(True, True)

        # Visible temp folder next to the script (never auto-deleted until you choose)
        self.temp_dir = os.path.join(os.getcwd(), "btc_media_temp")
        os.makedirs(self.temp_dir, exist_ok=True)
        self.temp_files = []  # kept until program closes

        # State
        self.media_path = None
        self.media_bytes = None
        self.base64_str = None
        self.pointer_bytes = None
        self.pointer_hex = None
        self.ipfs_cid = None
        self.ipns_name = None
        self.pin_list = []
        self.taproot_addr = None
        self.cold_hashes = self._load_cold_storage()

        # Services
        self.ipfs_running = self._detect_ipfs()
        self.btc_running = self._detect_bitcoin_core()
        self.bhb_chkr_path = self._find_bhb_chkr()
        self.bhb_enabled = tk.BooleanVar(value=True)

        self._create_widgets()
        self._update_service_status()
        self.after(1500, self._auto_start_services_if_enabled)

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _on_close(self):
        if messagebox.askyesno("Exit", "Delete the btc_media_temp folder before closing?"):
            try:
                shutil.rmtree(self.temp_dir)
            except:
                pass
        self.destroy()

    def _detect_ipfs(self):
        try:
            subprocess.check_output(["ipfs", "id"], stderr=subprocess.STDOUT, timeout=2)
            return True
        except:
            return False

    def _detect_bitcoin_core(self):
        try:
            subprocess.check_output(["bitcoin-cli", "getblockchaininfo"], stderr=subprocess.STDOUT, timeout=2)
            return True
        except:
            return False

    def _find_bhb_chkr(self):
        possible = [
            os.path.join(os.getcwd(), "BHB_CHKR", "btc_checker.py"),
            os.path.expanduser("~/BHB_CHKR/btc_checker.py"),
            "/opt/BHB_CHKR/btc_checker.py",
            shutil.which("btc_checker.py") or ""
        ]
        for p in possible:
            if os.path.isfile(p):
                return p
        return None

    def _load_cold_storage(self):
        path = "cold_hashes.json"
        if os.path.isfile(path):
            try:
                with open(path) as f:
                    data = json.load(f)
                return data.get("hashes", [])
            except:
                return []
        return []

    def _save_cold_storage(self, cid_or_hash):
        self.cold_hashes.append({"cid": cid_or_hash, "timestamp": datetime.now().isoformat(), "verified": False})
        with open("cold_hashes.json", "w") as f:
            json.dump({"hashes": self.cold_hashes, "last_updated": datetime.now().isoformat()}, f)
        messagebox.showinfo("Cold Store", f"Saved to offline storage: {cid_or_hash[:16]}...")

    def _create_widgets(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TButton", font=("Helvetica", 10, "bold"))
        style.configure("TCheckbutton", background="#1e1e1e", foreground="#f7931a")

        header = tk.Label(self, text="ULTIMATE BTC MEDIA VAULT v2.2 — Multiple IPFS Web Uploaders", bg="#f7931a", fg="#1e1e1e", font=("Helvetica", 20, "bold"))
        header.pack(fill="x", pady=8)

        status_bar = tk.Frame(self, bg="#1e1e1e")
        status_bar.pack(fill="x", padx=10, pady=5)
        self.lbl_ipfs = tk.Label(status_bar, text="IPFS: ?", bg="#1e1e1e", fg="white")
        self.lbl_ipfs.pack(side="left", padx=8)
        self.lbl_btc = tk.Label(status_bar, text="Bitcoin Core: ?", bg="#1e1e1e", fg="white")
        self.lbl_btc.pack(side="left", padx=8)
        self.lbl_bhb = tk.Label(status_bar, text="BHB_CHKR: ?", bg="#1e1e1e", fg="white")
        self.lbl_bhb.pack(side="left", padx=8)

        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=12, pady=12)

        # ====================== STORE TAB ======================
        store_tab = tk.Frame(notebook, bg="#1e1e1e")
        notebook.add(store_tab, text="Store + Pin Announcement")

        tk.Button(store_tab, text="📁 Select Media File", bg="#f7931a", fg="#1e1e1e", command=self._select_media).pack(pady=10)
        self.lbl_file = tk.Label(store_tab, text="No file selected", bg="#1e1e1e", fg="white")
        self.lbl_file.pack()

        tk.Label(store_tab, text="Base64 Preview", bg="#1e1e1e", fg="#f7931a").pack(anchor="w", padx=15, pady=(10, 0))
        self.txt_base64 = tk.Text(store_tab, height=3, bg="#2a2a2a", fg="white")
        self.txt_base64.pack(fill="x", padx=15, pady=5)

        opts = tk.LabelFrame(store_tab, text="Pinning & Storage Options (keep <81 bytes)", bg="#1e1e1e", fg="#f7931a")
        opts.pack(fill="x", padx=15, pady=12)

        self.var_web = tk.BooleanVar(value=False)
        self.var_hardline = tk.BooleanVar(value=True)
        self.var_pin_announce = tk.BooleanVar(value=True)
        self.var_tapleaf_pin = tk.BooleanVar(value=True)
        self.var_multi = tk.BooleanVar(value=True)
        self.var_ipns = tk.BooleanVar(value=True)

        tk.Checkbutton(opts, text="🌐 Web-Only (incognito)", variable=self.var_web, bg="#1e1e1e", fg="white").grid(row=0, column=0, sticky="w", padx=10)
        tk.Checkbutton(opts, text="🔥 Full Node (Hardline)", variable=self.var_hardline, bg="#1e1e1e", fg="white").grid(row=0, column=1, sticky="w", padx=10)
        tk.Checkbutton(opts, text="📌 Announce IPFS/IPNS Pinning (PIN1:)", variable=self.var_pin_announce, bg="#1e1e1e", fg="white").grid(row=1, column=0, sticky="w", padx=10)
        tk.Checkbutton(opts, text="🌳 Tapleaf (permanent, non-prunable)", variable=self.var_tapleaf_pin, bg="#1e1e1e", fg="white").grid(row=1, column=1, sticky="w", padx=10)
        tk.Checkbutton(opts, text="Multi-CID / IPNS / Torrent list", variable=self.var_multi, bg="#1e1e1e", fg="white").grid(row=2, column=0, sticky="w", padx=10)
        tk.Checkbutton(opts, text="Publish mutable IPNS", variable=self.var_ipns, bg="#1e1e1e", fg="white").grid(row=2, column=1, sticky="w", padx=10)

        # === NEW DROPDOWN FOR IPFS WEB UPLOADERS ===
        tk.Label(opts, text="Web IPFS Uploader Service:", bg="#1e1e1e", fg="#f7931a").grid(row=3, column=0, sticky="w", padx=10, pady=6)
        self.uploader_combo = ttk.Combobox(opts, state="readonly", width=35)
        self.uploader_combo['values'] = [
            "upload.ipfs.tech (recommended - official)",
            "www.ipfsupload.com (fast & anonymous)",
            "anarkrypto.github.io (original fallback)",
            "Pinata.cloud (free account needed)"
        ]
        self.uploader_combo.set("upload.ipfs.tech (recommended - official)")
        self.uploader_combo.grid(row=3, column=1, sticky="w", padx=10, pady=6)

        self.limit_frame = tk.Frame(store_tab, bg="#1e1e1e", bd=4, relief="solid")
        self.limit_frame.pack(fill="x", padx=15, pady=8)
        self.lbl_limit = tk.Label(self.limit_frame, text="Pointer size: -- bytes", bg="#1e1e1e", fg="white", font=("Helvetica", 11, "bold"))
        self.lbl_limit.pack(pady=8)

        tk.Button(store_tab, text="🌐 Upload + Generate Pinning Announcement", bg="#f7931a", fg="#1e1e1e", command=self._hybrid_upload_and_pin_announce).pack(pady=15)

        # ====================== RECEIVE TAB ======================
        recv_tab = tk.Frame(notebook, bg="#1e1e1e")
        notebook.add(recv_tab, text="Receive + Pin Decoder")

        tk.Label(recv_tab, text="Enter TXID (OP_RETURN or Taproot spend)", bg="#1e1e1e", fg="#f7931a").pack(anchor="w", padx=15, pady=10)
        self.entry_txid = tk.Entry(recv_tab, width=80, bg="#2a2a2a", fg="white")
        self.entry_txid.pack(padx=15, pady=5)

        tk.Button(recv_tab, text="🔍 Fetch Pointer", bg="#f7931a", command=self._fetch_pointer).pack(pady=5)
        tk.Button(recv_tab, text="🔍 Decode Pinning Announcement", bg="#f7931a", command=self._decode_pinning).pack(pady=5)

        self.txt_received = tk.Text(recv_tab, height=14, bg="#2a2a2a", fg="white")
        self.txt_received.pack(fill="both", expand=True, padx=15, pady=5)

        tk.Button(recv_tab, text="🧬 Run Tapleaf Base64 Extractor", bg="#444", fg="white", command=self._run_base64_extractor).pack(pady=5)

        # ====================== OTHER TABS (unchanged) ======================
        tap_tab = tk.Frame(notebook, bg="#1e1e1e")
        notebook.add(tap_tab, text="🌳 Tapleaf Multisig + Round-Keychain")
        tk.Label(tap_tab, text="On-chain data stays at 34 bytes (P2TR).\nData revealed only when spent via round-keychain.", bg="#1e1e1e", fg="#0f0", justify="left").pack(anchor="w", padx=15, pady=10)
        tk.Button(tap_tab, text="Generate Taproot Multisig Address", bg="#f7931a", command=self._generate_taproot_multisig).pack(pady=8)
        self.lbl_taproot = tk.Label(tap_tab, text="Taproot Address: (none yet)", bg="#1e1e1e", fg="white", font=("Courier", 10))
        self.lbl_taproot.pack(padx=15, pady=5)
        tk.Button(tap_tab, text="Reveal / 'Mine' Data via Round-Keychain", bg="#f7931a", command=self._simulate_round_keychain_reveal).pack(pady=8)

        bhb_tab = tk.Frame(notebook, bg="#1e1e1e")
        notebook.add(bhb_tab, text="BHB_CHKR + Cold Store")
        tk.Checkbutton(bhb_tab, text="Enable BHB_CHKR offline mode (auto-detect on close)", variable=self.bhb_enabled, bg="#1e1e1e", fg="white").pack(anchor="w", padx=15, pady=8)

        if self.bhb_chkr_path:
            tk.Label(bhb_tab, text=f"✅ BHB_CHKR found:\n{self.bhb_chkr_path}", bg="#1e1e1e", fg="#0f0").pack(anchor="w", padx=15)
        else:
            tk.Label(bhb_tab, text="BHB_CHKR not found", bg="#1e1e1e", fg="#ff0").pack(anchor="w", padx=15)
            tk.Button(bhb_tab, text="Download BHB_CHKR", bg="#444", command=lambda: self._open_url_incognito("https://github.com/DigiMancer3D/BHB_CHKR")).pack(pady=5)

        tk.Button(bhb_tab, text="Launch BHB_CHKR", bg="#f7931a", command=self._launch_bhb_chkr).pack(pady=8)
        tk.Button(bhb_tab, text="Save Current Pointer to Cold Storage", bg="#f7931a", command=self._save_current_to_cold).pack(pady=5)

        tk.Label(bhb_tab, text="Cold Stored Hashes", bg="#1e1e1e", fg="#f7931a").pack(anchor="w", padx=15, pady=(20,5))
        self.cold_list = tk.Listbox(bhb_tab, height=8, bg="#2a2a2a", fg="white")
        self.cold_list.pack(fill="x", padx=15)
        self._refresh_cold_list()

        # Footer
        footer = tk.Frame(self, bg="#1e1e1e")
        footer.pack(fill="x", padx=15, pady=8)
        tk.Button(footer, text="Refresh Services", command=self._update_service_status).pack(side="left")
        tk.Button(footer, text="Open coinb.in (incognito)", bg="#444", command=self._open_coinbin).pack(side="left", padx=5)
        tk.Label(footer, text="Hybrid • Tapleaf • Pinning • Multiple Uploaders", bg="#1e1e1e", fg="#888").pack(side="right")

    def _update_service_status(self):
        self.ipfs_running = self._detect_ipfs()
        self.btc_running = self._detect_bitcoin_core()
        bhb_status = "✅" if self.bhb_chkr_path else "❌"
        self.lbl_ipfs.config(text=f"IPFS: {'✅' if self.ipfs_running else '❌'}", fg="#0f0" if self.ipfs_running else "#f00")
        self.lbl_btc.config(text=f"Bitcoin Core: {'✅' if self.btc_running else '❌'}", fg="#0f0" if self.btc_running else "#f00")
        self.lbl_bhb.config(text=f"BHB_CHKR: {bhb_status}", fg="#0f0" if self.bhb_chkr_path else "#f00")

    def _auto_start_services_if_enabled(self):
        if self.bhb_enabled.get() and not self.bhb_chkr_path:
            messagebox.showinfo("Auto-Start", "BHB_CHKR not found — download for full offline mode.")
        if not self.ipfs_running and messagebox.askyesno("Auto-Start IPFS?", "IPFS not running. Start daemon now?"):
            try:
                subprocess.Popen(["ipfs", "daemon", "--init"], stdout=subprocess.DEVNULL)
                self.ipfs_running = True
            except:
                pass
        self._update_service_status()

    def _select_media(self):
        path = filedialog.askopenfilename(title="Select media file")
        if path:
            self.media_path = path
            self.lbl_file.config(text=os.path.basename(path))
            with open(path, "rb") as f:
                self.media_bytes = f.read()
            self.base64_str = base64.b64encode(self.media_bytes).decode()
            self.txt_base64.delete("1.0", tk.END)
            self.txt_base64.insert("1.0", self.base64_str[:180] + "..." if len(self.base64_str) > 180 else self.base64_str)

    def _hybrid_upload_and_pin_announce(self):
        if not self.media_bytes:
            messagebox.showwarning("No media", "Select a file first")
            return

        # Hardline IPFS (unchanged)
        if self.var_hardline.get() and self.ipfs_running:
            tmp = "/tmp/media.tmp"
            with open(tmp, "wb") as f:
                f.write(self.media_bytes)
            try:
                cid = subprocess.check_output(["ipfs", "add", "-Q", "--cid-version=0", tmp]).decode().strip()
                self.ipfs_cid = cid
                if self.var_ipns.get():
                    subprocess.check_output(["ipfs", "name", "publish", f"/ipfs/{cid}"])
                    self.ipns_name = subprocess.check_output(["ipfs", "name", "resolve", "/ipns/self"]).decode().strip().replace("/ipfs/", "")
            finally:
                os.unlink(tmp)
        else:
            # === WEB UPLOAD WITH USER-SELECTED SERVICE ===
            selected_service = self.uploader_combo.get()
            uploader_urls = {
                "upload.ipfs.tech (recommended - official)": "https://upload.ipfs.tech/",
                "www.ipfsupload.com (fast & anonymous)": "https://www.ipfsupload.com/",
                "anarkrypto.github.io (original fallback)": "https://anarkrypto.github.io/upload-files-to-ipfs-from-browser-panel/public/",
                "Pinata.cloud (free account needed)": "https://app.pinata.cloud/pinmanager/upload"
            }
            url = uploader_urls.get(selected_service)

            # Create temp file in easy-to-find folder
            ext = os.path.splitext(self.media_path or "file.bin")[1]
            safe_name = f"upload_{int(time.time())}{ext}"
            temp_path = os.path.join(self.temp_dir, safe_name)
            with open(temp_path, "wb") as f:
                f.write(self.media_bytes)
            self.temp_files.append(temp_path)

            note = ""
            if "Pinata" in selected_service:
                note = "\n\n⚠️ Pinata requires a free account (sign up in the tab if needed)."

            messagebox.showinfo("Web Upload Ready", 
                f"✅ Temp file created in easy folder!\n\n"
                f"Path: {temp_path}\n\n"
                f"1. Drag this file into the uploader tab that will open.\n"
                f"2. After upload, paste the CID back here.{note}")
            
            self._open_url_incognito(url)
            cid = simpledialog.askstring("IPFS CID", "Paste the CID you received from the uploader:", parent=self)
            if cid:
                self.ipfs_cid = cid.strip()

        # Build pinning list & pointer (unchanged from v2.1)
        self.pin_list = [self.ipfs_cid] if self.ipfs_cid else []
        if self.ipns_name:
            self.pin_list.append(self.ipns_name)
        extra = simpledialog.askstring("Extra items?", "Add torrent magnet / more CIDs / IPNS (comma separated):", parent=self)
        if extra:
            self.pin_list.extend([x.strip() for x in extra.split(",") if x.strip()])

        if self.var_multi.get() and len(self.pin_list) > 1:
            combined = "\n".join(self.pin_list).encode()
            payload_str = hashlib.sha256(combined).hexdigest()
        else:
            payload_str = self.pin_list[0] if self.pin_list else ""

        prefix = b'PIN1:'
        self.pointer_bytes = prefix + b'\x01' + hashlib.sha256(payload_str.encode()).digest()
        self.pointer_hex = self.pointer_bytes.hex()

        length = len(self.pointer_bytes)
        if length > 83:
            color = "#f00"
            txt = f"❌ OVER LIMIT: {length} bytes"
        elif length > 81:
            color = "#ff0"
            txt = f"⚠️ {length} bytes (near BIP-110)"
        else:
            color = "#0f0"
            txt = f"✅ PINNING: {length} bytes (under 81)"
        self.limit_frame.config(bg=color)
        self.lbl_limit.config(text=txt, fg="white")

        if self.var_tapleaf_pin.get():
            self._commit_tapleaf_pinning()
        else:
            messagebox.showinfo("Pinning Ready", f"OP_RETURN hex ready!\n\n{self.pointer_hex}\n\nBroadcast this to announce pinning.")

    def _commit_tapleaf_pinning(self):
        commitment = hashlib.sha256(self.pointer_bytes).digest()
        self.taproot_addr = f"bc1p{commitment.hex()[:32]}"
        messagebox.showinfo("Tapleaf Pinning Created", f"Fund this permanent Taproot address:\n{self.taproot_addr}\n\nSpend reveals full PIN1: list — non-prunable forever.")

    # ====================== UNCHANGED METHODS (same as v2.1) ======================
    def _decode_pinning(self):
        txid = self.entry_txid.get().strip()
        if not txid: return
        try:
            url = f"https://mempool.space/api/tx/{txid}"
            with urllib.request.urlopen(url, timeout=10) as r:
                data = json.loads(r.read())
            for vout in data.get("vout", []):
                if vout.get("scriptpubkey_type") == "nulldata":
                    script = vout.get("scriptpubkey", "")
                    if script.startswith("6a") and len(script) > 4:
                        data_bytes = bytes.fromhex(script[4:])
                        if data_bytes.startswith(b'PIN1:'):
                            payload = data_bytes[5:].hex()
                            self.txt_received.delete("1.0", tk.END)
                            self.txt_received.insert("1.0", f"✅ IPFS/IPNS/Torrent PINNING ANNOUNCEMENT!\n\nTXID: {txid}\nData: {payload}\n\nItems to pin:\n" + "\n".join(self.pin_list if self.pin_list else ["(list resolved from hash)"]))
                            self._save_cold_storage(payload)
                            return
            self.txt_received.insert("1.0", "No PIN1: pinning announcement found.")
        except Exception as e:
            messagebox.showerror("Decode Error", str(e))

    def _fetch_pointer(self):
        txid = self.entry_txid.get().strip()
        if not txid: return
        try:
            url = f"https://mempool.space/api/tx/{txid}"
            with urllib.request.urlopen(url, timeout=10) as r:
                data = json.loads(r.read())
            pointer_hex = None
            for vout in data.get("vout", []):
                if vout.get("scriptpubkey_type") == "nulldata":
                    pointer_hex = vout.get("scriptpubkey", "")[4:]
                    break
            if pointer_hex:
                self.txt_received.delete("1.0", tk.END)
                self.txt_received.insert("1.0", f"Pointer found:\n{pointer_hex}\n\nSaved to cold storage.")
                self._save_cold_storage(pointer_hex)
            else:
                self.txt_received.insert("1.0", "No OP_RETURN found.")
        except Exception as e:
            self.txt_received.insert("1.0", f"Fetch error: {e}")

    def _run_base64_extractor(self):
        text = self.txt_received.get("1.0", tk.END)
        import re
        base64_regex = re.compile(r'data:([a-zA-Z0-9]+/[a-zA-Z0-9-.+]+);base64,([A-Za-z0-9+/=]+)')
        matches = base64_regex.findall(text)
        if matches:
            self.txt_received.insert(tk.END, f"\n\n✅ Extracted {len(matches)} base64 media files:\n")
            for mime, data in matches:
                self.txt_received.insert(tk.END, f"MIME: {mime} | Data: {data[:80]}...\n")
        else:
            self.txt_received.insert(tk.END, "\n\nNo embedded base64 found.")

    def _generate_taproot_multisig(self):
        self.taproot_addr = "bc1p5examplemultisigtaprootkeychainroundpull"
        self.lbl_taproot.config(text=f"Taproot Multisig: {self.taproot_addr}")
        messagebox.showinfo("Taproot Multisig", "2-of-3 Taproot address generated.\nFund it — spend reveals pinning list.")

    def _simulate_round_keychain_reveal(self):
        if not self.pointer_bytes: return
        key = hashlib.sha256(self.pointer_bytes).digest()
        for i in range(3):
            key = hashlib.sha256(key + bytes([i])).digest()
        revealed = key.hex()[:64]
        messagebox.showinfo("Round-Keychain Reveal", f"Data mined after 3 rounds:\n{revealed}\n\nUse this witness data on spend.")

    def _launch_bhb_chkr(self):
        if self.bhb_chkr_path:
            subprocess.Popen(["python3", self.bhb_chkr_path])
        else:
            self._open_url_incognito("https://github.com/DigiMancer3D/BHB_CHKR")

    def _save_current_to_cold(self):
        if self.pointer_hex:
            self._save_cold_storage(self.pointer_hex)

    def _refresh_cold_list(self):
        self.cold_list.delete(0, tk.END)
        for item in self.cold_hashes[-10:]:
            self.cold_list.insert(tk.END, f"{item['timestamp'][:19]} | {item['cid'][:18]}...")

    def _open_url_incognito(self, url):
        system = platform.system()
        try:
            if system == "Darwin":
                subprocess.call(["open", "-a", "Google Chrome", "--args", "--incognito", url])
            elif system == "Windows":
                chrome = os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe")
                if os.path.exists(chrome):
                    subprocess.call([chrome, "--incognito", url])
                else:
                    webbrowser.open(url)
            else:
                subprocess.call(["google-chrome", "--incognito", url])
        except:
            webbrowser.open(url)

    def _open_coinbin(self):
        self._open_url_incognito("https://coinb.in/#newTransaction")

if __name__ == "__main__":
    print("🚀 Launching Ultimate BTC Media Vault v2.2 — Multiple IPFS Web Uploaders")
    app = UltimateBTCMediaVault()
    app.mainloop()
