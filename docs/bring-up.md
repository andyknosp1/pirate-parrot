# Bring-up: first power-on and motor tuning

Do this once for each new prop, one stage at a time, checking each stage before the next. It
is written for someone who hasn't done this kind of wiring before.

## Stage 0: know your prop

1. Open the prop's control box and photograph every connector before unplugging anything.
2. Work out which plug goes where by unplugging one at a time and running the prop's own demo
   (what stopped working?).
3. Find the motor wires and measure their resistance with the meter's ohms range: small DC
   motors read a few ohms. Note which pair is which motor.
4. Read the label on the prop's power adapter (volts, amps) and check its polarity with the
   meter at the plug: red probe inside the plug's hole, black on the outer barrel. A positive
   reading means center positive.
5. Check the motor voltage is within the TB6612's range (4.5 to 13.5V). If not, use a different
   driver.

## Stage 1: software only

Set up the Pi ([software.md](software.md)) with `MOTORS=off`, then confirm the conversation,
mic and camera work with `parrot.py --keyboard`.

## Stage 2: amp and speaker

Wire the amp ([wiring.md](wiring.md)), add the `dtoverlay`, install `~/.asoundrc`, and play a
quiet test first. Then set `AMP_SD_PIN` if you wired the mute pin.

## Stage 3: motor driver logic

Wire the driver's logic side (3.3V rail, ground bus, AIN/BIN pins) with the motor adapter
**unplugged**. Run the continuity checks in [wiring.md](wiring.md).

## Stage 4: motor power

Connect the adapter through the barrel-jack screw adapter to VM and the ground bus. With the
Pi off, plug the adapter in and measure VM to GND: you should see the adapter's voltage. The
driver stays asleep while the Pi is off.

## Stage 5: motor wires

Unplug the adapter. Connect the motor wires to MOT.A (beak) and MOT.B (head). Measure across
each pair: a few ohms means the motor is connected.

## Stage 6: pulse tests

Stop the service (`sudo systemctl stop pirate-parrot`), plug in the motor adapter, keep fingers
clear, and start gentle:

```bash
./venv/bin/python tools/pulse_test.py jaw forward --power 0.4 --seconds 0.15
```

- **Nothing, or just a hum:** go stronger, e.g. `--power 0.8 --seconds 0.3`. The reference
  build needed 80% for both motors.
- **The beak opened, then closed by itself:** correct. Set `JAW_POWER` to that power.
- **The beak clamped or strained:** unplug, swap the two beak wires, and try again.
- **Head:** pulse `head forward` and `head backward` and note which way each turns. Set
  `HEAD_POWER` to the lowest power that turns it reliably.

Keep pulses short (the tool caps them at 1 second): a motor held against its end stop draws
its stall current.

## Stage 7: talking with motors

Set `MOTORS=on` in `.env` and restart. Watch, and ideally film from the side, while he talks:

- **Beak late or early:** adjust `JAW_LEAD_SECONDS` (default 0.04). Filming at 30 fps and
  stepping through frames is the easiest way to judge it.
- **Beak flutters on quiet sounds or misses soft words:** adjust `JAW_OPEN_LEVEL` and
  `JAW_CLOSE_LEVEL`.
- **Head drifts to one side over a few minutes:** if it ends up to his right, lower
  `HEAD_RIGHT_SCALE` a little (default 0.9); if to his left, raise it toward 1.0. Centre the
  head by hand before each test.
- **Straining or grinding:** lower the power or `HEAD_MOVE_SECONDS`.

## Stage 8: full rehearsal

With everything assembled, walk up like a visitor: check he greets you by what you're
wearing, have three or four exchanges, try both secret phrases, walk away for the goodbye, and
come back after 30 seconds to be greeted as a new visitor. Then do it again on the porch after
dark to check camera aim and lighting.
