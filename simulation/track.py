import base64
import io
import json

import numpy as np

from simulation.checkpoint import Checkpoint


class Track:
    """Road mask representation of the circuit.
    The mask is a boolean array: True = grass (death), False = road (safe).
    """

    def __init__(self, width: int, height: int):
        self.width = width
        self.height = height
        self.road_mask = np.ones((height, width), dtype=bool)  # All grass by default
        self.start_pos = (100.0, 400.0)
        self.start_angle = 0.0
        self.checkpoints: list[Checkpoint] = []

    @classmethod
    def from_road_base64(cls, data: str, w: int, h: int) -> "Track":
        """Load track from base64 road mask PNG.
        Gray pixels = road, green pixels = grass.
        """
        img_bytes = base64.b64decode(data)
        track = cls(w, h)
        track.road_mask = _decode_mask(img_bytes, w, h)
        return track

    @classmethod
    def from_json(cls, track_data: dict) -> "Track":
        """Load from .track file dict."""
        w = track_data["width"]
        h = track_data["height"]
        track = cls(w, h)

        if "road_mask_base64" in track_data:
            img_bytes = base64.b64decode(track_data["road_mask_base64"])
            track.road_mask = _decode_mask(img_bytes, w, h)

        start = track_data.get("start", {})
        track.start_pos = (start.get("x", 100.0), start.get("y", 400.0))
        track.start_angle = start.get("angle", 0.0)

        track.checkpoints = []
        for i, cp_data in enumerate(track_data.get("checkpoints", [])):
            track.checkpoints.append(Checkpoint.from_dict(cp_data, index=i))

        return track

    def to_json(self) -> dict:
        """Export as .track dict."""
        mask_b64 = _encode_mask(self.road_mask, self.width, self.height)
        return {
            "version": 1,
            "width": self.width,
            "height": self.height,
            "road_mask_base64": mask_b64,
            "start": {
                "x": self.start_pos[0],
                "y": self.start_pos[1],
                "angle": self.start_angle,
            },
            "checkpoints": [cp.to_dict() for cp in self.checkpoints],
        }

    def save(self, filepath: str):
        with open(filepath, "w") as f:
            json.dump(self.to_json(), f)

    @classmethod
    def load(cls, filepath: str) -> "Track":
        with open(filepath, "r") as f:
            data = json.load(f)
        return cls.from_json(data)

    def is_grass(self, x: int, y: int) -> bool:
        """Single point check (True = death/grass)."""
        ix, iy = int(x), int(y)
        if ix < 0 or ix >= self.width or iy < 0 or iy >= self.height:
            return True  # Out of bounds = grass
        return bool(self.road_mask[iy, ix])

    def is_grass_batch(self, xs: np.ndarray, ys: np.ndarray) -> np.ndarray:
        """Vectorized check. Returns bool array, True = grass/death."""
        ixs = xs.astype(np.int32)
        iys = ys.astype(np.int32)

        out_of_bounds = (ixs < 0) | (ixs >= self.width) | (iys < 0) | (iys >= self.height)
        safe_xs = np.clip(ixs, 0, self.width - 1)
        safe_ys = np.clip(iys, 0, self.height - 1)

        on_grass = self.road_mask[safe_ys, safe_xs]
        return out_of_bounds | on_grass

    def raycast_batch(
        self,
        positions: np.ndarray,
        angles: np.ndarray,
        ray_offsets: np.ndarray,
        max_length: float,
    ) -> np.ndarray:
        """Cast rays for all cars.
        positions: (N, 2), angles: (N,), ray_offsets: (R,), max_length: float
        Returns: (N, R) distances per car per ray (normalized 0-1).
        """
        n_cars = positions.shape[0]
        n_rays = ray_offsets.shape[0]
        result = np.ones((n_cars, n_rays), dtype=np.float32)

        # Compute absolute ray angles: (N, R)
        abs_angles = angles[:, np.newaxis] + ray_offsets[np.newaxis, :]

        # Ray direction vectors: (N, R)
        cos_a = np.cos(abs_angles)
        sin_a = np.sin(abs_angles)

        # Step march along each ray
        step_size = 2.0
        n_steps = int(max_length / step_size)

        # Track which rays still need checking
        not_hit = np.ones((n_cars, n_rays), dtype=bool)

        for s in range(1, n_steps + 1):
            dist = s * step_size
            # Sample points: (N, R)
            sx = positions[:, 0:1] + cos_a * dist
            sy = positions[:, 1:2] + sin_a * dist

            # Check bounds
            ix = sx.astype(np.int32)
            iy = sy.astype(np.int32)
            oob = (ix < 0) | (ix >= self.width) | (iy < 0) | (iy >= self.height)

            safe_x = np.clip(ix, 0, self.width - 1)
            safe_y = np.clip(iy, 0, self.height - 1)

            hit = (oob | self.road_mask[safe_y, safe_x]) & not_hit

            if np.any(hit):
                result[hit] = dist / max_length
                not_hit &= ~hit
                # Early exit: all rays resolved
                if not np.any(not_hit):
                    break

        return result


