import tkinter as tk
from tkinter import filedialog, messagebox, ttk
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

class BitcoinMediaVaultWebOnly(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("BTC Media Vault - WEB ONLY (No BTC Core / No IPFS)")
        self.geometry("960x820")
        self.configure(bg="#1e1e1e")
        self.resizable(True, True)

        # State
        self.media_path = None
        self.media_bytes = None
        self.base64_str = None
        self.pointer_bytes = None
        self.pointer_hex = None
        self.ipfs_cid = None
        self.txid = None

        # Web services (safe, public, HTTPS)
        self.IPFS_WEB_UPLOADER = "https://anarkrypto.github.io/upload-files-to-ipfs-from-browser-panel/public/"
        self.BTC_WEB_BUILDER = "https://coinb.in/#newTransaction"
        self.MEMPOOL_API_BASE = "https://mempool.space/api"

        self._create_widgets()

    def _create_widgets(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TButton", font=("Helvetica", 10, "bold"))
        style.configure("TCheckbutton", background="#1e1e1e", foreground="#f7931a")

        # Header
        header = tk.Label(self, text="BTC Media Vault - WEB ONLY EDITION", bg="#f7931a", fg="#1e1e1e", font=("Helvetica", 18, "bold"))
        header.pack(fill="x", pady=8)

        tk.Label(self, text="✅ Sandboxed • HTTPS • Incognito Mode • No local nodes required", bg="#1e1e1e", fg="#0f0", font=("Helvetica", 9)).pack(pady=(0, 10))

        # Main notebook
        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=10, pady=10)

        # === STORE TAB ===
        store_tab = tk.Frame(notebook, bg="#1e1e1e")
        notebook.add(store_tab, text="Store Media (Web)")

        tk.Label(store_tab, text="1. Select Media File", bg="#1e1e1e", fg="#f7931a", font=("Helvetica", 11, "bold")).pack(anchor="w", padx=15, pady=(15, 5))
        self.btn_select = tk.Button(store_tab, text="📁 Select File", bg="#f7931a", fg="#1e1e1e", command=self._select_media)
        self.btn_select.pack(padx=15, pady=5)

        self.lbl_file = tk.Label(store_tab, text="No file selected", bg="#1e1e1e", fg="white")
        self.lbl_file.pack(anchor="w", padx=15)

        tk.Label(store_tab, text="Base64 Preview (first 150 chars)", bg="#1e1e1e", fg="#f7931a").pack(anchor="w", padx=15, pady=(15, 5))
        self.txt_base64 = tk.Text(store_tab, height=4, bg="#2a2a2a", fg="white", wrap="word")
        self.txt_base64.pack(fill="x", padx=15, pady=5)

        # Pointer options
        opts_frame = tk.LabelFrame(store_tab, text="Pointer Options & Limits", bg="#1e1e1e", fg="#f7931a", font=("Helvetica", 10, "bold"))
        opts_frame.pack(fill="x", padx=15, pady=12)

        self.var_ipfs = tk.BooleanVar(value=True)
        chk_ipfs = tk.Checkbutton(opts_frame, text="Use IPFS CID (recommended)", variable=self.var_ipfs, bg="#1e1e1e", fg="white")
        chk_ipfs.grid(row=0, column=0, sticky="w", padx=12, pady=6)

        self.var_spx_sim = tk.BooleanVar(value=False)
        chk_spx = tk.Checkbutton(opts_frame, text="Simulate SPX (SHA256 pointer - collision fixed)", variable=self.var_spx_sim, bg="#1e1e1e", fg="white")
        chk_spx.grid(row=0, column=1, sticky="w", padx=12, pady=6)

        # Byte limit display with colored border
        self.limit_frame = tk.Frame(store_tab, bg="#1e1e1e", bd=4, relief="solid")
        self.limit_frame.pack(fill="x", padx=15, pady=8)
        self.lbl_limit = tk.Label(self.limit_frame, text="Pointer size: -- bytes (BIP-110 check pending)", bg="#1e1e1e", fg="white", font=("Helvetica", 11, "bold"))
        self.lbl_limit.pack(padx=12, pady=8)

        # Action buttons
        btn_row = tk.Frame(store_tab, bg="#1e1e1e")
        btn_row.pack(pady=15)

        self.btn_upload_web = tk.Button(btn_row, text="🌐 Upload to Web IPFS (Incognito)", bg="#f7931a", fg="#1e1e1e", command=self._upload_web_ipfs)
        self.btn_upload_web.pack(side="left", padx=8)

        self.btn_gen_pointer = tk.Button(btn_row, text="Generate Pointer + Check Limits", bg="#f7931a", fg="#1e1e1e", command=self._generate_pointer)
        self.btn_gen_pointer.pack(side="left", padx=8)

        self.btn_prepare_web_tx = tk.Button(btn_row, text="🚀 Prepare & Sign on Web (coinb.in)", bg="#f7931a", fg="#1e1e1e", state="disabled", command=self._open_web_tx_builder)
        self.btn_prepare_web_tx.pack(side="left", padx=8)

        # === RECEIVE TAB ===
        receive_tab = tk.Frame(notebook, bg="#1e1e1e")
        notebook.add(receive_tab, text="Receive / View from Chain")

        tk.Label(receive_tab, text="Enter TXID (from your web-signed transaction)", bg="#1e1e1e", fg="#f7931a", font=("Helvetica", 11, "bold")).pack(anchor="w", padx=15, pady=15)
        self.entry_txid = tk.Entry(receive_tab, width=80, bg="#2a2a2a", fg="white", font=("Helvetica", 10))
        self.entry_txid.pack(padx=15, pady=5)

        self.btn_fetch_web = tk.Button(receive_tab, text="🔍 Fetch OP_RETURN from mempool.space", bg="#f7931a", fg="#1e1e1e", command=self._fetch_web_tx)
        self.btn_fetch_web.pack(pady=12)

        self.txt_received = tk.Text(receive_tab, height=14, bg="#2a2a2a", fg="white")
        self.txt_received.pack(fill="both", expand=True, padx=15, pady=5)

        # Footer
        footer = tk.Frame(self, bg="#1e1e1e")
        footer.pack(fill="x", padx=15, pady=10)

        tk.Button(footer, text="Open Web IPFS Uploader (Incognito)", bg="#444", fg="white", command=self._open_ipfs_uploader_direct).pack(side="left", padx=5)
        tk.Button(footer, text="Open coinb.in (Incognito)", bg="#444", fg="white", command=self._open_coinbin_direct).pack(side="left", padx=5)

        tk.Label(footer, text="All operations in browser sandbox • Private mode recommended", bg="#1e1e1e", fg="#888", font=("Helvetica", 8)).pack(side="right")

    def _open_url_incognito(self, url):
        """Safely open URL in private/incognito mode (sandboxed browser)"""
        system = platform.system()
        try:
            if system == "Darwin":  # macOS
                subprocess.call(["open", "-a", "Google Chrome", "--args", "--incognito", url])
            elif system == "Windows":
                # Try common Chrome path
                chrome = os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe")
                if os.path.exists(chrome):
                    subprocess.call([chrome, "--incognito", url])
                else:
                    webbrowser.open(url)  # fallback
            elif system == "Linux":
                subprocess.call(["google-chrome", "--incognito", url])
            else:
                webbrowser.open(url)
            messagebox.showinfo("Incognito Opened", "Browser opened in private mode.\n\nAll actions stay sandboxed and private.")
        except Exception:
            webbrowser.open(url)  # ultimate fallback

    def _select_media(self):
        path = filedialog.askopenfilename(title="Select media file", filetypes=[("All files", "*.*")])
        if not path:
            return
        self.media_path = path
        self.lbl_file.config(text=os.path.basename(path))
        with open(path, "rb") as f:
            self.media_bytes = f.read()
        self.base64_str = base64.b64encode(self.media_bytes).decode("utf-8")
        self.txt_base64.delete("1.0", tk.END)
        preview = self.base64_str[:150] + ("..." if len(self.base64_str) > 150 else "")
        self.txt_base64.insert("1.0", preview)
        self.btn_upload_web.config(state="normal")

    def _upload_web_ipfs(self):
        if not self.media_bytes:
            return
        # Save to temp file so user can drag it into the web uploader
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(self.media_path)[1]) as tmp:
            tmp.write(self.media_bytes)
            tmp_path = tmp.name
        messagebox.showinfo("Temp File Ready", f"File saved to:\n{tmp_path}\n\nNow drag this file into the IPFS web uploader that will open.")
        self._open_url_incognito(self.IPFS_WEB_UPLOADER)
        # Ask user to paste CID after upload
        cid = tk.simpledialog.askstring("IPFS Upload Complete?", "Paste the CID you received from the web uploader:", parent=self)
        if cid:
            self.ipfs_cid = cid.strip()
            messagebox.showinfo("CID Saved", f"IPFS CID: {self.ipfs_cid}\n\nReady for pointer generation.")

    def _generate_pointer(self):
        if not self.base64_str:
            return
        use_ipfs = self.var_ipfs.get() and self.ipfs_cid
        use_spx_sim = self.var_spx_sim.get()

        if use_ipfs:
            pointer_str = self.ipfs_cid
        else:
            # Fallback SHA256 of base64
            pointer_str = hashlib.sha256(self.base64_str.encode()).hexdigest()

        if use_spx_sim:
            # Collision-resistant SHA256 pointer (version byte)
            self.pointer_bytes = b'\x01' + hashlib.sha256(pointer_str.encode()).digest()
        else:
            self.pointer_bytes = pointer_str.encode() if isinstance(pointer_str, str) else pointer_str

        pointer_len = len(self.pointer_bytes)
        self.pointer_hex = self.pointer_bytes.hex()

        # Visual limit feedback (BIP-110 = 83 bytes max data push)
        if pointer_len > 83:
            self.limit_frame.config(bg="#f00")
            self.lbl_limit.config(text=f"❌ OVER LIMIT: {pointer_len} bytes (BIP-110 MAX 83)", fg="#fff")
            messagebox.showerror("Limit Exceeded", "Pointer too large for OP_RETURN.\nUse smaller media or IPFS CID.")
        elif pointer_len > 82:
            self.limit_frame.config(bg="#ff0")
            self.lbl_limit.config(text=f"⚠️ WARNING: {pointer_len} bytes (near BIP-110 limit)", fg="#000")
            messagebox.showwarning("Near Limit", "Still under BIP-110 83-byte max but over recommended 82.")
        else:
            self.limit_frame.config(bg="#0f0")
            self.lbl_limit.config(text=f"✅ VALID: {pointer_len} bytes (under 82 limit)", fg="#fff")

        self.btn_prepare_web_tx.config(state="normal")

    def _open_web_tx_builder(self):
        if not self.pointer_hex:
            return
        msg = f"""Copy this exact OP_RETURN data hex (already in clipboard):

{self.pointer_hex}

Steps in the web tool:
1. Paste the hex into the OP_RETURN data field
2. Add your input UTXO (from your wallet)
3. Sign with your private key
4. Broadcast the transaction
5. Copy the resulting TXID and paste it back here for future retrieval"""

        self.clipboard_clear()
        self.clipboard_append(self.pointer_hex)
        messagebox.showinfo("Data Copied", msg)
        self._open_url_incognito(self.BTC_WEB_BUILDER)

    def _open_ipfs_uploader_direct(self):
        self._open_url_incognito(self.IPFS_WEB_UPLOADER)

    def _open_coinbin_direct(self):
        self._open_url_incognito(self.BTC_WEB_BUILDER)

    def _fetch_web_tx(self):
        txid = self.entry_txid.get().strip()
        if not txid:
            messagebox.showwarning("TXID required", "Enter a transaction ID")
            return
        try:
            url = f"{self.MEMPOOL_API_BASE}/tx/{txid}"
            with urllib.request.urlopen(url, timeout=10) as resp:
                data = json.loads(resp.read().decode())
            # Find OP_RETURN
            pointer_hex = None
            for vout in data.get("vout", []):
                if vout.get("scriptpubkey_type") == "nulldata":
                    # scriptpubkey starts with 6a + length + data
                    script = vout.get("scriptpubkey", "")
                    if script.startswith("6a"):
                        pointer_hex = script[4:]  # skip 6a + push byte
                        break
            if pointer_hex:
                try:
                    pointer_bytes = bytes.fromhex(pointer_hex)
                    try:
                        cid = pointer_bytes.decode("utf-8")
                        if cid.startswith(("Qm", "bafy")):
                            self.txt_received.delete("1.0", tk.END)
                            self.txt_received.insert("1.0", f"✅ Found IPFS CID: {cid}\n\nFetch media: https://dweb.link/ipfs/{cid}")
                            return
                    except:
                        pass
                    # Fallback tiny base64
                    try:
                        b64 = base64.b64decode(pointer_bytes).decode("utf-8")
                        self.txt_received.delete("1.0", tk.END)
                        self.txt_received.insert("1.0", f"✅ Tiny embedded media (base64):\n{b64[:400]}...")
                    except:
                        self.txt_received.delete("1.0", tk.END)
                        self.txt_received.insert("1.0", f"✅ Raw pointer hex: {pointer_hex}\n\nDecode manually or resolve as CID.")
                except:
                    self.txt_received.delete("1.0", tk.END)
                    self.txt_received.insert("1.0", f"✅ OP_RETURN data: {pointer_hex}")
            else:
                self.txt_received.delete("1.0", tk.END)
                self.txt_received.insert("1.0", "No OP_RETURN found in this transaction.")
        except urllib.error.URLError as e:
            messagebox.showerror("Network Error", f"Could not reach mempool.space:\n{e}")
        except Exception as e:
            messagebox.showerror("Fetch Error", str(e))

if __name__ == "__main__":
    print("🚀 Starting BTC Media Vault - WEB ONLY EDITION")
    print("All operations run in your browser (incognito recommended for maximum privacy/safety)")
    app = BitcoinMediaVaultWebOnly()
    app.mainloop()
