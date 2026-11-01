# Software

## Files

| File | What it does |
|---|---|
| `parrot.py` | The main program: motion trigger, visit loop, listening (Deepgram), thinking (Claude), speaking (ElevenLabs), the two personalities, audio output with beak sync, amp mute. |
| `motors.py` | Beak and head control. |
| `camera.py` | Background camera capture; `python camera.py` saves one test photo per camera it finds. |
| `make_clips.py` | Generates the pre-recorded lines (greetings, thinking squawks, nudges, goodbyes, fallbacks, mode switches) into `sounds/`. `--redo` remakes all of them. |
| `.env.example` | Every setting, documented. Copy to `.env`. |
| `pirate-parrot.service` | systemd unit: start on boot, restart on crash, log to the journal and HDMI console. |
| `config/asoundrc.example` | Points the Pi's default sound output at the MAX98357A amp. |
| `tools/pulse_test.py` | Sends one short pulse to a motor during bring-up. |
| `tools/install-network-fixes.sh` | Run once with sudo: Wi-Fi power saving off, a network watchdog, and persistent logs. `--remove` undoes it. |

## Accounts and keys

1. **Deepgram:** create an API key (pay as you go; streaming Nova-3 costs pennies per night).
2. **Anthropic:** in the Anthropic Console, add prepaid API credits and create an API key.
   Keys can have an expiry date: note it, and see "Rotating a key" below.
3. **ElevenLabs:** design a voice (see [voice.md](voice.md)) and copy its voice ID, plus an
   API key.

Put all four in `.env`. Never commit `.env` (the `.gitignore` already excludes it).

## Setting up the Pi

1. Flash **Raspberry Pi OS Lite (64-bit)** with Raspberry Pi Imager. In its settings, set a
   hostname (e.g. `pirate-parrot`), a user (`pi`), Wi-Fi and SSH.
2. Update and install tools:
   ```bash
   sudo apt update && sudo apt full-upgrade -y
   sudo apt install -y git python3-venv python3-gpiozero v4l-utils alsa-utils libportaudio2
   ```
3. Get the code and a virtual environment (with system packages, so `gpiozero` is available):
   ```bash
   git clone https://github.com/andyknosp1/pirate-parrot.git ~/pirate-parrot
   cd ~/pirate-parrot
   python3 -m venv --system-site-packages venv
   ./venv/bin/pip install -r requirements.txt
   cp .env.example .env && nano .env
   ./venv/bin/python make_clips.py
   ```
4. Enable the amp: add this line at the end of `/boot/firmware/config.txt` (under `[all]`),
   then reboot:
   ```
   dtoverlay=max98357a
   ```
   `aplay -l` should then list a `MAX98357A` card.
5. Point the default sound output at the amp (no sudo needed):
   ```bash
   cp config/asoundrc.example ~/.asoundrc
   ```
6. Optional, for a monitor on the HDMI port: keep the screen from blanking by appending
   ` consoleblank=0` to the single line in `/boot/firmware/cmdline.txt`.
7. Optional but recommended: reserve the Pi's IP address in your router, so you can always
   find it.
8. Recommended for any Wi-Fi install: `sudo bash tools/install-network-fixes.sh`, then reboot.
   A prop at the edge of Wi-Fi range tends to drop off and not come back on its own.

## Testing step by step

- **Mic:** `./venv/bin/python parrot.py --mic-test` shows a live level meter.
- **Camera:** `./venv/bin/python camera.py` saves a test photo per camera; set `CAMERA=on` and
  `CAMERA_DEVICE` in `.env`. Delete the photos afterwards.
- **Conversation without the motion sensor:** `./venv/bin/python parrot.py --keyboard`
  (Enter = someone walks up, `b` then Enter = button, Ctrl+C quits).
- **Motors:** keep `MOTORS=off` until you've done [bring-up.md](bring-up.md).

## Running on boot

```bash
sudo cp pirate-parrot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now pirate-parrot
```

