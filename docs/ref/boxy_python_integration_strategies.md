# Boxy → Python Integration Strategies (Python Consumers)

This doc lays out practical options to expose the Rust **boxy** renderer to Python, starting with a **zero-glue subprocess shim** and graduating to native bindings later. It includes API shape, packaging, testing, performance, and migration notes.

---

## 0) Goals & Constraints
- **Immediate usability** for Python users (data/ML, backend scripts, notebooks).
- **Minimal maintenance**: avoid duplicating complex config parsing in Python.
- **Parity with CLI** today; **direct native calls** optional later.
- **Stable contract**: JSON/YAML config as the public interface.
- **Cross‑platform**: Linux, macOS (Intel/ARM), Windows.

---

## 1) Quick Win: Subprocess “Shim” Package
A tiny Python package shells out to the existing CLI. Good enough for most workflows now.

### 1.1 API Shape (Python)
- **Simple function:** `render_from_config(cfg: dict|str, body: bytes|str=b"", *, extra_flags: list[str]|None=None) -> bytes`
- **Ergonomic wrapper:** `render(**kwargs) -> bytes` (builds config dict and delegates)
- **Optional**: file-like inputs/outputs for streaming.

### 1.2 Implementation Sketch
```python
# boxy/__init__.py
import subprocess, json, shlex
from typing import Any

class BoxyError(RuntimeError):
    pass

def _as_cfg_str(cfg: dict|str) -> str:
    return json.dumps(cfg) if isinstance(cfg, dict) else str(cfg)

def _as_bytes(b: bytes|str) -> bytes:
    return b.encode() if isinstance(b, str) else b

# Core shim

def render_from_config(cfg: dict|str, body: bytes|str=b"", *, extra_flags: list[str]|None=None, exe: str="boxy") -> bytes:
    args = [exe, "--config", _as_cfg_str(cfg)]
    if extra_flags:
        args += list(extra_flags)
    p = subprocess.Popen(
        args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    out, err = p.communicate(_as_bytes(body))
    if p.returncode != 0:
        raise BoxyError(err.decode(errors="replace"))
    return out
```

### 1.3 Streaming Variants
- **Input**: accept `body` as `bytes|str|IO[bytes]|Iterator[bytes]`.
- **Output**: return `bytes` by default; optionally stream to a sink (file path, IO).

```python
from typing import BinaryIO, Iterable

def render_stream(cfg, body: Iterable[bytes], *, chunk: int = 65536, exe: str="boxy") -> bytes:
    import subprocess
    p = subprocess.Popen([exe, "--config", _as_cfg_str(cfg)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        for part in body:
            p.stdin.write(part)
        p.stdin.close()
        out, err = p.communicate()
    finally:
        try: p.kill()
        except Exception: pass
    if p.returncode != 0:
        raise BoxyError(err.decode(errors="replace"))
    return out
```

### 1.4 Error Handling & Diagnostics
- Map non‑zero exit to `BoxyError` with stderr payload.
- Add `--log-level` passthrough.
- Optional `verbose=True` → logs command + timing.

### 1.5 Cross‑Platform Notes
- Use an environment variable `BOXY_EXE` to override path.
- Windows quoting via `subprocess.list2cmdline` (implicitly handled when passing `list` args).
- Handle `SIGPIPE`/broken pipe on Unix by consuming stdout/stderr fully.

### 1.6 Performance Pragmatics
- **Overhead**: process spawn & JSON parsing; usually fine for non‑microbatch workloads.
- Batch multiple renders by persistent process? (see §1.7)

### 1.7 (Optional) Long‑Lived Daemon Mode
If CLI supports it or can be added:
- Start `boxy --server` once.
- Speak a simple length‑prefixed protocol over stdin/stdout or a local socket.
- Python client pools connections → reduces spawn overhead dramatically.

### 1.8 Packaging the Shim
- `pyproject.toml` using PEP 517/518.
- **No native wheels**; pure Python. Depend on the external `boxy` binary.
- Post‑install check: `shutil.which("boxy")` with a friendly error.
- Optional extras: `boxy[server]` that pins `uvloop`/`anyio` if you add async client.

### 1.9 Public API Proposal (Python)
```python
# High-level sugar
from boxy import render, render_from_config, BoxyError

img = render(text="Hello", width=400, height=200, style={"border":"round"})
# Under the hood, build cfg → call render_from_config → return PNG/SVG bytes.
```

---

## 2) Config Handling Strategy (Stable Contract)
- **Single source of truth**: Rust library owns the schema.
- Python doesn’t replicate the full type system; it **serializes dict → JSON**.
- Provide a version field (`schema: int`) and defaulting rules in Rust.
- Emit helpful errors (key path, expected type) to stderr for the shim to relay.

**Migration tip:** keep a small Rust subcommand `boxy --validate-config` to test configs without rendering.

---

## 3) I/O Surfaces & Formats
- **Input**: bytes/text body; optionally MIME type hint (`--body-type text|markdown|json|…`).
- **Output**: bytes; MIME string discoverable via `--format` or content sniffing.
- Consider `--out-format png|svg|pdf` so the Python return is predictable.

---

