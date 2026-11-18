"""Pack PNG files into one .ico (PNG entries, read by Windows Vista and later).

Usage: python scripts/make_ico.py brand/icons/app.ico brand/icons/app-16.png ... app-256.png
See brand/guidelines.md for how the PNGs are made.
"""

import struct
import sys
from pathlib import Path

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def main(out: Path, pngs: list[Path]) -> None:
    datas = [p.read_bytes() for p in pngs]
    sizes = []
    for path, data in zip(pngs, datas, strict=True):
        if data[:8] != PNG_SIGNATURE:
            sys.exit(f"{path}: not a PNG")
        width, height = struct.unpack(">II", data[16:24])
        if width != height or width > 256:
            sys.exit(f"{path}: must be square and at most 256 px")
        sizes.append(width)
    offset = 6 + 16 * len(datas)
    entries = b""
    for size, data in zip(sizes, datas, strict=True):
        # 256 is written as 0 in the one-byte width and height fields.
        entries += struct.pack("<BBBBHHII", size % 256, size % 256, 0, 0, 1, 32, len(data), offset)
        offset += len(data)
    out.write_bytes(struct.pack("<HHH", 0, 1, len(datas)) + entries + b"".join(datas))
    print(out, sizes)


if __name__ == "__main__":
    main(Path(sys.argv[1]), [Path(p) for p in sys.argv[2:]])
