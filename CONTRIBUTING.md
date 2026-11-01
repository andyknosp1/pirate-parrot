# Contributing

Thanks for your interest in PiRate Parrot! This is a seasonal hobby project, so replies to
issues and pull requests may be slow outside of October.

## Ways to help

- **Share your build.** Open an issue (or a pull request adding a page under `docs/builds/`)
  describing your prop: what's inside, motor voltages and resistances, the power settings that
  worked, and photos you have the right to share.
- **Report bugs.** Include your Pi model, OS version, the relevant part of
  `journalctl -u pirate-parrot` (remove anything personal), and what you expected.
- **Improve the docs.** Clearer steps for first-time builders are especially welcome.
- **Code changes.** Keep them small and focused, and keep the program working on a Mac/PC with
  `--keyboard` and `MOTORS=off`.

## Ground rules

- **Never commit secrets** (`.env`, API keys, voice IDs) or generated audio (`sounds/`).
- **No photos, video or audio of other people's children** in issues or pull requests.
- Changes to the prompts must keep kids mode squeaky clean, keep `kids` as the default, and keep
  the rule that he comments only on costumes, never on people's bodies or faces.
- By contributing, you agree that your code is released under the MIT License and your
  documentation under CC BY 4.0, as described in `LICENSE` and `LICENSE-docs.md`.

## Development tips

- `python parrot.py --keyboard -v` runs the full conversation with verbose logs, no hardware.
- `python tools/pulse_test.py --help` for motor bring-up on the Pi.
- Format: standard library `logging`, plain functions, comments in plain English for builders
  who are new to Python.
