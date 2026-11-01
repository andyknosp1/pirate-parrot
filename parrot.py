#!/usr/bin/env python3
"""PiRate Parrot: a talking, costume-spotting Halloween parrot on a Raspberry Pi.

https://github.com/andyknosp1/pirate-parrot  (MIT License)

A visit: the motion sensor spots kids -> he greets them (by costume if the
camera can see them) -> then listens and replies, back and forth, until they
go quiet or leave. The skull button is a backup way to wake him.

Pipeline for each reply:
  mic -> Deepgram streaming speech-to-text
  -> Claude Haiku (streamed, sentence by sentence)
  -> ElevenLabs Flash streaming text-to-speech -> speaker
  with the jaw driven by the loudness of the audio as it plays.

Run on a Mac/PC for testing (Enter = kids walk up, b + Enter = button):
    python parrot.py --keyboard
Run on the Pi:
    python parrot.py
"""
import argparse
import asyncio
import collections
import difflib
import json
import logging
import os
import random
import re
import shutil
import subprocess
import sys
import threading
import time
import wave
from pathlib import Path
from urllib.parse import urlencode

import httpx
import numpy as np
import sounddevice as sd
from anthropic import AsyncAnthropic
from dotenv import load_dotenv
from websockets.asyncio.client import connect as ws_connect

HERE = Path(__file__).resolve().parent
load_dotenv(HERE / ".env")

from motors import Motors  # noqa: E402  (needs .env loaded first)
from camera import Camera  # noqa: E402

log = logging.getLogger("parrot")

# ---------------------------------------------------------------- settings
_missing = [k for k in ("DEEPGRAM_API_KEY", "ANTHROPIC_API_KEY", "ELEVENLABS_API_KEY",
                        "ELEVENLABS_VOICE_ID") if not os.getenv(k)]
if _missing:
    sys.exit("Missing in .env: " + ", ".join(_missing) +
             "\nCopy .env.example to .env and fill in your keys (see docs/software.md).")
DEEPGRAM_KEY = os.environ["DEEPGRAM_API_KEY"]
ANTHROPIC_KEY = os.environ["ANTHROPIC_API_KEY"]
ELEVEN_KEY = os.environ["ELEVENLABS_API_KEY"]
VOICE_ID = os.environ["ELEVENLABS_VOICE_ID"]

CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-haiku-4-5")
TTS_MODEL = os.getenv("ELEVENLABS_MODEL", "eleven_flash_v2_5")
STT_MODEL = os.getenv("DEEPGRAM_MODEL", "nova-3")


def _device(value):
    """Audio device from .env: blank = system default, a number = index, else a name."""
    if not value:
        return None
    return int(value) if value.isdigit() else value


MIC_DEVICE = _device(os.getenv("MIC_DEVICE", ""))
SPEAKER_DEVICE = _device(os.getenv("SPEAKER_DEVICE", ""))
# Output buffer in seconds. Too small and the Pi's audio goes choppy; 0.15 is safe.
SPEAKER_LATENCY = float(os.getenv("SPEAKER_LATENCY", "0.15"))
# His loudness, 0.0 to 1.0 (the amp has no volume knob). The beak ignores this.
SPEAKER_VOLUME = min(1.0, max(0.0, float(os.getenv("SPEAKER_VOLUME", "1.0"))))
# Start the beak this much earlier than the sound, to cover the start-up time
# of the motor (measured on video on the reference build: the beak trailed his voice by ~50 ms).
JAW_LEAD = float(os.getenv("JAW_LEAD_SECONDS", "0.04"))
# Amp mute: the amp's SD pin wired to this GPIO (BCM number). Blank = not wired.
# The amp stays off (silent, no hiss) except while he's speaking.
AMP_SD_PIN = os.getenv("AMP_SD_PIN", "")
AMP_HOLD_S = float(os.getenv("AMP_HOLD_SECONDS", "1.0"))  # stay on this long after speech
BUTTON_PIN = int(os.getenv("BUTTON_PIN", "17"))
PIR_PIN = os.getenv("PIR_PIN", "")
MAX_LISTEN_S = float(os.getenv("MAX_LISTEN_SECONDS", "8"))     # longest single answer
REPLY_WAIT_S = float(os.getenv("REPLY_WAIT_SECONDS", "6"))     # wait for them to start talking
MAX_TURNS = int(os.getenv("MAX_TURNS", "4"))                   # back-and-forths per group
GREET_COOLDOWN_S = float(os.getenv("GREET_COOLDOWN_SECONDS", "20"))  # rest between groups
# If the camera sees nobody while the motion sensor still sees movement, look again
# every RECHECK_S seconds, at most RECHECKS times.
RECHECK_S = float(os.getenv("RECHECK_SECONDS", "3"))
RECHECKS = int(os.getenv("RECHECKS", "5"))

