"""Build a Replicad-friendly STL from the original serpent helmet mesh."""

from __future__ import annotations

import hashlib
import shutil
import struct
import tempfile
from pathlib import Path

import trimesh

SOURCE = Path("single_color.stl")
OUTPUT = Path("single_color_browser.stl")
EXPECTED_SHA256 = "698c845000630416e3dfeb83e694f6b4ebfaa3a176ba526e00e44dc00b7bc6e9"
FLIPPED_FACE_INDICES = (
    948359,
    948360,
    1137470,
    1137471,
    1653049,
    1653050,
)
TARGET_FACE_COUNT = 300_000


def flip_binary_stl_faces(path: Path) -> None:
    with path.open("r+b") as stream:
        for face_index in FLIPPED_FACE_INDICES:
            offset = 84 + face_index * 50
            stream.seek(offset)
            record = bytearray(stream.read(50))
            if len(record) != 50:
                raise RuntimeError(f"STL ended before face {face_index}")

            nx, ny, nz = struct.unpack_from("<3f", record, 0)
            struct.pack_into("<3f", record, 0, -nx, -ny, -nz)

            vertex_1 = bytes(record[24:36])
            record[24:36] = record[36:48]
            record[36:48] = vertex_1

            stream.seek(offset)
            stream.write(record)


def main() -> None:
    digest = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
    if digest != EXPECTED_SHA256:
        raise RuntimeError(
            "single_color.stl has changed; refusing to patch hard-coded face indices"
        )

    with tempfile.TemporaryDirectory() as directory:
        repaired_path = Path(directory) / "single_color_repaired.stl"
        shutil.copyfile(SOURCE, repaired_path)
        flip_binary_stl_faces(repaired_path)

        mesh = trimesh.load_mesh(repaired_path, process=False)
        mesh.merge_vertices(digits_vertex=6)

        if not mesh.is_watertight or not mesh.is_winding_consistent:
            raise RuntimeError("face repair did not produce an oriented watertight mesh")

        browser_mesh = mesh.simplify_quadric_decimation(
            face_count=TARGET_FACE_COUNT,
            aggression=3,
        )

        if not browser_mesh.is_watertight:
            raise RuntimeError("simplification produced a non-watertight mesh")
        if not browser_mesh.is_winding_consistent:
            raise RuntimeError("simplification produced inconsistent winding")

        browser_mesh.export(OUTPUT)

    print(
        f"wrote {OUTPUT}: {len(browser_mesh.faces)} triangles, "
        f"{OUTPUT.stat().st_size} bytes"
    )


if __name__ == "__main__":
    main()
