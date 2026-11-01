# His voice

PiRate Parrot doesn't ship a voice or any audio. You design your own in ElevenLabs, which
keeps your parrot unique and keeps you within ElevenLabs' terms for the audio you generate.

## Designing the voice

In ElevenLabs, open **Voices > Add a new voice > Voice Design** and describe the character.
A starting point you can adapt:

> An old, cackling pirate parrot. High-pitched, raspy and nasal, with a gravelly West Country
> pirate accent. Quick, bouncy, mischievous delivery with lots of energy, as if he's about to
> squawk at any moment. Theatrical and playful, never scary. Clear enough for children to
> understand every word.

Generate a few previews, pick the one you like, save it, and copy its **voice ID** into
`ELEVENLABS_VOICE_ID` in `.env`. Voice Design needs a paid plan; check ElevenLabs' current
plans and terms, especially if your display is for a business or event.

## Live replies vs pre-recorded clips

- Live replies use `ELEVENLABS_MODEL` (default `eleven_flash_v2_5`), chosen for speed.
- Pre-recorded clips use `CLIPS_MODEL` (default `eleven_multilingual_v2`), which sounds a
  little richer and isn't time-critical.

Both use the same voice, so he sounds like one character.

## Making the clips

```bash
./venv/bin/python make_clips.py          # makes any clips that don't exist yet
./venv/bin/python make_clips.py --redo   # remakes all of them
```

This fills `sounds/` with greetings (used when it's too dark for the camera), thinking
squawks, nudges for shy kids, goodbyes, offline fallbacks and the mode-switch lines, plus
adult-mode versions in `sounds/adult/`. Edit the lines at the top of `make_clips.py` to give
him your own catchphrases; `Rotwing` in a line is replaced with `PARROT_NAME`.

`sounds/` is in `.gitignore`: please don't commit generated audio.

## Ideas

- Generate real parrot squawks, wing flaps or an arrival sound with ElevenLabs' sound effects
  model and drop the WAV files into `sounds/think/` (16-bit WAV; other sample rates are
  converted automatically).
- Avoid continuous background audio (waves, creaking): the mic would hear it.
