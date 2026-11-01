# Changelog

## 1.0.0 (November 2026)

First public release, based on the "Rotwing" reference build used on Halloween 2026.

- Motion-triggered visits with costume-aware greetings from a camera photo.
- Streaming conversation: Deepgram Nova-3, Claude Haiku 4.5, ElevenLabs Flash v2.5.
- Kids and adult personalities with spoken switch phrases (tolerant of near-misses).
- Beak sync with a configurable lead; drift-resistant "there and back" head gestures.
- Amp mute via the MAX98357A SD pin, and a silence keepalive: no idle hiss or clicks.
- Re-checks when the first photo sees nobody; second thinking sound for slow replies.
- Pre-recorded clips (made with `make_clips.py`) for instant squawks and offline fallbacks.
- systemd service with logging to an HDMI console; `tools/pulse_test.py` for motor bring-up.
- Configurable character name (`PARROT_NAME`).
- Resilient to network blips: one retry per reply, keeps listening after an error, friendly
  offline lines, `tools/install-network-fixes.sh` (Wi-Fi power save off, watchdog, persistent
  logs), and a rotating log file in `logs/`.
