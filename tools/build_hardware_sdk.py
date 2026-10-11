"""Build MKW's pinned, locally patched Citro3D without changing the SDK."""
import hashlib
import json
from pathlib import Path
import subprocess

from devkitpro import arm

ROOT = Path(__file__).resolve().parents[1]
VENDOR = ROOT / "vendor/citro3d"


def build_citro3d(output, dkp):
    output = Path(output) / "hardware-sdk"
    output.mkdir(parents=True, exist_ok=True)
    compiler = arm("arm-none-eabi-gcc")
    files = sorted(p for directory in ("source", "include")
                   for p in (VENDOR / directory).rglob("*") if p.is_file() and not p.name.startswith("._"))
    hashes = {p.relative_to(VENDOR).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
              for p in files}
    flags = ["-march=armv6k", "-mtune=mpcore", "-mfloat-abi=hard", "-mtp=soft",
             "-O2", "-g", "-mword-relocations", "-ffunction-sections", "-fdata-sections",
             "-fno-math-errno", "-D__3DS__", "-DCITRO3D_BUILD", "-DNDEBUG=1",
             "-I" + str(VENDOR / "include"), "-I" + str(Path(dkp) / "libctru/include")]
    identity = {"upstream_commit": "9f21cf7b380ce6f9e01a0420f19f0763e5443ca7", "source_sha256": hashes, "flags": flags,
                "libctru_headers_sha256": {
                    p.relative_to(Path(dkp) / "libctru/include").as_posix():
                    hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in sorted((Path(dkp) / "libctru/include").rglob("*.h"))},
                "compiler": subprocess.check_output([str(compiler), "--version"], text=True)}
    receipt = output / "receipt.json"
    library = output / "libcitro3d.a"
    if library.is_file() and receipt.is_file():
        previous = json.loads(receipt.read_text())
        if previous.get("inputs") == identity and previous.get("library_sha256") == hashlib.sha256(library.read_bytes()).hexdigest():
            return library
    objects = []
    for source in files:
        if source.suffix not in (".c", ".s", ".S"):
            continue
        obj = output / (source.relative_to(VENDOR).as_posix().replace("/", "_") + ".o")
        subprocess.run([str(compiler), *flags, "-c", str(source), "-o", str(obj)], check=True)
        objects.append(str(obj))
    temporary = library.with_suffix(".tmp.a")
    if temporary.exists():
        temporary.unlink()
    subprocess.run([str(arm("arm-none-eabi-ar")),
                    "rcs", str(temporary), *objects], check=True)
    temporary.replace(library)
    receipt.write_text(json.dumps({"inputs": identity, "library_sha256":
        hashlib.sha256(library.read_bytes()).hexdigest()}, indent=2) + "\n")
    return library

