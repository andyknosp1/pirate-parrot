#!/usr/bin/env python3
"""Generate the parrot's pre-recorded clips in his ElevenLabs voice.

These play instantly (greeting, the "thinking" squawk) or when the internet
is down, so they need to exist before Halloween. Edit the lines below, then:
    python make_clips.py            # makes any clips that don't exist yet
    python make_clips.py --redo     # remakes all of them
"""
import argparse
import os
import wave
from pathlib import Path

import httpx
from dotenv import load_dotenv

HERE = Path(__file__).resolve().parent
load_dotenv(HERE / ".env")

RATE = 22050
LINES = {
    # Played when kids walk up and the camera can't see them (off or too dark).
    "greet": [
        "Squawk! Ahoy, mateys! Who dares approach me ship? Tell ol' Rotwing yer names!",
        "Arr, fresh sailors! What treasure have ye plundered tonight?",
        "Squawk! Well shiver me feathers, visitors! Who be ye, mateys?",
    ],
    "think": [
        "Squawk!",
        "Hmm, arr...",
        "Rawk! Let me think...",
        "Ooh, ooh!",
    ],
    # One nudge for shy kids who don't answer the greeting.
    "nohear": [
        "Squawk? Speak up, matey! These old ears be full o' seawater!",
        "Arr, cat got yer tongue? Say somethin' to ol' Rotwing!",
    ],
    # When they go quiet or walk away.
    "goodbye": [
        "Fair winds, mateys! Grab yer treasure and sail on! Squawk!",
        "Arr, off ye go, sailors! Happy Halloween! Rawk!",
        "Squawk! Farewell, me hearties! Mind the ghosts on yer way!",
    ],
    # Played if something fails (e.g. no internet). Keep them warm, not "move along".
    "fallback": [
        "Squawk! Happy Halloween, matey! That be a fearsome costume!",
        "Arr, me parrot brain be takin' a little nap. Happy Halloween, matey! Squawk!",
        "Pieces of eight! Pieces of candy! Happy Halloween, me hearties! Squawk!",
    ],
}


# Extra lines for kids mode: what he says when you switch modes with a secret phrase.
LINES["to_adult"] = [
    "Squawk! The rum locker be open! Hic! Now we're talkin', matey!",
]
LINES["to_kids"] = [
    "Aye aye! Deck swabbed, beak washed! Best behavior, mateys! Squawk!",
]

# Adult mode (sassier, a bit tipsy). Kinds missing here fall back to the kids clips.
ADULT_LINES = {
    "greet": [
        "Squawk! Hic! Well well, who let this lot aboard? State yer business, or pass the rum!",
        "Arr, more landlubbers! Hic! Did ye bring rum, or just that sorry excuse for a costume?",
        "Ahoy! Hic. Either there be two of ye, or old Rotwing's had one too many. Who goes there?",
    ],
    "think": [
        "Hic!",
        "Hmm, hic, arr...",
        "Squawk! Where was I?",
    ],
    "nohear": [
        "Hic! Speak up! Me ears be pickled in rum!",
        "Arr, cat got yer tongue? Or did ye forget how to talk, like I forgot me own name? Hic!",
    ],
    "goodbye": [
        "Off with ye, then! More rum for Rotwing! Hic! Squawk!",
        "Fair winds, ye scallywags! Mind the step, it moves when I've been drinkin'! Hic!",
        "Squawk! Leavin' already? Fine! I was talkin' to the skeleton anyway!",
    ],
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--redo", action="store_true")
    args = ap.parse_args()
    name = os.getenv("PARROT_NAME", "Rotwing")  # his name in the lines below
    voice = os.environ["ELEVENLABS_VOICE_ID"]
    key = os.environ["ELEVENLABS_API_KEY"]
    # Clips aren't time-critical, so use the richer-sounding model if you like.
    model = os.getenv("CLIPS_MODEL", "eleven_multilingual_v2")
    with httpx.Client(timeout=60) as http:
        jobs = [(HERE / "sounds" / kind, kind, lines) for kind, lines in LINES.items()]
        jobs += [(HERE / "sounds" / "adult" / kind, kind, lines)
                 for kind, lines in ADULT_LINES.items()]
        for folder, kind, lines in jobs:
            folder.mkdir(parents=True, exist_ok=True)
            for i, text in enumerate(lines, 1):
                path = folder / f"{kind}_{i:02d}.wav"
                if path.exists() and not args.redo:
                    continue
                r = http.post(
                    f"https://api.elevenlabs.io/v1/text-to-speech/{voice}",
                    params={"output_format": f"pcm_{RATE}"},
                    headers={"xi-api-key": key},
                    json={"text": text.replace("Rotwing", name), "model_id": model})
                r.raise_for_status()
                with wave.open(str(path), "wb") as w:
                    w.setnchannels(1)
                    w.setsampwidth(2)
                    w.setframerate(RATE)
                    w.writeframes(r.content)
                print(f"made {path.relative_to(HERE)}: {text.replace('Rotwing', name)}")


if __name__ == "__main__":
    main()
