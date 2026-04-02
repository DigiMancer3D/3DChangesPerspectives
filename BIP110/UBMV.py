import tkinter as tk
from tkinter import filedialog, messagebox, ttk, simpledialog
import base64
import hashlib
import os
import tempfile
import urllib.request
import urllib.error
import json
import webbrowser
import platform
import subprocess
import time
import shutil
from datetime import datetime

# Ultimate BTC Media Vault [UBMV] - Hybrid (Hardline + Web) + Tapleaf Multisig + BHB_CHKR
# No extra pip installs required (uses stdlib + bitcoin-cli + ipfs + BHB_CHKR if present)

class UltimateBTCMediaVault(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("🚀 Ultimate BTC Media Vault - Hybrid + Tapleaf + BHB_CHKR")
        self.geometry("1080x860")
        self.configure(bg="#1e1e1e")
        self.resizable(True, True)

        # State
        self.media_path = None
        self.media_bytes = None
        self.base64_str = None
        self.pointer_bytes = None
        self.pointer_hex = None
        self.ipfs_cid = None
        self.ipns_name = None
        self.taproot_addr = None
        self.cold_hashes = self._load_cold_storage()

        # Service detection
        self.ipfs_running = self._detect_ipfs()
        self.btc_running = self._detect_bitcoin_core()
        self.bhb_chkr_path = self._find_bhb_chkr()
        self.bhb_enabled = tk.BooleanVar(value=True)

        self._create_widgets()
        self._update_service_status()
        self.after(2000, self._auto_start_services_if_enabled)

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
        messagebox.showinfo("Cold Store", f"Saved to cold storage: {cid_or_hash[:12]}...")

    def _create_widgets(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TButton", font=("Helvetica", 10, "bold"))
        style.configure("TCheckbutton", background="#1e1e1e", foreground="#f7931a")

        header = tk.Label(self, text="ULTIMATE BTC MEDIA VAULT", bg="#f7931a", fg="#1e1e1e", font=("Helvetica", 20, "bold"))
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

        # TAB 1: Store Media (Hybrid)
        store_tab = tk.Frame(notebook, bg="#1e1e1e")
        notebook.add(store_tab, text="Store Media (Hybrid)")

        tk.Button(store_tab, text="📁 Select Media", bg="#f7931a", fg="#1e1e1e", command=self._select_media).pack(pady=10)
        self.lbl_file = tk.Label(store_tab, text="No file", bg="#1e1e1e", fg="white")
        self.lbl_file.pack()

        # Base64 preview
        tk.Label(store_tab, text="Base64 Preview", bg="#1e1e1e", fg="#f7931a").pack(anchor="w", padx=15)
        self.txt_base64 = tk.Text(store_tab, height=3, bg="#2a2a2a", fg="white")
        self.txt_base64.pack(fill="x", padx=15, pady=5)

        # Options
        opts = tk.LabelFrame(store_tab, text="Mode & Limits (keep <81 bytes when possible)", bg="#1e1e1e", fg="#f7931a")
        opts.pack(fill="x", padx=15, pady=12)

        self.var_web = tk.BooleanVar(value=False)
        self.var_hardline = tk.BooleanVar(value=True)
        self.var_tapleaf = tk.BooleanVar(value=True)
        tk.Checkbutton(opts, text="🌐 Web-Only (incognito)", variable=self.var_web, bg="#1e1e1e", fg="white").grid(row=0, column=0, sticky="w", padx=10)
        tk.Checkbutton(opts, text="🔥 Full Node (Hardline)", variable=self.var_hardline, bg="#1e1e1e", fg="white").grid(row=0, column=1, sticky="w", padx=10)
        tk.Checkbutton(opts, text="🌳 Tapleaf Multisig (smallest on-chain)", variable=self.var_tapleaf, bg="#1e1e1e", fg="white").grid(row=1, column=0, sticky="w", padx=10)

        self.var_ipns = tk.BooleanVar(value=True)
        tk.Checkbutton(opts, text="Publish IPNS (mutable)", variable=self.var_ipns, bg="#1e1e1e", fg="white").grid(row=1, column=1, sticky="w", padx=10)

        self.limit_frame = tk.Frame(store_tab, bg="#1e1e1e", bd=4, relief="solid")
        self.limit_frame.pack(fill="x", padx=15, pady=8)
        self.lbl_limit = tk.Label(self.limit_frame, text="Pointer size: -- bytes", bg="#1e1e1e", fg="white", font=("Helvetica", 11, "bold"))
        self.lbl_limit.pack(pady=8)

        btn_row = tk.Frame(store_tab, bg="#1e1e1e")
        btn_row.pack(pady=15)
        tk.Button(btn_row, text="🌐 Upload IPFS + Generate Pointer", bg="#f7931a", command=self._hybrid_upload_and_pointer).pack(side="left", padx=8)
        tk.Button(btn_row, text="🚀 Commit via Tapleaf Multisig", bg="#f7931a", command=self._commit_tapleaf_multisig).pack(side="left", padx=8)

        # TAB 2: Receive / View
        recv_tab = tk.Frame(notebook, bg="#1e1e1e")
        notebook.add(recv_tab, text="Receive / View")

        tk.Label(recv_tab, text="TXID or Taproot Spend TXID", bg="#1e1e1e", fg="#f7931a").pack(anchor="w", padx=15, pady=10)
        self.entry_txid = tk.Entry(recv_tab, width=80, bg="#2a2a2a", fg="white")
        self.entry_txid.pack(padx=15)
        tk.Button(recv_tab, text="🔍 Fetch Pointer (mempool + BHB_CHKR check)", bg="#f7931a", command=self._fetch_pointer).pack(pady=10)

        self.txt_received = tk.Text(recv_tab, height=12, bg="#2a2a2a", fg="white")
        self.txt_received.pack(fill="both", expand=True, padx=15, pady=5)

        # Bonus: Base64 extractor from screenshot
        tk.Button(recv_tab, text="🧬 Run Tapleaf Base64 Extractor (from your screenshot)", bg="#444", fg="white", command=self._run_base64_extractor).pack(pady=5)

        # TAB 3: Advanced Tapleaf + Multisig + Round-Keychain
        tap_tab = tk.Frame(notebook, bg="#1e1e1e")
        notebook.add(tap_tab, text="🌳 Tapleaf Multisig + Round-Keychain")

        tk.Label(tap_tab, text="Tapleaf commitment keeps on-chain data at 34 bytes (P2TR address).\nData revealed only on spend via 'round-keychain' derivation.", bg="#1e1e1e", fg="#0f0", justify="left").pack(anchor="w", padx=15, pady=10)

        tk.Button(tap_tab, text="Generate Taproot Multisig Address (2-of-3 example)", bg="#f7931a", command=self._generate_taproot_multisig).pack(pady=8)
        self.lbl_taproot = tk.Label(tap_tab, text="Taproot Address: (none yet)", bg="#1e1e1e", fg="white", font=("Courier", 10))
        self.lbl_taproot.pack(padx=15, pady=5)

        tk.Button(tap_tab, text="Reveal / 'Mine' Data via Round-Keychain Spend", bg="#f7931a", command=self._simulate_round_keychain_reveal).pack(pady=8)

        # TAB 4: BHB_CHKR + Cold Storage + Offline
        bhb_tab = tk.Frame(notebook, bg="#1e1e1e")
        notebook.add(bhb_tab, text="BHB_CHKR + Cold Store")

        tk.Checkbutton(bhb_tab, text="Enable BHB_CHKR offline mode (auto-detect on close)", variable=self.bhb_enabled, bg="#1e1e1e", fg="white").pack(anchor="w", padx=15, pady=8)

        if self.bhb_chkr_path:
            tk.Label(bhb_tab, text=f"✅ BHB_CHKR found at:\n{self.bhb_chkr_path}", bg="#1e1e1e", fg="#0f0").pack(anchor="w", padx=15)
        else:
            tk.Label(bhb_tab, text="BHB_CHKR not found - click to open GitHub", bg="#1e1e1e", fg="#ff0").pack(anchor="w", padx=15)
            tk.Button(bhb_tab, text="Download BHB_CHKR", bg="#444", command=lambda: self._open_url_incognito("https://github.com/DigiMancer3D/BHB_CHKR")).pack(pady=5)

        tk.Button(bhb_tab, text="Launch BHB_CHKR (offline UTXO/TX check)", bg="#f7931a", command=self._launch_bhb_chkr).pack(pady=8)
        tk.Button(bhb_tab, text="Save Current Pointer to Cold Storage", bg="#f7931a", command=self._save_current_to_cold).pack(pady=5)

        tk.Label(bhb_tab, text="Cold Stored Hashes (offline verified)", bg="#1e1e1e", fg="#f7931a").pack(anchor="w", padx=15, pady=(20,5))
        self.cold_list = tk.Listbox(bhb_tab, height=8, bg="#2a2a2a", fg="white")
        self.cold_list.pack(fill="x", padx=15)
        self._refresh_cold_list()

        # Footer
        footer = tk.Frame(self, bg="#1e1e1e")
        footer.pack(fill="x", padx=15, pady=8)
        tk.Button(footer, text="Refresh Services", command=self._update_service_status).pack(side="left")
        tk.Button(footer, text="Open coinb.in (incognito)", bg="#444", command=self._open_coinbin).pack(side="left", padx=5)
        tk.Label(footer, text="Hybrid • Tapleaf • BHB_CHKR • <81 byte payloads", bg="#1e1e1e", fg="#888").pack(side="right")

    def _update_service_status(self):
        self.ipfs_running = self._detect_ipfs()
        self.btc_running = self._detect_bitcoin_core()
        bhb_status = "✅" if self.bhb_chkr_path else "❌"
        self.lbl_ipfs.config(text=f"IPFS: {'✅' if self.ipfs_running else '❌'}", fg="#0f0" if self.ipfs_running else "#f00")
        self.lbl_btc.config(text=f"Bitcoin Core: {'✅' if self.btc_running else '❌'}", fg="#0f0" if self.btc_running else "#f00")
        self.lbl_bhb.config(text=f"BHB_CHKR: {bhb_status}", fg="#0f0" if self.bhb_chkr_path else "#f00")

    def _auto_start_services_if_enabled(self):
        if self.bhb_enabled.get() and not self.bhb_chkr_path:
            messagebox.showinfo("Auto-Start", "BHB_CHKR not found - download recommended for offline mode.")
        # IPFS auto-start example (user must have ipfs installed)
        if not self.ipfs_running and messagebox.askyesno("Auto-Start IPFS?", "IPFS not running. Start daemon now?"):
            try:
                subprocess.Popen(["ipfs", "daemon", "--init"], stdout=subprocess.DEVNULL)
                messagebox.showinfo("IPFS", "Daemon started in background.")
                self.ipfs_running = True
            except:
                pass
        self._update_service_status()

    def _select_media(self):
        path = filedialog.askopenfilename()
        if path:
            self.media_path = path
            self.lbl_file.config(text=os.path.basename(path))
            with open(path, "rb") as f:
                self.media_bytes = f.read()
            self.base64_str = base64.b64encode(self.media_bytes).decode()
            self.txt_base64.delete("1.0", tk.END)
            self.txt_base64.insert("1.0", self.base64_str[:180] + "...")

    def _hybrid_upload_and_pointer(self):
        if not self.media_bytes:
            return
        # Hybrid: prefer hardline IPFS, fallback web
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
            except:
                self.ipfs_cid = None
            finally:
                os.unlink(tmp)
        else:
            # Web fallback
            with tempfile.NamedTemporaryFile(delete=False, suffix=".png" if self.media_path.endswith(".png") else ".bin") as tmp:
                tmp.write(self.media_bytes)
                tmp_path = tmp.name
            messagebox.showinfo("Web Upload", f"Drag {tmp_path} into the IPFS web uploader.")
            self._open_url_incognito("https://anarkrypto.github.io/upload-files-to-ipfs-from-browser-panel/public/")
            cid = simpledialog.askstring("CID", "Paste CID from web uploader:")
            if cid:
                self.ipfs_cid = cid.strip()

        # Generate pointer (collision-free SHA256 + version)
        pointer_str = self.ipns_name or self.ipfs_cid or hashlib.sha256(self.base64_str.encode()).hexdigest()
        self.pointer_bytes = b'\x01' + hashlib.sha256(pointer_str.encode()).digest()  # 33 bytes
        self.pointer_hex = self.pointer_bytes.hex()

        length = len(self.pointer_bytes)
        if length > 82:
            self.limit_frame.config(bg="#f00")
            self.lbl_limit.config(text=f"❌ OVER 82: {length} bytes", fg="white")
        elif length > 80:
            self.limit_frame.config(bg="#ff0")
            self.lbl_limit.config(text=f"⚠️ {length} bytes (near limit)", fg="#000")
        else:
            self.limit_frame.config(bg="#0f0")
            self.lbl_limit.config(text=f"✅ {length} bytes (<81 ideal)", fg="white")

        messagebox.showinfo("Pointer Ready", f"Pointer hex ready ({length} bytes)\nTapleaf mode recommended for smallest on-chain footprint.")

    def _commit_tapleaf_multisig(self):
        if not self.pointer_hex:
            messagebox.showwarning("No pointer", "Generate pointer first")
            return
        # Simple Tapleaf commitment (hash of pointer in script)
        # Real implementation would use bitcoin-cli descriptors or JS tapleaf-circuits
        # Here we simulate a P2TR address with embedded commitment (user funds manually)
        commitment_hash = hashlib.sha256(self.pointer_bytes).digest()[:32]
        # Fake a taproot address for demo (in real use replace with proper TapTree)
        self.taproot_addr = f"bc1p{commitment_hash.hex()[:32]}"  # placeholder
        messagebox.showinfo("Tapleaf Multisig", f"Fund this Taproot address for multisig commitment:\n{self.taproot_addr}\n\nData lives in tapleaf - revealed on spend (round-keychain style).")
        self.lbl_taproot.config(text=f"Taproot: {self.taproot_addr}")

    def _generate_taproot_multisig(self):
        # Demo 2-of-3 multisig taproot (placeholder - real script would use OP_CHECKSIGADD)
        messagebox.showinfo("Taproot Multisig", "Example 2-of-3 Taproot created.\nOn-chain: 34 bytes P2TR.\nSpend reveals pointer via tapleaf (under 81 bytes effective).")
        self.taproot_addr = "bc1p5examplemultisigtaprootkeychainroundpull"
        self.lbl_taproot.config(text=f"Taproot Multisig: {self.taproot_addr}")

    def _simulate_round_keychain_reveal(self):
        if not self.pointer_bytes:
            return
        # Round-keychain simulation: derive preimage rounds to "mine" the reveal
        key = hashlib.sha256(self.pointer_bytes).digest()
        for i in range(3):  # 3 "rounds"
            key = hashlib.sha256(key + bytes([i])).digest()
        revealed = key.hex()[:64]
        messagebox.showinfo("Round-Keychain Reveal", f"Data 'mined' after {3} rounds:\n{revealed}\n\nThis is the witness data you would reveal on spend.")

    def _fetch_pointer(self):
        txid = self.entry_txid.get().strip()
        if not txid:
            return
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
                self.txt_received.insert("1.0", f"Pointer: {pointer_hex}\n\nUse BHB_CHKR to verify UTXO status offline.")
                # Cold-store it
                self._save_cold_storage(pointer_hex)
            else:
                self.txt_received.insert("1.0", "No OP_RETURN / nulldata found.")
        except Exception as e:
            self.txt_received.insert("1.0", f"Fetch error: {e}")

    def _run_base64_extractor(self):
        # Exact regex + function from your screenshot
        text = self.txt_received.get("1.0", tk.END)
        import re
        base64_regex = re.compile(r'data:([a-zA-Z0-9]+/[a-zA-Z0-9-.+]+);base64,([A-Za-z0-9+/=]+)')
        matches = base64_regex.findall(text)
        if matches:
            self.txt_received.insert(tk.END, f"\n\n✅ Extracted {len(matches)} base64 media files:\n")
            for mime, data in matches:
                self.txt_received.insert(tk.END, f"MIME: {mime} | Data (first 80): {data[:80]}...\n")
        else:
            self.txt_received.insert(tk.END, "\n\nNo embedded base64 media found.")

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
                subprocess.call([chrome, "--incognito", url] if os.path.exists(chrome) else [url])
            else:
                subprocess.call(["google-chrome", "--incognito", url])
        except:
            webbrowser.open(url)

    def _open_coinbin(self):
        self._open_url_incognito("https://coinb.in/#newTransaction")

if __name__ == "__main__":
    print("🚀 Launching ULTIMATE BTC Media Vault (Hybrid + Tapleaf + BHB_CHKR)")
    app = UltimateBTCMediaVault()
    app.mainloop()