# Modes: "kids" (default) or "adult" (sassier, a bit tipsy). Switch by saying a secret
# phrase to him. Use real, everyday words: made-up words get misheard.
START_MODE = os.getenv("START_MODE", "kids").lower()
FILLER_AFTER_S = float(os.getenv("FILLER_AFTER_SECONDS", "3.5"))  # second squawk if slow
RETRY_DELAY_S = float(os.getenv("RETRY_DELAY_SECONDS", "0.5"))  # pause before a retry
MAX_FAILS = int(os.getenv("MAX_FAILS", "2"))  # errors in one visit before he gives up
ADULT_PHRASE = os.getenv("ADULT_PHRASE", "open the rum locker")
KIDS_PHRASE = os.getenv("KIDS_PHRASE", "swab the deck")

MIC_RATE = 16000   # what we send to Deepgram
TTS_RATE = 22050   # what ElevenLabs sends back (pcm_22050 works on non-Pro plans)
SOUNDS = HERE / "sounds"
# The character's name, used in his prompts (the reference build is "Rotwing").
PARROT_NAME = os.getenv("PARROT_NAME", "Rotwing")

KIDS_PERSONA = """You are Rotwing, the undead parrot of a ghostly pirate ship. You are perched \
on a front porch on Halloween night, chatting with trick-or-treaters.

Rules:
- Stay in character: a cackling, cheeky old pirate parrot. Use pirate slang, the odd "Squawk!", \
and parrot habits like repeating a word ("Treasure, treasure!").
- Keep every reply to one or two short sentences, under 30 words. Kids are waiting in line.
- When it fits, end with a short, fun question so they answer you (their name, their candy \
haul, their favorite pirate treasure).
- Your audience is mostly young children. Keep it spooky-fun, never truly frightening, crude, \
rude, or mean. No gore, romance, alcohol, or real-world scary news.
- Compliment costumes enthusiastically when they mention them.
"""

ADULT_PERSONA = """You are Rotwing, the undead parrot of a ghostly pirate ship, perched on a \
front porch on Halloween night. The little ones have gone home, you've been at the captain's \
rum, and now you're holding court with the grown-ups.

Rules:
- Stay in character: a sassy, quick-witted, slightly tipsy old pirate parrot. Pirate slang, the \
odd "Squawk!" or "hic!", losing your thread now and then, tall tales that fall apart halfway \
through. Keep the tipsiness light: every word must stay easy to understand.
- Keep every reply to one or two short sentences, under 35 words.
- Tease them the way a funny friend would: roast their costumes, their candy-stealing, their \
pirate credentials. Joke about choices, never about the person: nothing about anyone's body, \
looks, age, race, gender, disability, or anything else they can't change. Never truly mean.
- Keep it PG-13 for a neighborhood porch: no profanity beyond pirate oaths like "blast" or \
"scallywag", and no sexual content or innuendo. You're the one who's had the rum: never urge \
anyone to drink, and never joke about drinking and driving.
- If a child is clearly speaking, or any children are visible in a photo, drop the rum talk and \
the roasting at once and be the friendly, squeaky-clean parrot for them.
- When it fits, end with a cheeky question so they answer you.
"""

COMMON_RULES = """
- When the chat is over (they say goodbye, or you're told it's your last reply), say a pirate \
goodbye and end with the exact marker [END].
- Never ask for personal details like last names, addresses, schools, or ages. First names are fine.
- If asked something inappropriate or off-limits, dodge it playfully in character and steer back \
to treasure, candy, ghosts, or the sea.
- Everything you write is spoken aloud: no emojis, asterisks, stage directions, or lists.
- Speech recognition may garble what they said. If it makes no sense, ask them to squawk it again.

What you can see:
- You usually get a photo of the people in front of you, taken just now. Treat it as what you \
see with your beady parrot eyes. Never mention a camera or a photo.
- React to what they're wearing and carrying: costumes, hats, masks, glasses and sunglasses, \
capes, wigs, face paint, props, candy bags. If they ask what you see or what they're wearing, \
answer from the photo.
- Only comment on clothing, accessories and props. Never comment on anyone's face, body, size, \
skin, hair, age, or anything else about the person themselves.
- If you're not sure what a costume is, describe it playfully ("a spooky green creature!") \
instead of guessing a name. If you can't make something out, say your old eyes are foggy \
rather than inventing it.
- Don't bring up their outfit in every reply; once per group is plenty unless they ask.
"""

