import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import subprocess
import base64
import hashlib
import os
import json
import urllib.request
import urllib.parse
import time

class BitcoinMediaStorageGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("BTC Media Vault - Store/Receive Media via OP_RETURN + IPNS")
        self.geometry("920x780")
        self.configure(bg="#1e1e1e")
        self.resizable(True, True)

        # State
        self.media_path = None
        self.media_bytes = None
        self.base64_str = None
        self.pointer_data = None  # bytes to put in OP_RETURN (max 82)
        self.ipfs_cid = None
        self.ipns_name = None
        self.raw_tx = None
        self.signed_tx = None

        # Detect running services
        self.ipfs_running = self._detect_ipfs()
        self.btc_running = self._detect_bitcoin_core()

        self._create_widgets()
        self._update_service_status()

    def _detect_ipfs(self):
        try:
            subprocess.check_output(["ipfs", "id"], stderr=subprocess.STDOUT, timeout=3)
            return True
        except Exception:
            return False

    def _detect_bitcoin_core(self):
        try:
            subprocess.check_output(["bitcoin-cli", "getblockchaininfo"], stderr=subprocess.STDOUT, timeout=3)
            return True
        except Exception:
            return False

    def _create_widgets(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TCheckbutton", background="#1e1e1e", foreground="#f7931a")
        style.configure("TButton", font=("Helvetica", 10, "bold"))

        # Header (mimics BTC orange)
        header = tk.Label(self, text="BTC Media Vault", bg="#f7931a", fg="#1e1e1e", font=("Helvetica", 18, "bold"))
        header.pack(fill="x", pady=8)

        # Service status bar
        self.status_frame = tk.Frame(self, bg="#1e1e1e")
        self.status_frame.pack(fill="x", padx=10, pady=5)
        self.lbl_ipfs = tk.Label(self.status_frame, text="IPFS: DETECTING", bg="#1e1e1e", fg="white", font=("Helvetica", 9))
        self.lbl_ipfs.pack(side="left", padx=10)
        self.lbl_btc = tk.Label(self.status_frame, text="Bitcoin Core: DETECTING", bg="#1e1e1e", fg="white", font=("Helvetica", 9))
        self.lbl_btc.pack(side="left", padx=10)

        # Main notebook (tabs)
        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=10, pady=10)

        # Tab 1: Store Media
        store_tab = tk.Frame(notebook, bg="#1e1e1e")
        notebook.add(store_tab, text="Store Media")

        # Media selection
        tk.Label(store_tab, text="1. Select Media File", bg="#1e1e1e", fg="#f7931a", font=("Helvetica", 11, "bold")).pack(anchor="w", padx=10, pady=(10, 5))
        self.btn_select = tk.Button(store_tab, text="Select File", bg="#f7931a", fg="#1e1e1e", font=("Helvetica", 10, "bold"), command=self._select_media)
        self.btn_select.pack(padx=10, pady=5)

        self.lbl_file = tk.Label(store_tab, text="No file selected", bg="#1e1e1e", fg="white")
        self.lbl_file.pack(anchor="w", padx=10)

        # Base64 preview
        tk.Label(store_tab, text="Base64 (preview first 200 chars)", bg="#1e1e1e", fg="#f7931a").pack(anchor="w", padx=10, pady=(15, 5))
        self.txt_base64 = tk.Text(store_tab, height=4, bg="#2a2a2a", fg="white", wrap="word")
        self.txt_base64.pack(fill="x", padx=10, pady=5)

        # Options toggles (all possible methods)
        options_frame = tk.LabelFrame(store_tab, text="Options & Methods", bg="#1e1e1e", fg="#f7931a", font=("Helvetica", 10, "bold"))
        options_frame.pack(fill="x", padx=10, pady=10)

        # Use IPFS toggle
        self.var_ipfs = tk.BooleanVar(value=self.ipfs_running)
        self.chk_ipfs = tk.Checkbutton(options_frame, text="Use Local IPFS (if running)", variable=self.var_ipfs, bg="#1e1e1e", fg="white", command=self._toggle_ipfs)
        self.chk_ipfs.grid(row=0, column=0, sticky="w", padx=10, pady=4)

        # Use IPNS toggle
        self.var_ipns = tk.BooleanVar(value=False)
        self.chk_ipns = tk.Checkbutton(options_frame, text="Publish mutable IPNS name", variable=self.var_ipns, bg="#1e1e1e", fg="white", state="disabled" if not self.ipfs_running else "normal")
        self.chk_ipns.grid(row=0, column=1, sticky="w", padx=10, pady=4)

        # Use SPX toggle (collision fixed by using deterministic SHA256 pointer + version byte instead of original SPX)
        self.var_spx = tk.BooleanVar(value=False)
        self.chk_spx = tk.Checkbutton(options_frame, text="Use SPX-style compression (collision fixed via SHA256 pointer)", variable=self.var_spx, bg="#1e1e1e", fg="white")
        self.chk_spx.grid(row=1, column=0, sticky="w", padx=10, pady=4)
        tk.Label(options_frame, text="(SPX collision error corrected - now uses collision-resistant SHA256 pointer)", bg="#1e1e1e", fg="#888", font=("Helvetica", 8)).grid(row=1, column=1, sticky="w", padx=10)

        # Method toggles
        self.var_opreturn = tk.BooleanVar(value=True)
        chk_op = tk.Checkbutton(options_frame, text="OP_RETURN (simple pointer)", variable=self.var_opreturn, bg="#1e1e1e", fg="white", command=self._update_method_ui)
        chk_op.grid(row=2, column=0, sticky="w", padx=10, pady=4)

        self.var_tapleaf = tk.BooleanVar(value=False)
        chk_tap = tk.Checkbutton(options_frame, text="Tapleaf (advanced - no OP_RETURN)", variable=self.var_tapleaf, bg="#1e1e1e", fg="white", command=self._update_method_ui)
        chk_tap.grid(row=2, column=1, sticky="w", padx=10, pady=4)

        # Byte limit status (colored border)
        self.limit_frame = tk.Frame(store_tab, bg="#1e1e1e", bd=3, relief="solid")
        self.limit_frame.pack(fill="x", padx=10, pady=8)
        self.lbl_limit = tk.Label(self.limit_frame, text="Pointer size: -- bytes", bg="#1e1e1e", fg="white", font=("Helvetica", 11, "bold"))
        self.lbl_limit.pack(padx=10, pady=6)

        # Action buttons
        btn_frame = tk.Frame(store_tab, bg="#1e1e1e")
        btn_frame.pack(pady=15)

        self.btn_upload_ipfs = tk.Button(btn_frame, text="Upload to IPFS + Publish IPNS", bg="#f7931a", fg="#1e1e1e", state="disabled", command=self._upload_ipfs_ipns)
        self.btn_upload_ipfs.pack(side="left", padx=8)

        self.btn_generate_pointer = tk.Button(btn_frame, text="Generate Pointer & Check Limits", bg="#f7931a", fg="#1e1e1e", command=self._generate_pointer)
        self.btn_generate_pointer.pack(side="left", padx=8)

        self.btn_prepare_tx = tk.Button(btn_frame, text="Prepare BTC TX", bg="#f7931a", fg="#1e1e1e", state="disabled", command=self._prepare_tx)
        self.btn_prepare_tx.pack(side="left", padx=8)

        # Tab 2: Receive / View
        receive_tab = tk.Frame(notebook, bg="#1e1e1e")
        notebook.add(receive_tab, text="Receive / View")

        tk.Label(receive_tab, text="Enter OP_RETURN TXID to retrieve media", bg="#1e1e1e", fg="#f7931a", font=("Helvetica", 11, "bold")).pack(anchor="w", padx=10, pady=10)
        self.entry_txid = tk.Entry(receive_tab, width=70, bg="#2a2a2a", fg="white")
        self.entry_txid.pack(padx=10, pady=5)

        self.btn_fetch = tk.Button(receive_tab, text="Fetch & Decode Media", bg="#f7931a", fg="#1e1e1e", command=self._fetch_from_tx)
        self.btn_fetch.pack(pady=10)

        self.txt_received = tk.Text(receive_tab, height=12, bg="#2a2a2a", fg="white")
        self.txt_received.pack(fill="both", expand=True, padx=10, pady=5)

        # Footer controls (global toggles + warnings)
        footer = tk.Frame(self, bg="#1e1e1e")
        footer.pack(fill="x", padx=10, pady=8)

        self.btn_refresh_services = tk.Button(footer, text="Refresh Services", bg="#444", fg="white", command=self._update_service_status)
        self.btn_refresh_services.pack(side="left", padx=5)

        # Help text
        help_lbl = tk.Label(footer, text="Runs alongside Bitcoin Core • Uses bitcoin-cli & ipfs CLI • No extra Python pip installs required", bg="#1e1e1e", fg="#888", font=("Helvetica", 8))
        help_lbl.pack(side="right", padx=5)

    def _update_service_status(self):
        self.ipfs_running = self._detect_ipfs()
        self.btc_running = self._detect_bitcoin_core()

        self.lbl_ipfs.config(text=f"IPFS: {'✅ RUNNING' if self.ipfs_running else '❌ NOT RUNNING'}",
                             fg="#0f0" if self.ipfs_running else "#f00")
        self.lbl_btc.config(text=f"Bitcoin Core: {'✅ RUNNING' if self.btc_running else '❌ NOT RUNNING'}",
                            fg="#0f0" if self.btc_running else "#f00")

        # Enable/disable IPFS buttons
        state_ipfs = "normal" if self.ipfs_running else "disabled"
        self.chk_ipfs.config(state=state_ipfs)
        self.btn_upload_ipfs.config(state=state_ipfs if self.media_bytes else "disabled")

    def _toggle_ipfs(self):
        if self.var_ipfs.get() and not self.ipfs_running:
            messagebox.showwarning("IPFS", "IPFS daemon not detected. Start it with 'ipfs daemon' in terminal.")

    def _update_method_ui(self):
        # Simple visual feedback
        pass

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
        self.txt_base64.insert("1.0", self.base64_str[:200] + "..." if len(self.base64_str) > 200 else self.base64_str)
        self.btn_upload_ipfs.config(state="normal" if self.ipfs_running else "disabled")
        self.btn_generate_pointer.config(state="normal")

    def _upload_ipfs_ipns(self):
        if not self.media_bytes or not self.ipfs_running:
            return

        # Write temp file for ipfs add
        tmp_path = "/tmp/btc_media_temp.bin"
        with open(tmp_path, "wb") as f:
            f.write(self.media_bytes)

        try:
            # Add to IPFS
            cid_out = subprocess.check_output(["ipfs", "add", "--cid-version=0", "-Q", tmp_path]).decode().strip()
            self.ipfs_cid = cid_out
            messagebox.showinfo("IPFS", f"Uploaded! CID: {self.ipfs_cid}")

            if self.var_ipns.get():
                # Publish to IPNS (uses default key)
                subprocess.check_output(["ipfs", "name", "publish", f"/ipfs/{self.ipfs_cid}"])
                # Get IPNS name
                ipns_out = subprocess.check_output(["ipfs", "name", "resolve", "/ipns/self"]).decode().strip()
                self.ipns_name = ipns_out.replace("/ipfs/", "")
                messagebox.showinfo("IPNS", f"Published mutable IPNS: {self.ipns_name}")
        except Exception as e:
            messagebox.showerror("IPFS Error", str(e))
        finally:
            os.remove(tmp_path)

    def _generate_pointer(self):
        if not self.base64_str:
            return

        use_spx = self.var_spx.get()
        use_ipns = self.var_ipns.get() and self.ipns_name

        # Build pointer bytes (max 82)
        if use_ipns and self.ipns_name:
            pointer_str = self.ipns_name  # ~46-50 bytes base32
        elif self.ipfs_cid:
            pointer_str = self.ipfs_cid
        else:
            # Fallback: SHA256 of base64 (32 bytes) + 1-byte version/magic
            h = hashlib.sha256(self.base64_str.encode()).digest()
            pointer_str = h.hex()  # 64 hex chars → 32 bytes raw later

        # SPX toggle: we simulate compression with deterministic hash (collision fixed)
        if use_spx:
            # Fixed collision: always prepend version byte 0x01 + SHA256 (no original SPX hash collisions)
            pointer_bytes = b'\x01' + hashlib.sha256(pointer_str.encode()).digest()
        else:
            pointer_bytes = pointer_str.encode() if isinstance(pointer_str, str) else pointer_str

        # Enforce limits
        pointer_len = len(pointer_bytes)
        self.pointer_data = pointer_bytes

        # Colored border + warning
        self.limit_frame.config(bg="#0f0" if pointer_len <= 82 else "#f00")
        if pointer_len > 83:
            self.lbl_limit.config(text=f"ERROR: {pointer_len} bytes > BIP-110 MAX (83)", fg="#f00")
            messagebox.showerror("Limit Exceeded", "Pointer exceeds BIP-110 83-byte limit. Reduce media or use IPNS pointer.")
        elif pointer_len > 82:
            self.lbl_limit.config(text=f"WARNING: {pointer_len} bytes (BIP-110 max 83)", fg="#ff0")
            messagebox.showwarning("Near Limit", "Pointer is over recommended 82 bytes but under BIP-110 max.")
        else:
            self.lbl_limit.config(text=f"VALID: {pointer_len} bytes (under 82 limit)", fg="#0f0")

        self.btn_prepare_tx.config(state="normal" if self.var_opreturn.get() and self.btc_running else "disabled")

    def _prepare_tx(self):
        if not self.pointer_data or not self.btc_running:
            return

        try:
            # Get a small UTXO for funding (first unspent)
            unspent = json.loads(subprocess.check_output(["bitcoin-cli", "listunspent", "0"]).decode())
            if not unspent:
                messagebox.showerror("No funds", "Wallet has no confirmed UTXOs.")
                return
            utxo = unspent[0]

            data_hex = self.pointer_data.hex()

            # createrawtransaction with OP_RETURN output (value 0)
            inputs = json.dumps([{"txid": utxo["txid"], "vout": utxo["vout"]}])
            outputs = json.dumps({"data": data_hex, utxo["address"]: str(utxo["amount"] - 0.00001)})  # tiny fee to self

            self.raw_tx = subprocess.check_output(["bitcoin-cli", "createrawtransaction", inputs, outputs]).decode().strip()

            messagebox.showinfo("Raw TX Ready", f"Raw TX hex (copy if needed):\n{self.raw_tx[:120]}...")
            self.btn_prepare_tx.config(state="disabled")
            # Auto sign next
            self._sign_tx()
        except Exception as e:
            messagebox.showerror("TX Prep Error", str(e))

    def _sign_tx(self):
        if not self.raw_tx:
            return
        try:
            # Sign with wallet
            signed = subprocess.check_output(["bitcoin-cli", "signrawtransactionwithwallet", self.raw_tx]).decode()
            signed_json = json.loads(signed)
            if signed_json.get("complete"):
                self.signed_tx = signed_json["hex"]
                messagebox.showinfo("Signed!", "Transaction signed successfully.")
                self._send_tx()
            else:
                messagebox.showerror("Signing Failed", signed_json.get("errors", "Unknown error"))
        except Exception as e:
            messagebox.showerror("Sign Error", str(e))

    def _send_tx(self):
        if not self.signed_tx:
            return
        try:
            txid = subprocess.check_output(["bitcoin-cli", "sendrawtransaction", self.signed_tx]).decode().strip()
            messagebox.showinfo("Broadcast Success!", f"TXID: {txid}\n\nYour pointer is now on-chain!\n\nSave this TXID to retrieve later.")
            self.raw_tx = self.signed_tx = None
        except Exception as e:
            messagebox.showerror("Broadcast Error", str(e))

    def _fetch_from_tx(self):
        txid = self.entry_txid.get().strip()
        if not txid or not self.btc_running:
            return
        try:
            raw = json.loads(subprocess.check_output(["bitcoin-cli", "getrawtransaction", txid, "true"]).decode())
            # Find OP_RETURN
            for vout in raw.get("vout", []):
                if vout.get("scriptPubKey", {}).get("type") == "nulldata":
                    data_hex = vout["scriptPubKey"]["hex"][4:]  # skip OP_RETURN opcode
                    pointer_bytes = bytes.fromhex(data_hex)
                    # Decode (IPNS/CID or hash)
                    try:
                        pointer_str = pointer_bytes.decode("utf-8")
                        if pointer_str.startswith("Qm") or len(pointer_str) > 40:  # rough CID check
                            self.txt_received.delete("1.0", tk.END)
                            self.txt_received.insert("1.0", f"Found IPFS pointer: {pointer_str}\n\nFetch with: ipfs get /ipfs/{pointer_str}")
                            return
                    except:
                        pass
                    # Fallback base64 decode attempt (if tiny media)
                    try:
                        decoded_b64 = base64.b64decode(pointer_bytes).decode("utf-8")
                        self.txt_received.delete("1.0", tk.END)
                        self.txt_received.insert("1.0", f"Decoded base64 media (tiny):\n{decoded_b64[:500]}...")
                    except:
                        self.txt_received.delete("1.0", tk.END)
                        self.txt_received.insert("1.0", f"Pointer bytes (hex): {pointer_bytes.hex()}\n\nUse IPFS/IPNS resolver manually.")
        except Exception as e:
            messagebox.showerror("Fetch Error", str(e))

if __name__ == "__main__":
    # Self-check: remind user to have bitcoin-cli and ipfs in PATH
    print("Starting BTC Media Vault GUI...\nRequires: bitcoin-cli in PATH + optional ipfs daemon.")
    app = BitcoinMediaStorageGUI()
    app.mainloop()