## 4) Testing & CI
- **Golden files**: for deterministic outputs (SVG text or PNG checksum with fixed seed/fonts).
- **Property tests**: fuzz configs (Rust) + sanity calls (Python shim).
- **Round‑trip tests**: CLI vs shim parity (same config → same bytes).
- GitHub Actions matrix (3 OSes; Python 3.9–3.12).

Example pytest:
```python
def test_basic_png(tmp_path):
    from boxy import render
    out = render(text="hi", width=100, height=50)
    (tmp_path/"a.png").write_bytes(out)
    assert out[:8] == b"\x89PNG\r\n\x1a\n"
```

---

## 5) Documentation & UX
- README shows **two paths**: (A) pure shim usage; (B) CLI parity cheatsheet.
- Examples directory: notebook + script + server mode (if enabled).
- Clear error copy when `boxy` binary missing (install instructions per OS).

---

## 6) Security & Sandboxing
- Treat configs as untrusted input. Validate before rendering.
- Avoid shell‑=True; pass argv list only.
- Consider a `--safe-mode` in CLI restricting file access, fonts, or network.

---

## 7) Roadmap to Native Bindings (When Ready)
A forward path that doesn’t break users of the shim.

### 7.1 PyO3 + maturin (native module)
- Build `boxy_py` as `cdylib` using PyO3.
- Expose one **stable** function: `render_from_json(cfg_json: str, body: bytes) -> bytes`.
- Internally: `serde_json` → `BoxyConfig` → call core lib → return bytes.
- Release the GIL around CPU‑bound work.

### 7.2 Pythonic Wrapper Layer
- Keep **the same Python API** as the shim (`render`, `render_from_config`).
- Swap implementation behind a feature flag or runtime detection:
  - If native module imports → use it.
  - Else → fallback to subprocess shim.

### 7.3 Wheels & Compatibility
- Use `maturin build` to ship manylinux, macOS universal2, Windows wheels.
- CI builds matrix; publish to PyPI under the same package name (with extras):
  - `pip install boxy` → shim only (pure python + requires binary)
  - `pip install boxy[native]` → includes native extension wheels

### 7.4 Zero‑Copy & NumPy (optional)
- Accept `memoryview`/buffer for body to avoid copies.
- If integrating with arrays, support `numpy` crate for input/output.

---

## 8) Versioning & Deprecations
- Public contract is the **config schema**.
- Use semantic schema numbers and a `"schema": N` field.
- For breaking changes:
  1. Add deprecation warnings in CLI (`stderr`) and Python shim (`warnings.warn`).
  2. Support both schemas for one cycle.
  3. Remove old paths in next major.

---

## 9) Distribution Plan
- **Rust CLI**: published binaries (Homebrew tap, cargo install, GitHub Releases).
- **Python shim**: PyPI `boxy` (pure python). Post‑install check locates CLI.
- Optional meta‑installer: `pip install boxy-installer` that downloads the matching CLI binary for the user’s OS/arch.

---

## 10) Example: High‑Level Python API (User‑friendly)
```python
from dataclasses import dataclass, field
from typing import Literal, Any
import json
from .core import render_from_config  # subprocess or native under the hood

@dataclass
class Style:
    border: Literal["round","square"] = "round"
    padding: int = 1

@dataclass
class Config:
    width: int = 200
    height: int = 100
    style: Style = field(default_factory=Style)

def render(body: bytes|str = b"", **kwargs: Any) -> bytes:
    cfg = Config(**kwargs)
    cfg_json = json.dumps(cfg, default=lambda o: o.__dict__)
    return render_from_config(cfg_json, body)
```

---

## 11) Optional: Long‑Lived Service Mode (Advanced)
If render volume is high and startup is heavy:
- CLI implements `--server` JSON‑RPC over stdio or TCP.
- Python client keeps a connection pool; retries on crash; health checks.
- Back‑pressure via async generators for body/output streaming.

---

## 12) Checklists

### 12.1 Ship the Shim
- [ ] Decide public API (`render`, `render_from_config`).
- [ ] Implement subprocess wrapper + streaming variant.
- [ ] Friendly error messages; binary detection.
- [ ] Basic docs + examples; tests on 3 OSes.
- [ ] Publish to PyPI.

### 12.2 Prep for Native
- [ ] Stabilize JSON config schema & versioning.
- [ ] Factor core Rust lib cleanly from CLI.
- [ ] Add `render_boxy(cfg, body)` entrypoint in Rust.
- [ ] Prototype PyO3 module; benchmark vs shim.
- [ ] Plan wheels + CI matrix.

---

## 13) FAQs
**Q: Will process spawn kill performance?**  
A: For sporadic renders, no. For high‑QPS, use daemon mode or native bindings.

**Q: How do we keep Python API stable while lib evolves?**  
A: Make the JSON config the only contract; map new features to new fields; version it.

**Q: Can we support notebooks easily?**  
A: Yes—return `bytes` and provide helpers to display in Jupyter (e.g., PNG via IPython.display).

---

**TL;DR**: Ship the **subprocess shim** now; keep the **JSON config** as the stable contract; add **daemon mode** if needed; later, drop in **PyO3** under the same Python API for speed without breaking users.