SYSTEM_PROMPTS = {"kids": (KIDS_PERSONA + COMMON_RULES).replace("Rotwing", PARROT_NAME),
                  "adult": (ADULT_PERSONA + COMMON_RULES).replace("Rotwing", PARROT_NAME)}

GREET_PROMPT = ("(New visitors just walked up. Greet them in one short sentence, "
                "reacting to what they're wearing, then ask them one fun question to get them "
                "talking. If the photo clearly shows no people at all, reply with only the "
                "word NOBODY.)")
LAST_TURN_NOTE = ("\n\n(This is your last reply to this group: answer briefly, then give "
                  "them a cheerful pirate goodbye.)")
END_MARK = "[END]"

# ---------------------------------------------------------------- helpers
_SENTENCE = re.compile(r"(.+?[.!?]+[\"')\]]*)\s+", re.S)


def pop_sentences(buf: str):
    """Split finished sentences off the front of buf. Returns (sentences, remainder)."""
    out = []
    while True:
        m = _SENTENCE.match(buf)
        if not m:
            return out, buf
        out.append(m.group(1).strip())
        buf = buf[m.end():]


def _words(text: str) -> str:
    return " ".join(re.sub(r"[^a-z' ]", " ", text.lower()).split())


def heard_phrase(text: str, phrase: str) -> bool:
    """True if the secret phrase was said (ignoring case and punctuation). Close
    mishearings count too: "open the rum seller" for "open the rum locker"."""
    if not phrase:
        return False
    want, got = _words(phrase).split(), _words(text).split()
    if " ".join(want) in " ".join(got):
        return True
    n = len(want)
    for i in range(len(got) - n + 1):
        scores = [difflib.SequenceMatcher(None, a, b).ratio()
                  for a, b in zip(want, got[i:i + n])]
        # every word roughly right, and the phrase as a whole a close match
        if min(scores) >= 0.5 and sum(scores) / n >= 0.85:
            return True
    return False


def clean_for_speech(text: str) -> str:
    text = text.replace(END_MARK, "")
    text = re.sub(r"[*_#~`]", "", text).strip()
    return "" if text.strip(" .!").upper() == "NOBODY" else text


def load_clip(path: Path) -> bytes:
    """Load a WAV as 16-bit mono PCM at TTS_RATE (converting if needed)."""
    with wave.open(str(path), "rb") as w:
        rate, ch, width = w.getframerate(), w.getnchannels(), w.getsampwidth()
        raw = w.readframes(w.getnframes())
    if width != 2:
        raise ValueError(f"{path.name}: must be 16-bit WAV")
    s = np.frombuffer(raw, dtype=np.int16).astype(np.float32)
    if ch > 1:
        s = s.reshape(-1, ch).mean(axis=1)
    if rate != TTS_RATE:
        n = int(len(s) * TTS_RATE / rate)
        s = np.interp(np.linspace(0, len(s) - 1, n), np.arange(len(s)), s)
    return s.astype(np.int16).tobytes()


class Clips:
    """Pre-recorded clips (made by make_clips.py): sounds/<kind>/*.wav for kids mode and
    sounds/adult/<kind>/*.wav for adult mode. Adult mode falls back to the kids clip
    when it has none of that kind."""

    KINDS = ("greet", "think", "nohear", "goodbye", "fallback", "to_adult", "to_kids")

    def __init__(self):
        self.sets = {}
        for mode, folder in (("kids", SOUNDS), ("adult", SOUNDS / "adult")):
            self.sets[mode] = {}
            for kind in self.KINDS:
                files = sorted((folder / kind).glob("*.wav"))
                self.sets[mode][kind] = [load_clip(f) for f in files]
            log.info("loaded %s clips: %s", mode, ", ".join(
                f"{len(v)} {k}" for k, v in self.sets[mode].items() if v) or "none")

    def pick(self, kind, mode="kids"):
        clips = self.sets[mode].get(kind) or self.sets["kids"].get(kind) or []
        return random.choice(clips) if clips else None


