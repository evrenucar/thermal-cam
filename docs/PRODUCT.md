# Product direction

## What this is

A camera that prints. Point, shoot, and a thermal-paper photo comes out a few
seconds later. No screen to review on, no phone, no cloud, no app. The paper is
the photo.

## Target hardware — where this ends up

**Raspberry Pi Zero 2W.** Compact enough to hold in one hand, cheap enough that
the printer and battery dominate the bill of materials.

## Current hardware — where we are

**Raspberry Pi 5.** Not a product decision. It is what we have, and it makes
development faster: real CPU headroom, fast SD I/O, no patience required for a
rebuild. Everything written today should assume it will run on a Zero 2W
eventually.

### The gap that matters

| | Pi 5 (dev) | Pi Zero 2W (target) |
|---|---|---|
| CPU | quad Cortex-A76 @ 2.4 GHz | quad Cortex-A53 @ 1 GHz |
| RAM | 4–16 GB | 512 MB |
| Rough single-thread delta | — | ~5× slower |

Two consequences the current code has not paid for yet:

1. **The capture loop spins flat out** (`pi/main.py:436`) capturing 1640×1232
   RGB and running a LANCZOS resize plus Floyd–Steinberg dither in Python, then
   throws away almost every frame because the e-ink cannot keep up. On a Pi 5
   that wastes a core. On a Zero 2W it is likely the whole budget.
2. **512 MB is not much** once Picamera2 buffers and PIL intermediates are live
   at 1640×1232.

