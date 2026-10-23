"""Create the Ed25519 signing key pair for release manifests (run ONCE, on your own PC).

  python tools/make_keys.py [PRIVATE_KEY_FILE]

The PRIVATE key is written outside the repo (default: %USERPROFILE%\\CapitalConvert-signing\\release-private.key) and must never be committed,
shared or uploaded; BACK IT UP somewhere safe (if it is lost, existing installs cannot trust new updates and need a new exe).
The PUBLIC key (hex) is written into builder/update_key.py and ships inside the exe.
"""
import os, sys
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.expanduser('~'), 'CapitalConvert-signing', 'release-private.key')
if os.path.exists(path):
    sys.exit('refusing to overwrite %s' % path)
os.makedirs(os.path.dirname(path), exist_ok=True)
k = Ed25519PrivateKey.generate()
raw = k.private_bytes(serialization.Encoding.Raw, serialization.PrivateFormat.Raw, serialization.NoEncryption())
open(path, 'wb').write(raw.hex().encode())
pub = k.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw).hex()
open(os.path.join(HERE, 'builder', 'update_key.py'), 'w').write('"""Public key that update manifests must be signed with (Ed25519, hex)."""\nPUBLIC_KEY_HEX = %r\n' % pub)
print('private key: %s  (keep secret, back it up)\npublic key : %s  (written to builder/update_key.py)' % (path, pub))
