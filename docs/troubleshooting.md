# Troubleshooting

These are the problems hit while building the reference parrot, and what fixed them.

## Audio

| Symptom | Cause | Fix |
|---|---|---|
| The program freezes waiting for the mic; Ctrl+C does nothing | The reSpeaker XVF3800 (firmware 2.06) only delivers mic audio on Linux while something plays to its own USB output | Built in: `parrot.py` records with `arecord` and keeps a silent `aplay` running to the reSpeaker. Run `parrot.py --mic-test` to check levels. |
| No audio arrives from the mic | Wrong device | Set `MIC_DEVICE` to part of the mic's name (e.g. `reSpeaker`). `arecord -l` lists devices. |
| Choppy voice | Audio buffer too small for the Pi | `SPEAKER_LATENCY=0.15` (raise to 0.25 if needed). |
| The amp refuses the audio ("Invalid sample rate") | The amp's raw device rejects 22050 Hz mono | Install `config/asoundrc.example` as `~/.asoundrc`. |
| No `MAX98357A` in `aplay -l` | Overlay missing | Add `dtoverlay=max98357a` to `/boot/firmware/config.txt` and reboot. |
| A click between talking and listening | The audio stream ran dry and the amp switched itself off and on | Built in: a background thread keeps silence queued. |
| Faint hiss between visits, ticks at startup | The amp is on whenever it has a clock | Wire the amp's SD pin to GPIO16 and set `AMP_SD_PIN=16`. |

## Motion and camera

| Symptom | Cause | Fix |
|---|---|---|
| Never wakes up | PIR not wired, still warming up, or aimed away | Check VIN/OUT/GND; wait 60 s after power-on. `pinctrl get 27` should flip between `lo` and `hi` as you move. |
| Wakes up but stays quiet ("motion, but nobody in view" in the log) | The camera can't see the visitor | Aim the camera where visitors stop, and light that spot. He re-checks every 3 s while there's motion. |
| Greets the street | Camera or PIR aimed at the sidewalk | Re-aim both at the porch. |
| Doesn't mention costumes after dark | Too dark for a useful photo (below `CAMERA_MIN_BRIGHTNESS`) | Add light on the visitors. He falls back to a pre-recorded greeting. |
| Blurry photos | Manual-focus lens | Twist the lens while checking test photos (`python camera.py` with the service stopped). |

## Motors

| Symptom | Cause | Fix |
|---|---|---|
| Motors hum but don't move | Not enough power | Raise `JAW_POWER` / `HEAD_POWER` (0.8 worked on the reference build). Jumper and breadboard contacts add a few ohms. |
| Motors don't move at all | Motor adapter unplugged, STBY not at 3.3V, or wires loose | Check the adapter first, then the continuity checks in [wiring.md](wiring.md). |
| Beak clamps shut instead of opening | Beak wires reversed | Swap the two beak wires. |
| Beak lags the voice | Motor start-up time | Raise `JAW_LEAD_SECONDS` a little (the reference build measured about 50 ms of lag). |
| Head drifts to one side | Gear slack and no position sensor | Adjust `HEAD_RIGHT_SCALE`; centre the head by hand before power-on. |

## Conversation

| Symptom | Cause | Fix |
|---|---|---|
| Secret phrase not recognized | Speech recognition near-miss | Matching tolerates close misses (e.g. "rum seller"); pick phrases made of common words. |
| Occasional replies take 5 to 6 seconds | Variable response time from the AI service | A second thinking sound plays after `FILLER_AFTER_SECONDS`. |
| Fallback lines every time ("me parrot brain be takin' a little nap") | A key is missing, wrong or expired, or no internet | Check the log for "is the internet down?"; rotate the key ([software.md](software.md)). He retries each reply once and keeps listening after an error, giving up on a visit only after `MAX_FAILS` errors. |
| Wrong personality | He's still in the mode set last | Every restart begins in `START_MODE` (kids); or say the kids phrase. |

## Pi and network

| Symptom | Cause | Fix |
|---|---|---|
| Can't find the Pi on the network | Its DHCP address changed | Reserve an address in your router. |
| Password rejected over SSH | Usually a typo (nothing is echoed while typing) | Type slowly; check Caps Lock; it's the password set in Raspberry Pi Imager. |
| `python: command not found` on a Mac inside an activated venv | Homebrew upgraded Python, breaking the venv | `python3 -m venv --clear <venv path>` and reinstall the requirements. |
| Works on the bench, then goes quiet or plays fallback lines on the porch for hours | Weak Wi-Fi at the porch: the Pi drops off and doesn't reconnect by itself (the reference build lost Wi-Fi for 3 hours on Halloween night) | Run `sudo bash tools/install-network-fixes.sh` and reboot: turns off Wi-Fi power saving, adds a watchdog that restarts Wi-Fi and finally reboots if the router stays unreachable, and keeps logs across reboots. Best of all, give him a strong signal: Ethernet, a powerline adapter, or an access point near the door. Check your router's client log for disconnects. |
| Logs from last night are gone | The Pi's journal is kept in memory by default | `logs/parrot.log` keeps his own log; `install-network-fixes.sh` also makes the journal persistent. |
| Log times are wrong just after boot | The Pi has no clock battery | Harmless: the clock corrects itself once online. |
