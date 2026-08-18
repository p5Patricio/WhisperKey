---
name: whisper-engine-contract
description: "Rules for talking to the bundled whisper.cpp engine. Trigger: editing whisperkey/engine.py or transcription.py, changing decoding parameters, upgrading WHISPER_CPP_VERSION, debugging accuracy regressions, or resolving engine binaries."
metadata:
  author: WhisperKey
  version: "1.0"
---

## When to Use

Load this skill before changing anything that talks to `whisper-server`: decoding
parameters, binary resolution, engine downloads, or the `WHISPER_CPP_VERSION`
constant.

## The one rule that matters

**A parameter you send is not a parameter the engine honors.**

whisper.cpp's `/inference` endpoint silently ignores unknown form fields. It
returns `200 OK` with a perfectly valid transcription — computed with the
server's startup defaults, not with what you sent. There is no error, no warning,
nothing in the log. A stale binary will happily accept `prompt`, `beam_size` and
`language` and discard all three.

This is exactly how WhisperKey lost its Spanglish accuracy in v1.2.0: the dev
tree ran a v1.5.x binary whose `/inference` had no parameter table at all, so the
configured initial prompt never reached the decoder.

### Before you send a new parameter

1. Run `<engine>.exe --help` and confirm the flag exists.
2. Confirm the parameter is in the binary's request table, not just the CLI:
   ```bash
   python -c "import pathlib,re; b=pathlib.Path('<engine>.exe').read_bytes(); print([k for k in ('prompt','beam_size','vad','suppress_nst','temperature_inc','response_format') if k.encode() in b])"
   ```
   CLI flags and request fields are *different surfaces*. `--prompt` existing as a
   startup flag does not mean `prompt` is accepted per request.
3. A/B it: POST the same WAV twice, once with the parameter and once without. If
   the bytes are identical, the parameter is being ignored. Do not assume.

`whisperkey/engine.py` exposes `EngineCapabilities` for this — use it instead of
sending parameters blind. It parses `--help` once at startup and filters the
request payload down to what the running binary actually supports.

## Binary resolution

whisper.cpp release zips are **not flat**. `whisper-cublas-*.zip` extracts into a
`Release/` subdirectory; other builds extract flat. Always search the nested
layouts:

```python
for base in (bin_dir, bin_dir / "Release", bin_dir / "bin"):
    ...
```

Resolving only `bin_dir/whisper-server.exe` is how v1.2.0 ended up re-downloading
670 MB of CUDA engine on **every single launch** — the extraction succeeded, the
lookup failed, and the code fell back to CPU without telling anyone.

Executable names changed across versions: `whisper-server.exe` (>= 1.7) and
`server.exe` (older). Check both, newest name first.

## Dev and prod must run the same engine

`WhisperKey.spec` bundles `build/engine-cpu/Release` into `assets/bin`. If
`assets/bin` also holds a hand-copied binary from an older release, dev runs one
engine and users run another — and you will debug a bug your users do not have,
or ship one you cannot reproduce.

After bumping `WHISPER_CPP_VERSION`, verify the version actually on disk. The
constant is a declaration, not a fact.

## Accuracy levers, in order of real-world impact

Measured on this project, degraded 16 kHz speech, `ggml-base`:

1. **Model size.** `base` substitutes similar-sounding words on noisy input
   ("pull request" -> "pulrequez", "deploy" -> "Explorio"). This dominates
   everything else. `small` or better for code-switched Spanish/English.
2. **Audio completeness.** Truncated or spliced audio produces cut and glued
   words. See `realtime-audio-pipeline`.
3. **Initial prompt.** Steers vocabulary for technical Spanglish — but only if the
   engine actually honors it (see above).
4. **VAD.** Trims leading/trailing silence so the encoder does not hallucinate at
   the boundaries. Needs a separate Silero model file.
5. **Beam search.** Measurably smaller effect than the above. Do not lead with it
   when diagnosing an accuracy complaint.

Do not claim a decoding parameter fixed an accuracy problem without an A/B on the
same audio file.
