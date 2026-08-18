# Changelog

## v1.3.0 — Transcription accuracy and stability

This release fixes the accuracy regression introduced by the whisper.cpp
migration in v1.2.0, and hardens the audio pipeline against the silent data loss
that caused words to be cut or glued together.

### Fixed — transcription accuracy

- **The configured prompt reached the decoder again.** Old whisper.cpp builds
  accept every `/inference` form field and silently discard all of them,
  answering `200 OK` with a transcription computed from the startup flags alone.
  The bilingual prompt, the language and the decoding options were being thrown
  away. The engine is now probed at startup and every option is delivered through
  a surface the running build actually parses — request fields when supported,
  CLI flags otherwise.
- **The CUDA engine is found after download.** The CUDA release zip extracts into
  a `Release/` subdirectory that binary resolution never inspected, so the engine
  was re-downloaded (~670 MB) on *every single launch*, failed to resolve, and
  silently fell back to CPU. Binary resolution now covers the nested layouts.
- **Dev and packaged builds run the same engine.** The development tree resolved
  a stale hand-copied binary while the installer shipped a current one.
- **The default model is `auto` again** (it had been downgraded to `tiny`).
  `auto` picks by available memory; `small` and above are markedly better at
  code-switched Spanish/English.
- **Beam search, non-speech suppression and optional VAD are configurable**
  (`beam_size`, `suppress_non_speech`, `vad`) and were restored after being lost
  in the migration.
- **Quiet microphones are normalized** towards a target RMS with a capped gain
  and a peak ceiling, instead of being sent to the encoder at whatever level the
  device produced.

### Fixed — cut and glued words

- **Push-to-talk no longer eats the last word.** Releasing the hotkey closed the
  buffer while the final audio block was still in flight on the capture thread.
  Capture now continues through a short grace window.
- **Audio is no longer discarded in silence.** Inference ran on the same thread
  that drained the audio queue, so starting a new dictation while the previous
  one transcribed overflowed the queue and dropped chunks with no log line at
  all. Capture and inference are now decoupled, and any drop is counted and
  reported.
- **The engine leaves CPU headroom.** It was taking every core, starving the
  audio callback into missing its deadline. It now leaves two cores free.
- **The capture watchdog uses a monotonic clock**, so NTP and DST corrections can
  no longer make it fire on a healthy machine.

### Fixed — reliability

- The engine restarts automatically if the server process dies; a crash used to
  disable transcription for the rest of the session with no visible error.
- Transcription failures now surface in the overlay instead of failing silently.
- Configuration is validated again (model name, device, channels, sample rate,
  durations, threads, beam size, language). Validation had been removed in the
  migration and never replaced.
- Stereo capture is downmixed instead of interleaved, which previously produced
  audio at double the apparent sample rate.
- Downloads retry on truncation and verify the received length; a single dropped
  connection used to abandon a 670 MB download.
- Archive extraction rejects entries that escape the destination directory.
- The application log rotates instead of growing without bound.
- Release assets now include a `.sha256` file, so the in-app updater verifies the
  installer before running it.

### Removed

- Dead configuration keys `model.compute_type` and `model.use_cpu_fallback`,
  left over from the faster-whisper engine and read by nothing.

## v1.2.0

- Migrated the transcription engine to C++ (whisper.cpp) with a resident server.
- Professional Windows installer and landing page.