| Task | Command |
|---|---|
| Watch the log | `journalctl -u pirate-parrot -f` (also shown on an HDMI monitor) |
| Stop (e.g. for bench work) | `sudo systemctl stop pirate-parrot` |
| Start / restart | `sudo systemctl start pirate-parrot` / `sudo systemctl restart pirate-parrot` |
| Shut down safely | `sudo poweroff`, wait about 15 seconds, then unplug |

Don't run `parrot.py` by hand while the service is running: both would fight over the mic,
amp and motors. The service file assumes the user `pi` and the folder `/home/pi/pirate-parrot`;
edit it if yours differ.

## Settings reference

Every setting is described in [`.env.example`](../.env.example). The ones you're most likely
to change:

| Setting | Default | Notes |
|---|---|---|
| `PARROT_NAME` | Rotwing | His name in prompts and clips. Re-run `make_clips.py --redo` after changing it. |
| `MIC_DEVICE` | blank | Part of the mic's name, e.g. `reSpeaker`. |
| `SPEAKER_VOLUME` | 1.0 | 0.0 to 1.0. Judge it with the prop assembled; the enclosure makes him louder. |
| `AMP_SD_PIN` | blank | `16` if the amp's SD pin is wired (recommended: removes idle hiss and clicks). |
| `CAMERA`, `CAMERA_DEVICE`, `CAMERA_CONTROLS` | off, 0, blank | See the comments in `.env.example`. |
| `MOTORS`, `JAW_POWER`, `HEAD_POWER` | off, 0.8, 0.8 | Set from your bring-up tests. `HEAD_POWER=0` keeps the head still. |
| `START_MODE` | kids | Keep this as `kids`. |
| `ADULT_PHRASE`, `KIDS_PHRASE` | open the rum locker, swab the deck | Use real, everyday words; matching tolerates near-misses. |
| `MAX_TURNS`, `GREET_COOLDOWN_SECONDS` | 4, 20 | Exchanges per group; rest between groups. |

## Rotating a key

Create the new key, then on the Pi paste it without it appearing on screen or in your shell
history:

```bash
cd ~/pirate-parrot && read -rsp "Paste new key: " K && \
  sed -i "s|^ANTHROPIC_API_KEY=.*|ANTHROPIC_API_KEY=$K|" .env && unset K && echo " saved"
sudo systemctl restart pirate-parrot
```

Test a walk-up, then delete the old key in the provider's console.

## How a visit works (for developers)

1. The PIR fires (`gpiozero.MotionSensor` on `PIR_PIN`). Motion is ignored during the rest
   period after a visit; the button always works.
2. `Camera.snapshot()` returns the latest frame as a JPEG (or `None` if off or too dark).
3. The greeting prompt and photo go to Claude. If Claude answers `NOBODY`, he stays quiet,
   no rest period starts, and he looks again every `RECHECK_SECONDS` while the PIR still sees
   motion (up to `RECHECKS` times).
4. `Parrot.listen()` streams the mic to Deepgram over a websocket and returns the transcript
   when the visitor stops talking. The secret phrases are passed to Deepgram as key terms.
5. `Parrot.respond()` streams Claude's reply, splits it into sentences, streams each one
   through ElevenLabs, and plays the audio. A thinking clip plays immediately, and another if
   nothing has been spoken after `FILLER_AFTER_SECONDS`.
6. `Speaker` plays 20 ms frames and passes each frame's loudness to `Motors.jaw()`, delayed by
   the audio buffer length minus `JAW_LEAD_SECONDS` so the beak lines up with the sound. A
   background thread keeps a little silence queued so the amp never switches off mid-visit.
7. If a reply fails before he has said anything, he retries once after `RETRY_DELAY_SECONDS`;
   otherwise he plays a fallback line and keeps listening. After `MAX_FAILS` errors in one
   visit he stops until the next group.
8. Claude ends a conversation with an `[END]` marker, or the visit ends after `MAX_TURNS` or
   on silence.

**reSpeaker note:** on Linux, the XVF3800 (firmware 2.06) only delivers mic audio while
something is playing to its own USB output. `parrot.py` therefore records with `arecord` and
keeps a silent `aplay` stream running to the reSpeaker.