Neither is fixed here. Both are on the table in the grill session — see
[Open questions](#open-questions).

### Known Zero 2W gotcha: the serial port

The printer talks on `/dev/ttyAMA0` at 9600 baud (`pi/lib/int/config.py`). On a
Zero 2W the PL011 UART that backs `ttyAMA0` is claimed by Bluetooth by default,
which leaves the mini-UART (`ttyS0`) — whose baud rate drifts with CPU frequency
scaling. Given that the original bitmap corruption bug was a baud-rate mismatch,
an unstable baud rate is the last thing this project wants. Plan on
`dtoverlay=disable-bt` in `/boot/config.txt`, and verify before assuming.

## Short term: the plywood rig

Before anything is compact, everything gets mounted flat on **a single sheet of
plywood**: Pi, printer, camera, e-ink panel, buttons, power. All components
visible, all wiring reachable, nothing behind a panel.

The point is development and testing speed:

- Probe any wire without disassembly.
- Swap the Pi 5 for a Zero 2W by unscrewing one board.
- See the whole system state at a glance when something misbehaves.
- Reproduce a print fault without holding the thing together by hand.

**The plywood rig is a bench fixture, not a prototype enclosure.** It is not
supposed to look like the product, and time spent making it pretty is time
stolen from the product. Layout should be optimised for probe access and
component swaps.

## Browser emulator for the interface

There is currently no interface to speak of: `pi/lib/int/ui.py` is empty and the
menu button (GPIO 6) is wired to a callback that logs and returns. The preview,
the menu, and the interaction model all still have to be designed.

Designing them on the device is the slow way round. An e-ink refresh is ~1.5 s,
the rig has to be assembled and powered, and a layout tweak costs a redeploy.

**The emulator's job:** run the interface in a browser with no camera, no Pi and
no printer, so interaction design iterates in seconds.

What makes this cheap is that both output targets are tiny and fully specified:

| Target | Real device | In a browser |
|---|---|---|
| e-ink panel | 176×264, 1-bit | a `<canvas>`, 1-bit, scaled up |
| printer | 384 px wide, 1-bit | a tall `<canvas>` on a paper-coloured strip |
| 4 GPIO buttons | gpiozero callbacks | 4 on-screen buttons + keyboard |
| camera | Picamera2 | drop a file, paste an image, or webcam |

So the emulator is a faithful pixel target, not an approximation — if it looks
right at 176×264 1-bit, it looks right on the panel.

**The one real decision** is where the dithering runs, because that pipeline is
the part most likely to drift out of sync with the device:

- Reimplement Floyd–Steinberg in JS — no server needed, but two
  implementations that will disagree eventually.
- POST the image to `tools/serve.py` and have the real PIL pipeline return the
  bitmap — one implementation, always honest, but the emulator then needs Python
  and Pillow running locally.

This is a question in the grill, not a decision made here.

## Roadmap

| Stage | Goal | Status |
|---|---|---|
| 0 | Capture → e-ink → print works on Pi 5 | done |
| 1 | Plywood rig: every component mounted, powered, testable | next |
| 1b | Browser emulator for preview + menu, no hardware needed | proposed |
| 2 | Freeze the capture→print path; cut what the Zero 2W cannot afford | not started |
| 3 | Port to Pi Zero 2W on the same rig | not started |
| 4 | Compact form factor + power source | not started |

Stage 1b runs in parallel with 1 — it needs no hardware, which is the point.

Stage 2 before stage 3 is deliberate. Porting a moving target means debugging
the port and the features at the same time.

## Decisions — answered 2026-07-28

From the grill session (`tools/grill.html`).

| # | Decision |
|---|---|
| 1 | Novelty/art instant camera for friends **and** a commercial product later. Prototyping now. |
| 2 | Operated by Evren + friends, with a sentence of explanation. Product-grade robustness is a later concern. |
| 3 | **Internal LiPo + charger board.** |
| 4 | Live e-ink preview: **de-prioritised** — left as-is for now, revisit before the Zero 2W port. |
| 5 | E-ink is **multi-mode**: last photo + status, status/menu only, or photo-then-menu depending on state. |
| 6 | **Keep high resolution on disk.** The captured original is kept for reprocessing — crop and reposition are wanted features. Only the print path downscales. |
| 7 | Serial: **unknown, will test on hardware.** Hard constraint: **Bluetooth and WiFi must both stay usable** in the final device. |
| 8 | Emulator dithering: **JS and PIL both**, with the web version required to track the Pi version without extra maintenance. |
| 9 | Emulator covers everything, including simulated failures — **enable/disable and frequency configurable in settings.** |
| 10 | Menu button: **reprint last photo** confirmed. The rest waits until there's a device layout to look at. |
| 11 | Plywood rig: bench fixture, ugly is fine, but **mobile** — usable handheld like a camera. |
| 12 | Port to Zero 2W **after** the capture→print path is frozen **and** the emulator exists with the UI settled. |

### Consequences worth spelling out

**Battery (3).** The decision is made; this is the spec it has to meet. The
printer pulls roughly 1.5–2 A peaks while the head burns. "A competent battery"
therefore means a pack whose continuous discharge rating sits comfortably above
2 A and a protection board that will not trip on burn spikes. A pack that sags
under load produces faint or corrupt prints that look exactly like a software
bug — that is the failure mode to design against.

**Serial (7) — the earlier recommendation is void.** `dtoverlay=disable-bt` was
the clean fix, and it costs Bluetooth, which is now off the table. Two remaining
options:

- **Mini-UART (`ttyS0`) with the core clock pinned.** Keeps BT and WiFi. The
  mini-UART's baud tracks the core frequency, so it must be pinned
  (`enable_uart=1`, and pin `core_freq`/`core_freq_min`) or the baud drifts with
  the governor and the corruption bug returns intermittently.
- **USB-serial adapter.** Sidesteps the conflict entirely and is immune to clock
  scaling. Costs the OTG port and some bulk in a compact build.

Recommendation: test the mini-UART with a pinned clock first, keep USB-serial as
the fallback. This is a hardware test to run, not a decision to make on paper.

**Emulator (8) + web hosting.** GitHub Pages is static hosting — no Python runs
there. So the online emulator **must** dither in JavaScript; PIL cannot be in
the web path. "Both" resolves to: JS is authoritative for the browser, PIL stays
authoritative for the device, and a **parity test** feeds fixed input images
through both and asserts identical output. Drift then becomes a failing test
rather than an emulator that quietly lies. That is what makes it low-maintenance
rather than two things to hand-sync.

**Resolution (6) + emulator (9).** Keeping the high-res original for crop and
reposition makes editing a real feature, not a nice-to-have — which means the
emulator needs to model an edit state, not just capture → preview → print.
