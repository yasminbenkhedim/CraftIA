"""
Downloads the Wav2Lip GAN checkpoint and the s3fd face detector weights
into the local project so the real lip-sync engine can run offline.

Run with the project's .venv python:
    .venv\\Scripts\\python.exe third_party\\download_checkpoints.py
"""
import os
import sys
import urllib.request

# --- Targets -----------------------------------------------------------------
WAV2LIP_DEST = os.path.join("storage", "models", "wav2lip_gan.pth")
S3FD_DEST = os.path.join(
    "third_party", "Wav2Lip", "face_detection", "detection", "sfd", "s3fd.pth"
)

# Multiple mirrors tried in order; first that yields a plausibly-sized file wins.
WAV2LIP_URLS = [
    "https://huggingface.co/numz/wav2lip_studio/resolve/main/Wav2lip/wav2lip_gan.pth",
    "https://huggingface.co/camenduru/Wav2Lip/resolve/main/checkpoints/wav2lip_gan.pth",
    "https://huggingface.co/spaces/fffiloni/Wav2Lip-HD/resolve/main/checkpoints/wav2lip_gan.pth",
    "https://huggingface.co/Nekochu/Wav2Lip/resolve/main/wav2lip_gan.pth",
]
S3FD_URLS = [
    "https://www.adrianbulat.com/downloads/python-fan/s3fd-619a316812.pth",
    "https://huggingface.co/camenduru/Wav2Lip/resolve/main/face_detection/detection/sfd/s3fd.pth",
    "https://huggingface.co/numz/wav2lip_studio/resolve/main/Wav2lip/s3fd.pth",
]

MIN_WAV2LIP_BYTES = 100_000_000   # ~416 MB expected; guard against HTML error pages
MIN_S3FD_BYTES = 50_000_000       # ~86 MB expected


def _human(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f}{unit}"
        n /= 1024
    return f"{n:.1f}TB"


def download(urls, dest, min_bytes) -> bool:
    if os.path.exists(dest) and os.path.getsize(dest) >= min_bytes:
        print(f"[skip] {dest} already present ({_human(os.path.getsize(dest))})")
        return True

    os.makedirs(os.path.dirname(dest), exist_ok=True)
    for url in urls:
        print(f"[try ] {url}")
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=60) as resp:
                total = int(resp.headers.get("Content-Length", 0))
                downloaded = 0
                chunk = 1024 * 256
                tmp = dest + ".part"
                with open(tmp, "wb") as f:
                    while True:
                        data = resp.read(chunk)
                        if not data:
                            break
                        f.write(data)
                        downloaded += len(data)
                        if total:
                            pct = downloaded * 100 // total
                            sys.stdout.write(
                                f"\r       {_human(downloaded)}/{_human(total)} ({pct}%)"
                            )
                            sys.stdout.flush()
                sys.stdout.write("\n")
            size = os.path.getsize(tmp)
            if size >= min_bytes:
                os.replace(tmp, dest)
                print(f"[ ok ] saved {dest} ({_human(size)})")
                return True
            else:
                print(f"[warn] file too small ({_human(size)}), trying next mirror")
                os.remove(tmp)
        except Exception as exc:  # noqa: BLE001
            print(f"[fail] {exc}")
            try:
                if os.path.exists(dest + ".part"):
                    os.remove(dest + ".part")
            except OSError:
                pass
    print(f"[ERR ] could not download to {dest} from any mirror")
    return False


if __name__ == "__main__":
    ok_wav2lip = download(WAV2LIP_URLS, WAV2LIP_DEST, MIN_WAV2LIP_BYTES)
    ok_s3fd = download(S3FD_URLS, S3FD_DEST, MIN_S3FD_BYTES)
    print("\n=== RESULT ===")
    print(f"wav2lip_gan.pth : {'OK' if ok_wav2lip else 'MISSING'}")
    print(f"s3fd.pth        : {'OK' if ok_s3fd else 'MISSING'}")
    sys.exit(0 if (ok_wav2lip and ok_s3fd) else 1)
