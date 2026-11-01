#!/usr/bin/env python3
"""Send one short, gentle pulse to a motor, to learn what it does before turning MOTORS=on.

Stop the parrot service first (sudo systemctl stop pirate-parrot) and plug in the motor
power supply. Keep fingers clear. Start gentle and work up:

    python tools/pulse_test.py jaw forward --power 0.4 --seconds 0.15
    python tools/pulse_test.py jaw forward --power 0.8 --seconds 0.3
    python tools/pulse_test.py head forward --power 0.8 --seconds 0.4
    python tools/pulse_test.py head backward --power 0.8 --seconds 0.4

Pins come from .env (JAW_PIN_A/B, HEAD_PIN_A/B). On the reference build the beak opened on
"jaw forward" and closed by itself; never pulse a spring-return beak backward for long, it
forces it shut hard. If the beak clamps instead of opening, swap the two beak motor wires.
"""
import argparse
import os
import time
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

PINS = {
    "jaw": (int(os.getenv("JAW_PIN_A", "23")), int(os.getenv("JAW_PIN_B", "24"))),
    "head": (int(os.getenv("HEAD_PIN_A", "5")), int(os.getenv("HEAD_PIN_B", "6"))),
}


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("motor", choices=PINS)
    ap.add_argument("direction", choices=["forward", "backward"])
    ap.add_argument("--power", type=float, default=0.4, help="0.0 to 1.0 (default 0.4)")
    ap.add_argument("--seconds", type=float, default=0.15, help="pulse length (max 1.0)")
    args = ap.parse_args()
    power = min(max(args.power, 0.0), 1.0)
    seconds = min(max(args.seconds, 0.0), 1.0)  # short pulses only: motors can stall

    from gpiozero import Motor
    motors = {name: Motor(forward=a, backward=b) for name, (a, b) in PINS.items()}
    for m in motors.values():
        m.stop()
    time.sleep(0.3)
    m = motors[args.motor]
    (m.forward if args.direction == "forward" else m.backward)(power)
    time.sleep(seconds)
    m.stop()
    time.sleep(0.2)
    for m in motors.values():
        m.close()
    print(f"sent: {args.motor} {args.direction} at {power:.0%} for {seconds:.2f} s")


if __name__ == "__main__":
    main()
