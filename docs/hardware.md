# Hardware

## Parts list

Prices are what the reference build paid in September 2026 (US); check current prices.

| Part | Purpose | Approx. price | Notes |
|---|---|---|---|
| Raspberry Pi 4 (2 GB+), case with fan, 5.1V 3A USB-C supply | Runs everything | already owned | A Pi 5 should also work but is untested. |
| microSD card, 16 GB+ | Raspberry Pi OS | already owned | |
| Seeed reSpeaker XVF3800 USB 4-mic array, **USB-only version, with case** | Microphone | $62.99 | Noise suppression copes with a crowd. Don't buy the XIAO ESP32-S3 version. |
| Arducam 1080P low-light USB camera (IMX291) | Costume recognition | | Any UVC webcam works; small and low-light is best for hiding it and for night. Manual-focus lens. |
| Adafruit MAX98357A I2S 3W class D amp (mono) | Drives the prop's speaker | $5.95 | Needs header and screw terminal soldered. |
| Adafruit TB6612 dual DC motor driver | Beak and head motors | $6.95 | Motor supply 4.5 to 13.5V, 1.2A continuous per channel. Needs headers soldered. |
| Adafruit mini PIR motion sensor | Wakes him | $3.95 | |
| 400-point solderless breadboard | Wiring | about $1 each in multipacks | Or solder onto an Adafruit Perma-Proto HAT (#2310) with an extra-tall stacking header for a sturdier build. |
| Jumper wires (male/male, female/female or female/male) | Wiring | a few dollars | Female ends onto the Pi's pins. |
| Female DC barrel jack to screw-terminal adapter | Brings the prop's power adapter to the motor driver | a few dollars | Get a pack with both 5.5 x 2.1 and 5.5 x 2.5 mm; the reference prop needed 2.1 mm. |
| Weatherproof box, outdoor power strip on a GFCI outlet | Porch install | | |
| Optional: 60 mm arcade button | Backup "wake up" button | $5.95 | Not used on the reference build. |

**Tools:** soldering iron (a temperature- or power-controlled station is much easier than a
basic wand iron), rosin-core solder (0.6 to 0.8 mm), a multimeter with continuity beep, and
a small flat screwdriver.

**Cloud accounts:** Deepgram, Anthropic Console (API credits, separate from any Claude
subscription) and ElevenLabs (a paid plan is needed for Voice Design voices and commercial
use; check their current terms).

## The reference prop: inside the Rotwing parrot

This section is specific to the Home Depot "Dead Water Animated LED Rotwing Parrot"
(26SV25390, by Seasonal Visions). For another prop, use it as an example of what to look for.

**Control box.** In the branch he perches on, behind a panel marked "C" with 4 corner screws.
It has a DC power jack (5.9V), a STEP PAD jack, a volume knob, a mode switch and the speaker
grille. Inside: one green board and the speaker. The factory hot-glues every connector; a few
drops of rubbing alcohol loosen the glue so plugs can be pulled out by their housings.

**Power adapter.** GQ18-059200-AU, 5.9V 2A, center pin positive (measured +5.96V unloaded).
Used for the motors only. Never connect it to the Pi or the amp.

**Speaker.** 4 ohm, 3W, on a white two-wire lead to the board's `SPK` socket. Unplug it and
push two male jumpers into the plug to connect it to the amp. The prop can be returned to
stock afterwards.

**Harness.** Four keyed plugs run from the control box up into the body:

| Label | Plug | Wires | Function | Used? |
|---|---|---|---|---|
| A1 | black | red, black, blue, teal | Both motors: red/black = beak (about 5.6 ohm), blue/teal = head (about 3 ohm) | Yes, to the motor driver |
| R1 | red | red, black, blue, teal | LED eyes | No, left on the stock board |
| N1 | white | red, orange, yellow | Probably the built-in motion sensor | No |
| Q1 | blue | red, teal, blue | Probably the built-in microphone | No |

**Motors.**

- **Beak:** opens when driven one way and springs shut when power stops. Driving it the other
  way forces it shut hard, so the software only ever drives it "forward". It needed about 80%
  power for 0.3 s to open.
- **Head:** turns side to side and reverses with polarity. It needed about 80% power (50% only
  hummed). There is no position sensor, so the software uses "there and back" gestures.

Always find a motor's behavior with short, gentle pulses first: see [bring-up.md](bring-up.md).

## Porch staging

- **Electronics box** (Pi, breadboard, barrel jack) right beside the prop's control box, since
  the jumper runs to the speaker and motor plugs are short. Raise it off the floor, add a few
  small vent holes low on the sides, and tape or glue the breadboard jumpers so moving the box
  can't pull one loose.
- **Speaker** back in its original place in the prop.
- **Camera** on the prop or its stand, aimed at the spot 3 to 6 ft in front where visitors
  stop, about chest height for kids, and **away from the street** (or he'll try to greet
  passers-by). Put a light on that spot, not into the lens. If he can't see people, he stays
  quiet. Focus the lens by hand once mounted.
- **Motion sensor** low and aimed at the last few steps of the approach; not at the street,
  heaters or lamps.
- **Microphone** between the prop and the visitors, under cover, at least a foot from the
  speaker.
- **Power:** plug in the motor adapter first, then the Pi. The PIR needs 30 to 60 seconds to
  warm up after power-on.
- **Head:** centre it by hand before powering on.
- A small sign such as "This parrot can see and hear you!" is a good idea (see
  [privacy.md](privacy.md)).
