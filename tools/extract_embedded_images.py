"""Extract data-URI embedded images from extracted .txt attachments.

The chat attachments are delivered as extracted text, but Word documents that
contain inline pictures also leave a ``data:image/png;base64,...`` URI in that
text.  Decoding those URIs recovers the original artwork (VTU emblem, college
logo, NBA/NAAC badges) without needing the original .docx binary.
"""

from __future__ import annotations

import base64
import hashlib
import io
import re
import sys
from pathlib import Path

from PIL import Image

URI = re.compile(r"data:image/(png|jpeg|jpg);base64,([A-Za-z0-9+/=\r\n\t ]+)", re.I)


def main(sources: list[str], outdir: str) -> None:
    out = Path(outdir)
    out.mkdir(parents=True, exist_ok=True)
    seen: dict[str, str] = {}
    index = 0

    for src in sources:
        raw = Path(src).read_text(encoding="utf-8", errors="ignore")
        for m in URI.finditer(raw):
            ext = ".png" if m.group(1).lower() == "png" else ".jpg"
            payload = re.sub(r"\s+", "", m.group(2))
            pad = (-len(payload)) % 4
            payload += "=" * pad
            try:
                blob = base64.b64decode(payload, validate=False)
            except Exception:
                continue
            if len(blob) < 4096:
                continue
            digest = hashlib.md5(blob).hexdigest()
            if digest in seen:
                continue
            index += 1
            name = f"{Path(src).stem[:10]}_{index:03d}{ext}"
            path = out / name
            path.write_bytes(blob)
            seen[digest] = name
            try:
                with Image.open(io.BytesIO(blob)) as im:
                    print(f"{name}\t{im.size[0]}x{im.size[1]}\t{len(blob)//1024} KB")
            except Exception:
                print(f"{name}\tUNREADABLE\t{len(blob)//1024} KB")

    print(f"\ntotal unique images: {len(seen)}")


if __name__ == "__main__":
    main(sys.argv[1:-1], sys.argv[-1])