def _decode_mask(img_bytes: bytes, w: int, h: int) -> np.ndarray:
    """Decode a PNG image to a grass mask. Road = gray (#808080), Grass = green (#4CAF50).
    Returns bool array: True = grass, False = road.
    """
    try:
        # Try using the raw RGBA/RGB data approach with minimal deps
        # We'll decode the PNG manually using numpy
        from io import BytesIO

        # Use a simple approach: check if pixel is close to gray (road)
        # We need to decode PNG - use base approach without PIL
        # Since we're in a controlled env, try importing what's available
        import struct
        import zlib

        data = BytesIO(img_bytes)
        # Verify PNG signature
        sig = data.read(8)
        if sig != b'\x89PNG\r\n\x1a\n':
            # Not a PNG - try raw RGBA
            return _decode_raw_rgba(img_bytes, w, h)

        img_w, img_h, bit_depth, color_type = None, None, None, None
        idat_chunks = []

        while True:
            chunk_header = data.read(8)
            if len(chunk_header) < 8:
                break
            length = struct.unpack(">I", chunk_header[:4])[0]
            chunk_type = chunk_header[4:8]
            chunk_data = data.read(length)
            data.read(4)  # CRC

            if chunk_type == b'IHDR':
                img_w = struct.unpack(">I", chunk_data[0:4])[0]
                img_h = struct.unpack(">I", chunk_data[4:8])[0]
                bit_depth = chunk_data[8]
                color_type = chunk_data[9]
            elif chunk_type == b'IDAT':
                idat_chunks.append(chunk_data)
            elif chunk_type == b'IEND':
                break

        if img_w is None:
            return np.ones((h, w), dtype=bool)

        raw = zlib.decompress(b''.join(idat_chunks))

        # Determine bytes per pixel
        if color_type == 2:  # RGB
            bpp = 3
        elif color_type == 6:  # RGBA
            bpp = 4
        else:
            bpp = 4  # default assume RGBA

        stride = 1 + img_w * bpp  # +1 for filter byte
        pixels = np.zeros((img_h, img_w, bpp), dtype=np.uint8)

        raw_bytes = np.frombuffer(raw, dtype=np.uint8)
        prev_row = np.zeros(img_w * bpp, dtype=np.uint8)

        for row in range(img_h):
            offset = row * stride
            filter_byte = raw_bytes[offset]
            row_data = raw_bytes[offset + 1: offset + stride].copy()

            if filter_byte == 0:  # None
                pass
            elif filter_byte == 1:  # Sub
                for i in range(bpp, len(row_data)):
                    row_data[i] = (int(row_data[i]) + int(row_data[i - bpp])) & 0xFF
            elif filter_byte == 2:  # Up
                row_data = (row_data.astype(np.int16) + prev_row.astype(np.int16)).astype(np.uint8)
            elif filter_byte == 3:  # Average
                for i in range(len(row_data)):
                    a = int(row_data[i - bpp]) if i >= bpp else 0
                    b = int(prev_row[i])
                    row_data[i] = (int(row_data[i]) + (a + b) // 2) & 0xFF
            elif filter_byte == 4:  # Paeth
                for i in range(len(row_data)):
                    a = int(row_data[i - bpp]) if i >= bpp else 0
                    b = int(prev_row[i])
                    c = int(prev_row[i - bpp]) if i >= bpp else 0
                    p = a + b - c
                    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                    if pa <= pb and pa <= pc:
                        pr = a
                    elif pb <= pc:
                        pr = b
                    else:
                        pr = c
                    row_data[i] = (int(row_data[i]) + pr) & 0xFF

            prev_row = row_data.copy()
            pixels[row] = row_data.reshape(img_w, bpp)

        # Road = gray (#808080): R~128, G~128, B~128
        # Grass = green (#4CAF50): R~76, G~175, B~80
        # Classify: if green channel > red channel + 20 => grass
        r = pixels[:, :, 0].astype(np.int16)
        g = pixels[:, :, 1].astype(np.int16)

        # Grass if green is significantly higher than red (green-ish)
        # Road if R, G, B are roughly equal (gray-ish)
        is_grass = g > (r + 20)

        # Resize if needed
        if img_w != w or img_h != h:
            result = np.ones((h, w), dtype=bool)
            min_h, min_w = min(h, img_h), min(w, img_w)
            result[:min_h, :min_w] = is_grass[:min_h, :min_w]
            return result

        return is_grass

    except Exception:
        return np.ones((h, w), dtype=bool)


def _decode_raw_rgba(data: bytes, w: int, h: int) -> np.ndarray:
    """Fallback: decode raw RGBA bytes."""
    expected = w * h * 4
    if len(data) < expected:
        return np.ones((h, w), dtype=bool)
    pixels = np.frombuffer(data[:expected], dtype=np.uint8).reshape(h, w, 4)
    r = pixels[:, :, 0].astype(np.int16)
    g = pixels[:, :, 1].astype(np.int16)
    return g > (r + 20)


def _encode_mask(mask: np.ndarray, w: int, h: int) -> str:
    """Encode grass mask to base64 PNG.
    True (grass) = green #4CAF50, False (road) = gray #808080.
    """
    import struct
    import zlib

    # Build RGBA image
    pixels = np.zeros((h, w, 4), dtype=np.uint8)
    # Road (not grass): gray
    pixels[~mask, 0] = 128  # R
    pixels[~mask, 1] = 128  # G
    pixels[~mask, 2] = 128  # B
    pixels[~mask, 3] = 255  # A
    # Grass: green
    pixels[mask, 0] = 76   # R
    pixels[mask, 1] = 175  # G
    pixels[mask, 2] = 80   # B
    pixels[mask, 3] = 255  # A

    # Build PNG manually
    def make_chunk(chunk_type: bytes, data: bytes) -> bytes:
        chunk = chunk_type + data
        crc = zlib.crc32(chunk) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + chunk + struct.pack(">I", crc)

    # IHDR
    ihdr_data = struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0)  # 8bit RGBA
    ihdr = make_chunk(b'IHDR', ihdr_data)

    # IDAT
    raw_rows = bytearray()
    for y in range(h):
        raw_rows.append(0)  # filter: None
        raw_rows.extend(pixels[y].tobytes())

    compressed = zlib.compress(bytes(raw_rows))
    idat = make_chunk(b'IDAT', compressed)

    # IEND
    iend = make_chunk(b'IEND', b'')

    png = b'\x89PNG\r\n\x1a\n' + ihdr + idat + iend
    return base64.b64encode(png).decode('ascii')
