# Wiring

Always wire with the Pi **shut down and unplugged** and the motor adapter **unplugged**.

## Finding the Pi's pins

The 40-pin header has two rows. Pin 1 is the corner pin nearest the microSD card, on the
inner row. Odd pins (1, 3, 5...) run along the inner row; even pins (2, 4, 6...) along the
board edge. Pin 40 is the far corner on the edge row. GPIO numbers in `.env` are **BCM**
numbers, not physical pin numbers; both are listed below.

Pins 2 and 4 are the only 5V pins. Many cases put a fan on pin 4 (and ground on pin 6), so
this design feeds the breadboard's 5V rail from pin 2 and shares it.

## Breadboard power rails

| Rail | Fed from | Feeds |
|---|---|---|
| **5V rail**, red + line | Pi pin 2 | PIR VIN, amp Vin |
| **Ground bus**: the 5V rail's blue line | Pi pin 20 | Motor driver GND, barrel jack − (motor ground) |
| **3.3V rail** (other edge; label it with tape), red + line | Pi pin 1 | Motor driver Vcc, STBY, PWMA, PWMB |

Never connect the prop's motor power adapter to either rail's + line.

## Connections

| From | To | Purpose |
|---|---|---|
| PIR VIN | 5V rail + | Sensor power |
| PIR OUT | Pi pin 13 (GPIO27) | Motion signal (`PIR_PIN=27`) |
| PIR GND | Pi pin 14 | Ground |
| Amp Vin | 5V rail + | Amp power (5.5V max) |
| Amp GND | Pi pin 9 | Ground |
| Amp BCLK | Pi pin 12 (GPIO18) | I2S bit clock |
| Amp LRC | Pi pin 35 (GPIO19) | I2S left/right clock |
| Amp DIN | Pi pin 40 (GPIO21) | I2S audio data |
| Amp SD | Pi pin 36 (GPIO16) | Mute (`AMP_SD_PIN=16`): the amp is on only while he speaks |
| Amp GAIN | not connected | Default 9 dB |
| Amp + / − screw terminal | Prop's speaker | Polarity doesn't matter for one speaker |
| Driver Vcc, STBY, PWMA, PWMB | 3.3V rail + | Logic power and enables |
| Driver GND | Ground bus | Common ground |
| Driver AIN1 | Pi pin 16 (GPIO23) | Beak "forward" (`JAW_PIN_A=23`) |
| Driver AIN2 | Pi pin 18 (GPIO24) | Beak "backward" (`JAW_PIN_B=24`, not used in normal running) |
| Driver BIN1 | Pi pin 29 (GPIO5) | Head "forward" (`HEAD_PIN_A=5`) |
| Driver BIN2 | Pi pin 31 (GPIO6) | Head "backward" (`HEAD_PIN_B=6`) |
| Driver VM | Barrel jack + screw | Motor power from the prop's own adapter |
| Barrel jack − screw | Ground bus | Motor ground shared with the Pi |
| Driver MOT.A (2 pins) | Beak motor wires | |
| Driver MOT.B (2 pins) | Head motor wires | |
| Camera, microphone | Pi USB ports | |
| Optional backup button | Pi pin 11 (GPIO17) and any ground pin | `BUTTON_PIN=17` |

The PWMA and PWMB inputs are tied high, and the software drives speed with PWM on the
AIN/BIN pins. The TB6612's 10 control pins sit in a single row, so place the board across a
breadboard column (not along a row, which would join every pin together).

## Checks before the first power-on

Set your meter to continuity (beep), with everything unplugged:

| Probe 1 | Probe 2 | Expect |
|---|---|---|
| 5V rail + | ground bus | **no** beep |
| 3.3V rail + | ground bus | **no** beep |
| 3.3V rail + | 5V rail + | **no** beep |
| Barrel jack + | either rail + | **no** beep |
| Driver Vcc | Driver STBY, PWMA, PWMB | beep |
| Driver GND | a spare Pi ground pin (e.g. pin 39) | beep |
| Neighbouring solder joints on each board | each other | **no** beep |
| The two MOT.A joints | | a few ohms (the beak motor) |
| The two MOT.B joints | | a few ohms (the head motor) |

Then, with the motor adapter plugged in and the Pi still off, measure DC volts between the
driver's VM and GND: you should see the adapter's voltage (about 5.9V on the reference build).

## Soldering notes

The amp and motor driver come with loose header pins. Push the long ends into a breadboard,
set the board on top, and solder there: the breadboard holds everything straight. Tack one
corner pin, check the board sits flat, then do the rest. A good joint is a shiny cone that
covers the whole copper ring. Clean burnt rosin with rubbing alcohol so you can inspect for
bridges, then do the neighbouring-pin continuity check above.
