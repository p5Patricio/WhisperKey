# Changelog

## v1.4.3 — The indicator sits on the taskbar again

### Fixed

- **The recording indicator rests just above the taskbar**, instead of floating
  over a gap. Its position was measured against the full screen with a constant
  48px subtracted "for the taskbar", and that constant was scaled by the display
  DPI on top. On a 125% display with a 60px taskbar it reserved 80px, leaving
  53px of dead air.
- Position is now measured against the desktop **work area** that Windows
  reports, so the indicator lands correctly whatever the taskbar's height, and
  whichever edge it lives on — bottom, top, left or right. On a multi-monitor
  setup it uses the work area of the monitor the indicator is on.

## v1.4.2 — Silent startup, and the indicator back to its usual size

### Fixed — no console window at startup

- **Starting with Windows no longer flashes a terminal.** The application lives
  in the tray and has no console of its own, and on Windows launching a console
  program from such a process *creates a window* even when its output is
  redirected — it needs `CREATE_NO_WINDOW`. Two `nvidia-smi` lookups run at
  startup (GPU detection and model selection) and neither passed it, so the
  flash happened on every boot.
- Every child process in the package now goes through one helper that sets the
  flag, and a test fails the build if any module calls `subprocess` directly.

### Fixed — the indicator was too small and flickered

- **Back to its previous size.** The pill is drawn with Pillow, which measures
  fonts in pixels, while tkinter measures them in points. Passing the configured
  size straight through made it about 30% smaller than before. It is now
  converted using the same scaling factor tkinter applies, and the pill height
  comes from the font's line height rather than the ink box, so it no longer
  changes with accents or descenders.
- **The flicker is gone.** The window was being resized and re-shown on every
  frame of the status dot's pulse, eleven times a second. `UpdateLayeredWindow`
  already sets size and position, so that only happens when the size genuinely
  changes now.
- The pulse itself is slower and shallower — faster or deeper stops reading as
  breathing and starts reading as blinking.

### Tests

381 -> 410.

## v1.4.1 — Visual finish

### Fixed — the recording indicator was jagged

- **The floating indicator is drawn with real antialiasing.** Tkinter's canvas
  has none, so its rounded corners came out as hard stair-steps and the status
  dot as a pixelated blob. The pill is now drawn with Pillow at 4x and
  downsampled, then shown through a Windows layered window with **per-pixel
  alpha** so the smoothed edge blends against the desktop rather than against a
  transparency key colour. No new dependency: Pillow was already required.
- The non-Windows drawing path is unchanged and still used as a fallback.

### Fixed — windows looked unfinished

- **Stray line fragments are gone.** The design system set a border as the
  *default* for every frame, but nearly all frames are transparent and exist
  only for layout, so each one drew its own rounded corner. The result was
  pieces of line that started and ended nowhere, most visible beside the status
  dot. Borders are opt-in now: only real cards ask for one.
- **Scrollbars appear only when the content overflows.** A permanently visible
  scrollbar drew a vertical line down tabs that fit on screen.
- **The dropdown button blends into its field** instead of sitting beside it as
  a differently coloured block with a hard edge.
- **In the history, the timestamp aligns with the first line** of its dictation
  rather than floating at the vertical centre of a multi-line entry.

### Changed — setup wizard

- The progress bar moved to the top edge, full width: under the step text it
  read as a stray underline rather than as progress.
- Step content sits in a panel, and the navigation buttons have a footer with
  breathing room instead of being pressed against the window edge.

### Tests

369 -> 381. New coverage pins the opt-in border rule and the palette, so the
defect that caused the loose lines cannot come back unnoticed.

## v1.4.0 — Dictation experience and design system

### Fixed — words broken apart

- **Dictations no longer come back with spaces inside words** ("dedic ación",
  "organiz ar", "circun stancia"). whisper.cpp opens a segment at token
  boundaries and Whisper's tokenizer splits words into subword tokens, so a
  break lands mid-word regularly. Segments carry their own leading space when
  they start a new word and none when they continue one; stripping each segment
  and re-joining them with a space turned every one of those breaks into a
  literal space.

### Added — dictation feedback and control

- **The overlay stays on screen while transcribing.** Releasing the key used to
  hide it immediately, leaving no sign the application was still working until
  the text appeared. It now shows an animated indicator, and past three seconds
  it reports elapsed time so a long wait reads as progress.
- **Esc discards the dictation in progress** (`hotkeys.cancel`, configurable).
  Starting to speak and changing your mind had no exit other than finishing the
  sentence and deleting the text afterwards. The key is inert outside a
  recording, so it keeps working normally everywhere else.
- **Long dictations are transcribed while you are still speaking.** Once a
  recording passes 25 seconds it is cut at a natural pause and the finished part
  is transcribed in the background, so only the last segment is pending on
  release. A 34-second dictation now waits about one second instead of the whole
  recording. Cuts land on silence, never inside a word.
- **A short tone confirms the text was delivered.**
- Errors clear themselves after a few seconds instead of leaving a permanent
  badge on the desktop.

### Changed — perceived latency cut in half

Profiling a four-second dictation showed two thirds of the wait was fixed
`sleep` calls rather than the model, which already runs at 20-24x realtime.

- **The clipboard is confirmed, not waited on.** A blind 150 ms wait became a
  poll that returns as soon as the clipboard actually holds the text — a
  measured 3 ms typically, while still waiting when the system is genuinely
  slow.
- **The push-to-talk tail window became a ceiling instead of a delay.** Capture
  now ends as soon as the audio blocks covering the key release arrive (~62 ms
  at a 31 ms block period) rather than always running out 200 ms.

Together: roughly 545 ms down to 260 ms, without touching decoding quality.
Dynamic `audio_ctx` and greedy decoding were both measured and rejected — the
first degraded accuracy on GPU for no speed gain, the second traded accuracy for
13% of a wait that is no longer dominated by inference.

### Changed — visual design

- **A single design system** (`whisperkey/theme.py`): one blue-on-black palette,
  one type scale, one spacing scale, installed as the customtkinter theme so
  every window inherits it. Colors were previously chosen per widget, which is
  why the application looked assembled rather than designed.
- **The recording indicator is a dark rounded pill** with a breathing status
  dot, replacing the orange and red blocks.
- **All six settings tabs share one rhythm**: section headings, muted helper
  text, and a label-and-control row. Tab contents scroll, so no setting is cut
  off. The cancel key is exposed in the interface.
- **The setup wizard shows a progress bar**, and its back button no longer
  renders as a filled action button while disabled.

### Fixed — reliability

- **The settings window opens again.** `settings_gui.py` had carried a syntax
  error since 2026-08-15 and shipped broken in v1.2.0 and v1.3.0. No test
  imported the module, so the suite stayed green while the window was
  unopenable.
- The tray poller waits on the shutdown event instead of sleeping, so it exits
  immediately instead of lingering.
- The overlay logs a warning when its startup handshake expires instead of
  silently leaving the indicator half-built.
- Test runs no longer write practice dictations into the real history file.

### Tests

273 -> 363, and stable across repeated runs. New coverage parses and imports
every module and builds the settings and onboarding windows for real — an import
alone would not have caught either the syntax error or a layout manager
conflict.

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