# ---------------------------------------------------------------- microphone
def _find_alsa_mic():
    """On Linux (the Pi), record with ALSA's own `arecord`, which converts channels and
    sample rate for us and is more dependable there than PortAudio. Returns the device
    name to record from, or None to use sounddevice (Mac/Windows)."""
    if os.getenv("MIC_ALSA"):
        return os.getenv("MIC_ALSA")
    if not sys.platform.startswith("linux") or not shutil.which("arecord"):
        return None
    out = subprocess.run(["arecord", "-l"], capture_output=True, text=True).stdout
    cards = re.findall(r"^card (\d+): .*?\[(.*?)\], device (\d+):", out, re.M)
    want = str(MIC_DEVICE or "").lower()
    for num, name, dev in cards:
        if want and want in name.lower():
            return f"plughw:{num},{dev}"
    return f"plughw:{cards[0][0]},{cards[0][2]}" if cards else None


ALSA_MIC = _find_alsa_mic()


class Mic:
    """`async with Mic() as mic:` then read 16 kHz mono PCM chunks from mic.q."""

    _keepalive = None   # one shared silent-playback process (see keepalive())

    def __init__(self):
        self.q: asyncio.Queue = asyncio.Queue()
        self.chunks = 0
        self.proc = self.task = self.stream = None

    @classmethod
    async def keepalive(cls):
        """The reSpeaker XVF3800 on Linux only delivers mic audio while something is
        playing to its own output (they share a clock); recording alone fails with an
        I/O error. So play silence to it the whole time he's running."""
        if not ALSA_MIC or (cls._keepalive and cls._keepalive.returncode is None):
            return
        cls._keepalive = await asyncio.create_subprocess_exec(
            "aplay", "-q", "-D", ALSA_MIC, "-f", "S16_LE", "-r", str(MIC_RATE),
            "-c", "2", "-t", "raw", "/dev/zero",
            stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
        await asyncio.sleep(0.4)  # let it start before the first recording

    @classmethod
    def stop_keepalive(cls):
        if cls._keepalive and cls._keepalive.returncode is None:
            try:
                cls._keepalive.kill()
            except ProcessLookupError:
                pass

    async def __aenter__(self):
        loop = asyncio.get_running_loop()
        if ALSA_MIC:
            await self.keepalive()
            self.proc = await asyncio.create_subprocess_exec(
                "arecord", "-q", "-D", ALSA_MIC, "-f", "S16_LE", "-r", str(MIC_RATE),
                "-c", "2", "-t", "raw",
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            self.task = asyncio.create_task(self._pump())
            return self

        # Mic arrays like the reSpeaker send 2 channels; keep the first.
        ch = min(2, sd.query_devices(MIC_DEVICE, "input")["max_input_channels"])

        def on_audio(indata, frames, t, status):
            data = bytes(indata)
            if ch > 1:
                data = np.frombuffer(data, dtype=np.int16)[::ch].tobytes()
            loop.call_soon_threadsafe(self._put, data)

        self.stream = sd.RawInputStream(
            samplerate=MIC_RATE, channels=ch, dtype="int16",
            blocksize=int(MIC_RATE * 0.05), device=MIC_DEVICE, callback=on_audio)
        self.stream.start()
        return self

    def _put(self, data):
        self.chunks += 1
        self.q.put_nowait(data)

    async def _pump(self):
        n = int(MIC_RATE * 0.05) * 4  # 50 ms of 2-channel 16-bit audio
        try:
            while True:
                data = await self.proc.stdout.readexactly(n)
                self._put(np.frombuffer(data, dtype=np.int16)[::2].tobytes())
        except asyncio.IncompleteReadError:
            err = (await self.proc.stderr.read()).decode(errors="replace").strip()
            log.error("microphone (%s) stopped: %s", ALSA_MIC, err or "arecord exited")

    async def __aexit__(self, *exc):
        if self.proc:
            self.task.cancel()
            try:
                self.proc.kill()
            except ProcessLookupError:
                pass
            await self.proc.wait()
        elif self.stream:
            # Close off the main thread so a stuck audio driver can never freeze him.
            asyncio.get_running_loop().run_in_executor(None, self.stream.close)


async def mic_test(seconds=6):
    """python parrot.py --mic-test : shows a live level meter so you can check the mic."""
    print(f"Mic: {ALSA_MIC or MIC_DEVICE or 'system default'}. Talk for {seconds} seconds...")
    async with Mic() as mic:
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            try:
                data = await asyncio.wait_for(mic.q.get(), 1.0)
            except asyncio.TimeoutError:
                print("  (no audio arriving from the mic)")
                continue
            while not mic.q.empty():
                data = mic.q.get_nowait()
            peak = int(np.abs(np.frombuffer(data, dtype=np.int16)).max()) / 32768
            print("  " + "#" * int(peak * 60) + f" {peak:.2f}")
            await asyncio.sleep(0.25)
    print("Done. Bars should jump when you talk; if they stay near 0.00 the mic isn't heard.")


# ---------------------------------------------------------------- speaker
class Speaker:
    """Plays 16-bit mono PCM and moves the jaw with the loudness, 20 ms at a time."""

    def __init__(self, motors: Motors):
        self.motors = motors
        self.frame_bytes = int(TTS_RATE * 0.02) * 2
        self._buf = b""
        self.underflows = 0
        self.stream = sd.RawOutputStream(
            samplerate=TTS_RATE, channels=1, dtype="int16",
            device=SPEAKER_DEVICE, latency=SPEAKER_LATENCY)
        self.stream.start()
        # Keep a trickle of silence flowing whenever he isn't talking. If the audio
        # ever runs dry, the amp switches itself off and on again, which clicks.
        self._wlock = threading.Lock()
        self._last_sound = 0.0
        self._amp = None
        if AMP_SD_PIN:
            try:
                from gpiozero import DigitalOutputDevice
                self._amp = DigitalOutputDevice(int(AMP_SD_PIN), initial_value=False)
                log.info("amp mute on GPIO%s", AMP_SD_PIN)
            except Exception:
                log.warning("amp mute pin GPIO%s not available; amp stays on", AMP_SD_PIN)
        self._empty = self.stream.write_available  # free space when the buffer is empty
        threading.Thread(target=self._keepalive, daemon=True).start()
        # Sound comes out one buffer-length after we hand it over, so hold each
        # jaw movement back by the same amount to keep beak and voice together.
        delay_frames = max(1, round((self.stream.latency - JAW_LEAD) / 0.02))
        self._jaw_queue = collections.deque([0.0] * delay_frames, maxlen=delay_frames)
        log.info("speaker ready (buffer %.0f ms)", self.stream.latency * 1000)

    def _write(self, data: bytes):
        with self._wlock:
            return self.stream.write(data)

    def _amp_wake(self):
        self._last_sound = time.monotonic()
        if self._amp and not self._amp.value:
            self._amp.on()

    def _keepalive(self):
        silence = b"\0" * self.frame_bytes
        low = self._empty - 5 * (self.frame_bytes // 2)  # keep ~100 ms queued
        while True:
            time.sleep(0.01)
            if (self._amp and self._amp.value
                    and time.monotonic() - self._last_sound > AMP_HOLD_S):
                self._amp.off()
            try:
                with self._wlock:
                    if self.stream.write_available > low:
                        self.stream.write(silence)
            except Exception:
                log.exception("speaker keepalive")
                time.sleep(1)

    def _jaw(self, level: float):
        delayed = self._jaw_queue[0]
        self._jaw_queue.append(level)  # maxlen drops the oldest
        self.motors.jaw(delayed)

    def play(self, pcm: bytes):  # blocking; call from a thread
        self._buf += pcm
        fb = self.frame_bytes
        while len(self._buf) >= fb:
            frame, self._buf = self._buf[:fb], self._buf[fb:]
            s = np.frombuffer(frame, dtype=np.int16).astype(np.float32)
            self._jaw(float(np.sqrt(np.mean(s * s))) / 32768.0)
            if SPEAKER_VOLUME < 1.0:
                frame = (s * SPEAKER_VOLUME).astype(np.int16).tobytes()
            self._amp_wake()
            if self._write(frame):
                self.underflows += 1

    def finish(self):  # blocking
        if self._buf:
            tail = self._buf + b"\0" * (len(self._buf) % 2)
            self._buf = b""
            self._amp_wake()
            self._write(tail)
        for _ in range(len(self._jaw_queue)):  # let the last sounds (and jaw moves) play out
            self._jaw(0.0)
            time.sleep(0.02)
        self.motors.jaw(0.0)
        if self.underflows:
            log.debug("audio buffer ran dry %d times", self.underflows)
            self.underflows = 0


# ---------------------------------------------------------------- the parrot
class Parrot:
    def __init__(self, motors: Motors):
        self.motors = motors
        self.speaker = Speaker(motors)
        self.clips = Clips()
        self.camera = Camera()
        self.claude = AsyncAnthropic(api_key=ANTHROPIC_KEY)
        self.http = httpx.AsyncClient(timeout=httpx.Timeout(10.0, read=20.0))
        self.history = []
        self.last_visit_end = -1e9
        self.mode = START_MODE if START_MODE in SYSTEM_PROMPTS else "kids"
        log.info("mode: %s", self.mode)

    # ---- audio output ---------------------------------------------------
    async def _player(self, q: asyncio.Queue):
        loop = asyncio.get_running_loop()
        self.motors.talking(True)
        try:
            while (chunk := await q.get()) is not None:
                await loop.run_in_executor(None, self.speaker.play, chunk)
            await loop.run_in_executor(None, self.speaker.finish)
        finally:
            self.motors.talking(False)

    async def play_clip(self, kind):
        clip = self.clips.pick(kind, self.mode)
        if clip is None:
            log.warning("no %s clips; run make_clips.py", kind)
            return
        q = asyncio.Queue()
        await q.put(clip)
        await q.put(None)
        await self._player(q)

    # ---- listening ------------------------------------------------------
    async def listen(self, start_timeout: float) -> str:
        """Stream the mic to Deepgram until they stop talking. Returns the transcript
        ("" if nobody started talking within start_timeout seconds)."""
        loop = asyncio.get_running_loop()
        params = [
            ("model", STT_MODEL), ("encoding", "linear16"), ("sample_rate", MIC_RATE),
            ("channels", 1), ("smart_format", "true"), ("interim_results", "true"),
            ("endpointing", 300), ("utterance_end_ms", 1000), ("vad_events", "true"),
        ]
        if STT_MODEL.startswith("nova-3"):  # help it catch the secret mode phrases
            params += [("keyterm", p) for p in (ADULT_PHRASE, KIDS_PHRASE) if p]
        url = "wss://api.deepgram.com/v1/listen?" + urlencode(params)
        finals = []

        # Open the mic first so nothing is lost while the websocket connects.
        log.info("listening...")
        async with Mic() as mic:
            async with ws_connect(url, open_timeout=8, close_timeout=2, additional_headers={
                    "Authorization": f"Token {DEEPGRAM_KEY}"}) as ws:
                log.debug("connected to Deepgram")

                async def sender():
                    while True:
                        await ws.send(await mic.q.get())

                send_task = asyncio.create_task(sender())
                deadline = loop.time() + start_timeout
                heard = False
                try:
                    while (remaining := deadline - loop.time()) > 0:
                        try:
                            msg = await asyncio.wait_for(ws.recv(), remaining)
                        except asyncio.TimeoutError:
                            break
                        data = json.loads(msg)
                        kind = data.get("type")
                        text = ""
                        if kind == "Results":
                            text = data["channel"]["alternatives"][0]["transcript"]
                        if not heard and (kind == "SpeechStarted" or text):
                            heard = True  # they started talking: give them time to finish
                            deadline = loop.time() + MAX_LISTEN_S
                        if kind == "Results":
                            if data.get("is_final") and text:
                                finals.append(text)
                            if data.get("speech_final") and finals:
                                break
                        elif kind == "UtteranceEnd" and finals:
                            break
                finally:
                    send_task.cancel()
                    try:
                        await ws.send(json.dumps({"type": "CloseStream"}))
                    except Exception:
                        pass
            if mic.chunks == 0:
                log.error("no audio arrived from the microphone; run: python parrot.py --mic-test")
        return " ".join(finals).strip()

    # ---- thinking + speaking ---------------------------------------------
    async def _tts(self, text: str):
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}/stream"
        async with self.http.stream(
                "POST", url, params={"output_format": f"pcm_{TTS_RATE}"},
                headers={"xi-api-key": ELEVEN_KEY},
                json={"text": text, "model_id": TTS_MODEL}) as r:
            if r.status_code != 200:
                body = (await r.aread())[:300]
                raise RuntimeError(f"ElevenLabs {r.status_code}: {body!r}")
            async for chunk in r.aiter_bytes():
                yield chunk

    async def _tts_worker(self, sentences: asyncio.Queue, audio_q: asyncio.Queue, state):
        while (s := await sentences.get()) is not None:
            log.info("parrot: %s", s)
            async for chunk in self._tts(s):
                state["spoke"] = True
                await audio_q.put(chunk)

    async def _think(self, question: str, sentences: asyncio.Queue, image=None,
                     extra: str = "") -> str:
        content = question + extra
        if image:  # this turn only; photos are never kept in the history
            content = [{"type": "image", "source": {"type": "base64",
                        "media_type": "image/jpeg", "data": image}},
                       {"type": "text", "text": question + extra}]
        messages = self.history + [{"role": "user", "content": content}]
        reply, pending = "", ""
        async with self.claude.messages.stream(
                model=CLAUDE_MODEL, max_tokens=150, system=SYSTEM_PROMPTS[self.mode],
                messages=messages) as stream:
            async for delta in stream.text_stream:
                reply += delta
                done, pending = pop_sentences(pending + delta)
                for s in done:
                    if (s := clean_for_speech(s)):
                        await sentences.put(s)
        if (s := clean_for_speech(pending)):
            await sentences.put(s)
        return reply

    async def respond(self, question: str, image=None, squawk=True, extra: str = "",
                      history_text: str = None):
        """Think and speak a reply. Returns the reply text, or None if it failed."""
        reply = None
        audio_q: asyncio.Queue = asyncio.Queue()
        sentences: asyncio.Queue = asyncio.Queue()
        state = {"spoke": False}
        player = asyncio.create_task(self._player(audio_q))

        # Instant short squawk so there's no dead air while the answer is made.
        if squawk and (think := self.clips.pick("think", self.mode)) is not None:
            await audio_q.put(think)

        async def filler():  # a slow answer gets a second "thinking" noise
            await asyncio.sleep(FILLER_AFTER_S)
            if not state["spoke"] and (c := self.clips.pick("think", self.mode)) is not None:
                log.info("slow reply; playing a second thinking sound")
                await audio_q.put(c)
        fill = asyncio.create_task(filler()) if squawk else None
        try:
            for attempt in (1, 2):
                sentences: asyncio.Queue = asyncio.Queue()
                tts = asyncio.create_task(self._tts_worker(sentences, audio_q, state))
                try:
                    text = await self._think(question, sentences, image, extra)
                    await sentences.put(None)
                    await tts
                    reply = text
                    self.history += [{"role": "user", "content": history_text or question},
                                     {"role": "assistant", "content": reply}]
                    self.history = self.history[-12:]
                    break
                except Exception as e:
                    tts.cancel()
                    if attempt == 1 and not state["spoke"]:
                        # Nothing said yet: one quiet retry covers most blips.
                        log.warning("reply failed (%s: %s); retrying once",
                                    type(e).__name__, e)
                        await asyncio.sleep(RETRY_DELAY_S)
                        continue
                    log.exception("reply failed (is the internet down?)")
                    if not state["spoke"] and (fb := self.clips.pick("fallback", self.mode)) is not None:
                        await audio_q.put(fb)
                    break
        finally:
            if fill:
                fill.cancel()
            await audio_q.put(None)
            await player
        return reply

    # ---- a visit ----------------------------------------------------------
    async def visit(self, trigger: str):
        """One group of trick-or-treaters, from hello to goodbye."""
        self.history = []  # every group gets a fresh conversation
        image = self.camera.snapshot()
        greeted_with_image = False

        fails = 0  # errors this visit; he keeps going until MAX_FAILS

        if trigger == "motion":
            if image:
                reply = await self.respond(GREET_PROMPT, image, squawk=False,
                                           history_text="(New trick-or-treaters walked up.)")
                if reply is None:
                    fails += 1  # fallback line already played; still listen for them
                    log.info("greeting failed, fallback line played; listening anyway")
                elif reply.strip(" .!").upper() == "NOBODY":
                    log.info("motion, but nobody in view; staying quiet")
                    return "nobody"
                else:
                    greeted_with_image = True
            else:
                await self.play_clip("greet")

        turns, nudged = 0, False
        while turns < MAX_TURNS:
            self.motors.listening(True)
            try:
                heard = await self.listen(REPLY_WAIT_S)
            except Exception:
                fails += 1
                log.exception("listening failed (is the internet down?)")
                if fails >= MAX_FAILS:
                    await self.play_clip("fallback")
                    log.info("visit over: %d errors this visit, fallback line played", fails)
                    return
                await asyncio.sleep(RETRY_DELAY_S)
                continue
            finally:
                self.motors.listening(False)
            log.info("heard: %s", heard or "(nothing)")

            # Secret phrases switch his personality (and don't count as a turn).
            new_mode = ("adult" if heard_phrase(heard, ADULT_PHRASE) else
                        "kids" if heard_phrase(heard, KIDS_PHRASE) else None)
            if new_mode:
                if new_mode != self.mode:
                    self.mode = new_mode
                    self.history = []
                    log.info("mode switched to: %s", self.mode)
                await self.play_clip("to_" + new_mode)
                continue

            if not heard:
                if turns == 0 and not nudged:  # shy kids get one nudge
                    nudged = True
                    await self.play_clip("nohear")
                    continue
                await self.play_clip("goodbye")
                log.info("visit over: no answer after %d exchange(s), said goodbye", turns)
                return

            turns += 1
            # A fresh look every turn, so he can answer "what am I wearing?" at any point.
            reply = await self.respond(
                heard,
                image=self.camera.snapshot(),
                extra=LAST_TURN_NOTE if turns >= MAX_TURNS else "")
            if reply is None:
                fails += 1
                if fails >= MAX_FAILS:
                    log.info("visit over: %d errors this visit", fails)
                    return
                log.info("reply failed, fallback line played; listening again")
                continue
            if END_MARK in reply:
                log.info("visit over: he said goodbye after %d exchange(s)", turns)
                return
        log.info("visit over: reached %d exchanges", turns)


# ---------------------------------------------------------------- main
async def main(keyboard: bool):
    loop = asyncio.get_running_loop()
    events: asyncio.Queue = asyncio.Queue()
    parrot = Parrot(Motors())
    await Mic.keepalive()

    def fire(name):
        return lambda: loop.call_soon_threadsafe(events.put_nowait, name)

    if keyboard:
        def on_key():
            line = sys.stdin.readline().strip().lower()
            events.put_nowait("button" if line == "b" else "motion")
        loop.add_reader(sys.stdin, on_key)
        print("Press Enter to simulate kids walking up (b + Enter = the skull button). "
              "Ctrl+C to quit.")
    else:
        from gpiozero import Button, MotionSensor
        button = Button(BUTTON_PIN, bounce_time=0.05)  # backup: button between pin and GND
        button.when_pressed = fire("button")
        if PIR_PIN:
            pir = MotionSensor(int(PIR_PIN))
            pir.when_motion = fire("motion")
        else:
            log.warning("PIR_PIN not set: only the button will wake him")
        log.info("ready: motion sensor on GPIO%s, backup button on GPIO%d",
                 PIR_PIN or "-", BUTTON_PIN)

    rechecks = 0
    while True:
        event = await events.get()
        rested = loop.time() - parrot.last_visit_end > GREET_COOLDOWN_S
        # Motion only counts after a short rest; a deliberate button press always does.
        if event == "button" or rested:
            result = await parrot.visit(event)
            if result == "nobody":
                # The camera saw nobody, so this wasn't a visit: no rest period. The
                # motion sensor only fires when motion starts, so while it still sees
                # movement, look again in a few seconds (people are often still walking
                # into view). Limited, so a swaying branch can't run up the bill.
                still_moving = (not keyboard) and PIR_PIN and pir.motion_detected
                if still_moving and rechecks < RECHECKS:
                    rechecks += 1
                    loop.call_later(RECHECK_S, events.put_nowait, "motion")
                else:
                    rechecks = 0
            else:
                rechecks = 0
                parrot.last_visit_end = loop.time()
        while not events.empty():  # ignore anything that happened while he was busy
            events.get_nowait()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--keyboard", action="store_true", help="use Enter instead of the GPIO button")
    ap.add_argument("--mic-test", action="store_true", help="show a live mic level meter")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")
    # Also keep a log file that survives reboots (logs/parrot.log, a few MB at most).
    if (log_file := os.getenv("LOG_FILE", "logs/parrot.log")):
        from logging.handlers import RotatingFileHandler
        path = Path(log_file) if Path(log_file).is_absolute() else HERE / log_file
        path.parent.mkdir(parents=True, exist_ok=True)
        fh = RotatingFileHandler(path, maxBytes=2_000_000, backupCount=5)
        fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        logging.getLogger().addHandler(fh)
    for noisy in ("httpx", "httpcore", "websockets", "anthropic"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    try:
        asyncio.run(mic_test() if args.mic_test else main(args.keyboard))
    except KeyboardInterrupt:
        pass
    finally:
        Mic.stop_keepalive()
        logging.shutdown()
        sys.stdout.flush()
        os._exit(0)  # never hang on exit, even if an audio driver is stuck
