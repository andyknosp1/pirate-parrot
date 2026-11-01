# PiRate Parrot

**A talking, costume-spotting Halloween parrot powered by a Raspberry Pi.**

PiRate Parrot turns an animatronic Halloween parrot into a character that holds real
conversations with trick-or-treaters. When someone walks up, a motion sensor wakes him,
a small camera lets him see what they're wearing, and he greets them by their costume.
He listens, answers in a pirate-parrot voice, moves his beak in time with his words and
turns his head while he talks.

> "Ahoy there, me hearty in the smart spectacles! What be yer name, and have ye found any treasure tonight?"

The reference build, **Rotwing**, is a modified 5 ft animated parrot (the Home Depot
"Dead Water Animated LED Rotwing Parrot", item 26SV25390) that ran on a front porch for
Halloween 2026. The software is not tied to that prop: any animatronic with a DC motor
for the beak (and optionally the head) and a small speaker can be adapted.

**[Watch the demo video](https://www.youtube.com/shorts/qg-jDwzeedQ)** to see Rotwing in action.

## Features

- **Sees costumes.** A fresh photo with every turn, so he reacts to what visitors are
  wearing and carrying. He comments on costumes, accessories and props only, never faces
  or bodies. Photos are never saved.
- **Real conversation.** Streaming speech-to-text, a streamed AI reply spoken sentence by
  sentence, and an instant "thinking" squawk to hide the delay.
- **Two personalities.** Kid-friendly by default; a sassier, slightly tipsy PG-13 mode for
  grown-ups, switched by secret spoken phrases ("open the rum locker" and "swab the deck").
  Adult mode drops back to kid-friendly behavior if a child is speaking or visible.
- **Animatronic sync.** The beak follows the loudness of his voice (with a small lead to
  cover motor start-up); the head makes natural "there and back" gestures that stay centred
  without a position sensor.
- **Motion-triggered and hands-free.** Starts on boot, greets each new group, says goodbye,
  rests, and looks again if the first photo caught nobody.
- **Robust on a porch.** Canned fallback lines if the internet drops, a silent amp between
  visits (no hiss or clicks), and an optional live log on an HDMI monitor.

## How it works

```
motion sensor ──► photo ──► Claude (greeting about their costume)
                                     │
mic ──► Deepgram (speech to text) ──► Claude (reply, streamed sentence by sentence)
                                     │
                    ElevenLabs (voice) ──► amp ──► parrot's speaker
                                     │
                       loudness ──► beak motor     talking ──► head motor
```

| Job | Service | Default model |
|---|---|---|
| Hearing | Deepgram (streaming) | `nova-3` |
| Brain | Anthropic Claude | `claude-haiku-4-5` |
| Voice | ElevenLabs (your own designed voice) | `eleven_flash_v2_5` for replies, `eleven_multilingual_v2` for pre-recorded clips |

On the reference build, most replies start about a second after the visitor stops talking.
A busy Halloween night cost roughly 11 US dollars in cloud services (2026 prices).

## Hardware at a glance

| Part | Purpose |
|---|---|
| Raspberry Pi 4 (2 GB or more) | Runs everything |
| Seeed reSpeaker XVF3800 USB 4-mic array (USB-only version, with case) | Hears visitors in a noisy crowd |
| Arducam 1080P low-light USB camera (IMX291), or any small UVC webcam | Costume recognition |
| Adafruit MAX98357A I2S mono amp | Drives the prop's own speaker |
| Adafruit TB6612 dual motor driver | Beak and head motors |
| Adafruit mini PIR motion sensor | Wakes him up |
| Breadboard (or Perma-Proto HAT), jumpers, barrel-jack screw adapter | Wiring |

Full parts list, wiring tables and the reference prop's internals: [docs/hardware.md](docs/hardware.md)
and [docs/wiring.md](docs/wiring.md).

## Quick start

You can try the conversation on a Mac or PC first, with no hardware:

```bash
git clone https://github.com/andyknosp1/pirate-parrot.git
cd pirate-parrot
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # add your Deepgram, Anthropic and ElevenLabs keys and voice ID
python make_clips.py        # generate his pre-recorded lines in your voice
python parrot.py --keyboard # press Enter to pretend someone walked up
```

Then follow [docs/software.md](docs/software.md) to set up the Pi, and
[docs/bring-up.md](docs/bring-up.md) to connect and tune your prop's motors safely.

## Documentation

| Doc | What's in it |
|---|---|
| [hardware.md](docs/hardware.md) | Parts list, the reference prop's internals, porch staging |
| [wiring.md](docs/wiring.md) | Pin-by-pin wiring and safety checks |
| [software.md](docs/software.md) | Pi setup, `.env` reference, running as a service |
| [bring-up.md](docs/bring-up.md) | Step-by-step first power-on and motor tuning for a new prop |
| [voice.md](docs/voice.md) | Designing his voice in ElevenLabs and making his clips |
| [privacy.md](docs/privacy.md) | What the camera and mic send where, and good practice |
| [troubleshooting.md](docs/troubleshooting.md) | Problems hit on the reference build and their fixes |

## Privacy and safety

He photographs and listens to visitors, many of them children, and sends that data to
cloud AI services to reply. Please read [docs/privacy.md](docs/privacy.md) before you put
one on your porch. In short: photos and audio are never saved by this program, kids mode is
the default at every start, and a small sign telling visitors the parrot can see and hear
them is a good idea.

## Contributing

Builds on other props, bug fixes and ideas are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md).
This is a seasonal hobby project, so replies may be slow outside October.

## License

- Code: [MIT](LICENSE)
- Documentation, diagrams and photos: [CC BY 4.0](LICENSE-docs.md)

Not affiliated with or endorsed by The Home Depot, Seasonal Visions, Raspberry Pi,
Adafruit, Seeed, Arducam, Anthropic, Deepgram or ElevenLabs. Product names are used only to
describe compatibility.
