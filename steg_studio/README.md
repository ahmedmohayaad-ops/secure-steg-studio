# Secure Steganography Studio

## Project structure

```
steg_studio/          ← top-level package
│
├── main.py           ← entry point (run this file)
├── requirements.txt
│
├── core/
│   ├── __init__.py   ← re-exports the public API
│   ├── crypto.py     ← PBKDF2 key-derivation + Fernet encrypt/decrypt
│   ├── lsb.py        ← LSB embed / extract
│   ├── payload.py    ← binary outer & inner payload builder/parser
│   ├── encoder.py    ← encode_text / encode_file / encode_audio
│   ├── decoder.py    ← decode()
│   └── image_info.py ← get_image_info / estimate_encrypted_size
│
└── gui/
    ├── __init__.py
    ├── app.py         ← App window + run()
    ├── encrypt_tab.py ← Encrypt tab (Text / File / Audio sub-tabs)
    ├── decrypt_tab.py ← Decrypt tab
    └── widgets.py     ← ImageInfoPanel, StatusBar
```

## Install dependencies

```bash
pip install -r requirements.txt
```

> **Windows / PyAudio**: if `pip install pyaudio` fails, use:
> ```
> pip install pipwin && pipwin install pyaudio
> ```

## Run

```bash
# From the folder that CONTAINS steg_studio/
python steg_studio/main.py
```

or just double-click `main.py` in your IDE.

## Why the original import error happened

`gui/encrypt_tab.py` had `from ..core import …`  
That means "go two levels up from `gui/`", which lands *above* the top-level 
package — Python refuses this with **ImportError: attempted relative import 
beyond top-level package**.

**Fix applied**: every inter-package import now uses **absolute paths**:

```python
# correct
from steg_studio.core import encode_text, encode_file, ...

# broken (old)
from ..core import encode_text, ...
```

`main.py` adds the *parent* of `steg_studio/` to `sys.path` so the absolute 
imports resolve correctly regardless of where you launch the script from.

## Payload binary format

```
Outer (written into image pixels via LSB):
  MAGIC          8 bytes   b'STGSTD01'
  PAYLOAD_SIZE   8 bytes   uint64 LE
  SALT          16 bytes   PBKDF2 salt (random per encryption)
  ENCRYPTED_PAYLOAD        Fernet token

Inner (after decryption):
  TYPE           1 byte    b'T' | b'F' | b'A'
  META_LEN       4 bytes   uint32 LE
  META           N bytes   UTF-8 JSON
  DATA                     raw bytes
```
