---
name: realtime-audio-pipeline
description: "Rules for the PortAudio capture thread, the audio queue and the transcription worker. Trigger: editing whisperkey/audio.py, state.py, hotkeys.py or transcription_worker, debugging dropped audio, cut words, or push-to-talk timing."
metadata:
  author: WhisperKey
  version: "1.0"
---

## When to Use

Load this skill before touching audio capture, the audio queue, the hotkey
handlers, or the transcription worker loop.

## The capture callback is a hard-realtime context

`sounddevice`'s callback runs on a PortAudio thread with a deadline. Miss it and
the driver drops frames — which reaches the user as **cut words**, not as an
error message.

Inside the callback, never:

- allocate or copy more than the one `indata.copy()` you must,
- take a lock that any slow path also takes,
- log at INFO or above per callback,
- call anything that touches Tk, the network, or the filesystem.

## Never drop audio silently

A bounded queue that discards on overflow is a data-loss path wearing a
correctness costume. In v1.2.0 the callback dropped the oldest chunk on `Full`
with no log line at all, so audio vanished from the middle of an utterance and
the transcription came back with words spliced together — with nothing anywhere
to explain why.

If you must drop, you must count and log it (rate-limited, off the callback
thread). A drop that leaves no trace is a bug that cannot be diagnosed from a
user's log.

Better: do not drop. Keep the consumer draining.

## Never block the consumer

The transcription worker is the only thing draining `audio_queue`. If it blocks
on inference (`requests.post(..., timeout=300)`), nothing drains the queue for
the entire duration — and any recording the user starts in that window fills the
queue and overflows.

Capture and inference must be decoupled: the loop that drains the queue must not
be the loop that waits on the engine. Hand the finished buffer to a separate
worker and go straight back to draining.

## Push-to-talk has a tail

When the key is released, the last audio block is still in flight on the
PortAudio thread. Sending the stop sentinel from the keyboard handler
immediately truncates the final word.

Give the capture thread a grace window (~200 ms) after the key release before
closing the buffer. The user perceives this as nothing; without it they perceive
it as the tool eating their last word.

The same applies in reverse at the start: a hotkey handler that sets a flag which
the callback reads has a delay of up to one block.

## Do not starve the audio thread

The transcription engine and the audio callback compete for the same cores.
`threads = os.cpu_count()` hands every core to the engine and the capture
callback misses its deadline — which then trips watchdogs and drops frames.

Leave headroom: `max(1, cpu_count - 2)`. On GPU the engine barely needs CPU
threads at all.

## Watchdogs must not destroy user data

A watchdog that detects a stall and responds by wiping the recording buffer
converts a hiccup into total data loss. Detect, log, recover — do not discard
audio the user already spoke.

Always use `time.monotonic()` for elapsed-time checks. `time.time()` moves with
NTP corrections and DST, so a wall-clock watchdog can fire on a machine that is
working perfectly.

## Threading rules for AppState

Every field crossing threads goes through the lock — reads included. A read of
`state.model` without the lock can observe a server that another thread is in the
middle of stopping. Getters that lock and direct attribute reads that do not is
the worst of both worlds: it looks synchronized and is not.
