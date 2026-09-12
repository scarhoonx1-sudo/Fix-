import sys, os, io, zipfile, flask, requests, threading, time
from datetime import timedelta
from jinja2 import DictLoader, ChoiceLoader
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

# Encoding fix
try:
    if hasattr(sys.stdout, 'reconfigure'): sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except: pass

MAGIC = b"SCARVAULT\x01"
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
VAULT_FILE = os.path.join(PROJECT_DIR, "core.enc")

def start_self_ping():
    self_url = os.environ.get("SELF_URL", "").strip()
    if not self_url: return
    # 45 seconds ka ping takki server sleep na ho
    def ping_loop():
        while True:
            try: requests.get(self_url, timeout=10, headers={'User-Agent': 'Mozilla/5.0'})
            except: pass
            time.sleep(45)
    threading.Thread(target=ping_loop, daemon=True).start()

def launch_app():
    start_self_ping()
    key = os.environ.get("APP_KEY", "").strip()
    if not key:
        try: key = input("🔑 Password: ").strip()
        except: pass
    
    with open(VAULT_FILE, "rb") as vf: data = vf.read()
    offset = len(MAGIC)
    salt, nonce, ciphertext = data[offset:offset+16], data[offset+16:offset+28], data[offset+28:]
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=100000)
    aesgcm = AESGCM(kdf.derive(key.encode()))
    raw_zip = aesgcm.decrypt(nonce, ciphertext, None)
    bundle = {name: zipfile.ZipFile(io.BytesIO(raw_zip)).read(name) for name in zipfile.ZipFile(io.BytesIO(raw_zip)).namelist()}

    # FINAL LOGOUT FIX: Flask Session Hooking
    orig_flask_init = flask.Flask.__init__
    def secure_flask_init(self, *args, **kwargs):
        # 1. Fixed Secret Key (Restart hone par session break nahi hoga)
        self.secret_key = "KINGX_SESSION_LOCK_9999"
        # 2. Session Configuration
        self.config.update({
            'PERMANENT_SESSION_LIFETIME': timedelta(days=365), # Session 1 saal valid
            'SESSION_COOKIE_NAME': 'KINGX_SESSION_ID',        # Cookie ko lock kiya
            'SESSION_COOKIE_HTTPONLY': True,
            'SESSION_COOKIE_SAMESITE': 'Lax',
            'SESSION_REFRESH_EACH_REQUEST': False             # Cookie baar-baar change nahi hogi
        })
        orig_flask_init(self, *args, **kwargs)
        
        # Template loading
        templates = {path[9:]: bundle[path].decode(errors="replace") for path in bundle if path.startswith("templates/")}
        self.jinja_loader = ChoiceLoader([DictLoader(templates), self.jinja_loader]) if self.jinja_loader else DictLoader(templates)

    flask.Flask.__init__ = secure_flask_init

    # Run App
    exec(bundle["app.py"].decode(), {"__name__": "__main__", "__file__": "app.py", "__builtins__": __builtins__})

if __name__ == "__main__":
    launch_app()
