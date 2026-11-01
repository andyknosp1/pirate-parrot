# Privacy and safety

A PiRate Parrot sees and hears the people who walk up to it, and on Halloween most of them
are children. Please read this before putting one on your porch.

## What happens to photos and audio

| Data | Where it goes | Kept by this program? |
|---|---|---|
| Camera photo (one per greeting and per reply, resized to 1024 px wide) | Sent to Anthropic's API with the conversation, so Claude can react to costumes | **No.** Held in memory for that one request, never written to disk, never added to the conversation history. |
| Microphone audio (only while he's listening for a reply) | Streamed to Deepgram for speech-to-text | **No.** Not recorded or saved. |
| What visitors said (text) | Sent to Anthropic as part of the conversation; kept in memory for the current group only | Cleared when the next group arrives. The text also appears in the program's log (`journalctl`) on the Pi. |
| His replies (text) | Sent to ElevenLabs to be spoken | Appears in the log. |

Each provider has its own data-retention and usage policies for API traffic. Read them for
Anthropic, Deepgram and ElevenLabs, and check any zero-retention options your account offers.

If you don't want transcripts in the Pi's log, lower the log level or clear the journal after
the event (`sudo journalctl --rotate && sudo journalctl --vacuum-time=1s`).

## What the prompts enforce

- He comments only on **costumes, clothing, accessories and props**, never on anyone's face,
  body, size, skin, hair or age.
- He never asks for last names, addresses, schools or ages.
- **Kids mode is the default at every start.** Adult mode is PG-13 at most, never urges anyone
  to drink, and switches back to kid-friendly behavior when a child is speaking or visible.
- Off-limits questions get a playful in-character dodge.

AI models can still make mistakes. Test both modes yourself before the event, keep an ear on
him, and unplug him if something goes wrong.

## Good practice

- **Tell people.** A small sign such as "This parrot can see and hear you!" by the door.
- **Aim the camera at your own porch,** not the street or a neighbor's property.
- **Don't publish photos, video or audio of visitors,** especially children, without their
  parents' permission. Film demos with your own family.
- **Check local rules.** Some places have rules about recording audio or video of the public
  or about notices; a sign helps in any case.
- **Protect your keys:** keep `.env` private, use keys with spending limits or prepaid credit,
  and rotate them if they might have leaked.
