# Secure Steganography Studio

A desktop app for hiding authenticated, encrypted payloads inside lossless
images using LSB steganography. Payloads are encrypted with Fernet
(AES-128-CBC + HMAC-SHA256) and keys are derived with PBKDF2-HMAC-SHA256
(480k iterations), so a wrong passphrase fails HMAC verification cleanly
instead of producing garbage.

## Features

- **Encrypt** any text, file, or recorded voice message into a PNG cover.
- **Decrypt** stego images back to the original payload with HMAC-backed
  authentication.
- **Forensic Inspector** that updates *live* as you work:
  - Thumbnail + **Encrypted / Not Encrypted** badge the moment you pick
    an image.
  - Channel capacity bars (R / G / B) and **RAW vs ENCRYPTED** overhead
    diagram that track the payload as you type.
  - **What happened** narration card that logs each stage of the pipeline
    during a run: PBKDF2 key derivation → AES-128-CBC encrypt → HMAC → LSB
    embed across R/G/B.
  - LSB visualizer, cover-vs-stego histogram, and a bit-level 1-pixel peek.
- Dark / Light themes, resizable down to 900×600.

## Project structure

```
steg_studio/                  ← top-level package
│
├── main.py                   ← entry point (run this file)
├── requirements.txt
│
├── core/
│   ├── __init__.py           ← re-exports the public API
│   ├── crypto.py             ← PBKDF2 + Fernet wrappers
│   ├── lsb.py                ← LSB embed / extract
│   ├── payload.py            ← outer + inner binary format
│   ├── encoder.py            ← encode_text / encode_file / encode_audio
│   ├── decoder.py            ← decode() + check_magic()
│   └── image_info.py         ← get_image_info / estimate_encrypted_size
│
├── gui/                      ← current v2.1 workstation UI
│   ├── app.py                ← shell: title/top/rail/workspace/drawer
│   ├── encrypt_panel.py      ← embed workflow
│   ├── decrypt_panel.py      ← extract workflow
│   ├── components.py         ← widgets (BytePeek, ActivityLog, CoverPreview…)
│   ├── theme.py              ← dual dark / light palette + type scale
│   ├── assets.py             ← inline SVG icon pack
│   ├── workers.py            ← background thread helper
│   ├── prefs.py              ← persisted preferences (theme)
│   └── splash.py
│
└── gui_legacy/               ← earlier tkinter-tab UI (kept for reference)
```

## Install

```bash
pip install -r requirements.txt
```

> **Windows / PyAudio**: if `pip install pyaudio` fails, use:
>
> ```
> pip install pipwin && pipwin install pyaudio
> ```

## Run

```bash
# From the folder that CONTAINS steg_studio/
python -m steg_studio.main
```

or run `main.py` directly from your IDE.

## How it works

### Workflow

1. Drop a cover PNG into the **Encrypt** panel. The Inspector immediately
   shows the thumbnail, channel capacity, and an encrypted/not badge.
2. Choose a payload (file, text, or recorded voice), enter a passphrase,
   and hit **Begin encryption**. The Inspector's narration log explains
   each pipeline stage as it runs.
3. Export the stego PNG. To recover: drop it into the **Decrypt** panel,
   enter the passphrase, and the payload is verified with HMAC before
   being released.

### Binary format

```
Outer (written into image pixels via LSB):
  MAGIC          8 bytes    b'STGSTD02'
  PAYLOAD_SIZE   8 bytes    uint64 LE
  SALT          16 bytes    PBKDF2 salt (random per encryption)
  NONCE         16 bytes    Fernet IV
  CIPHER         N bytes    AES-128-CBC ciphertext (PKCS7 padded)
  MAC           32 bytes    HMAC-SHA256 over header+cipher

Inner (after decryption):
  TYPE           1 byte     b'T' | b'F' | b'A'
  META_LEN       4 bytes    uint32 LE
  META           N bytes    UTF-8 JSON
  DATA                      raw bytes
```

### Channel capacity

Each pixel carries 1 LSB per R/G/B channel, so the maximum payload size
(in bytes) of a `w × h` image is `w * h * 3 // 8`. The Inspector's
capacity bars show how much of that is consumed by the encrypted envelope
— the **RAW vs ENCRYPTED** overhead bar makes it obvious how much the
Fernet framing adds over your raw payload.

## Imports

All intra-package imports are absolute (`from steg_studio.core import …`)
so the package runs the same whether you execute `main.py` directly or
use `python -m steg_studio.main`.
