# Where we left off — 2026-07-28

Resume point for the review/design session. Delete this once it's stale.

## Grill: answered

All 13 answered on 2026-07-28 — recorded in
[PRODUCT.md § Decisions](PRODUCT.md#decisions--answered-2026-07-28).

Three answers changed the plan:

- **Bluetooth and WiFi must both stay usable**, which kills the
  `dtoverlay=disable-bt` fix for the printer's UART. Now a hardware test:
  mini-UART with a pinned core clock first, USB-serial as fallback.
- **GitHub Pages hosting** means the emulator must dither in **JavaScript** —
  Pages is static, no Python runs there. PIL stays authoritative for the device;
  a **parity test** over fixed images keeps the two honest. That is what makes
  "both" low-maintenance instead of two things to hand-sync.
- **High-res originals are kept** for crop and reposition, so editing is a real
  feature and the emulator has to model an edit state, not just
  capture → preview → print.

## Emulator — built

`docs/emulator.html`. Static, self-contained, phone-friendly, Pages-servable.
Mirrors `main.py` and `printer.py`: same 90° rotation, same fit-and-centre for
the panel, same 384px scale for print, Floyd–Steinberg to match PIL, and the
**real burn-time formula** from `print_bitmap` driving the animation.

Covers everything from Q9 except edit/crop, which was sidelined.

### What it revealed on the first run

**Printing one photo takes about a minute.** A 640×480 source becomes 512 rows,
25,260 bytes. At 9600 baud that is **26.3 s of serial time before any burn
pacing at all** — verified by arithmetic independently of the animation.

That is a product problem, not a code problem, and it was invisible until the
timing was modelled. Worth deciding what to do about it before the Zero 2W port:
raising the baud rate is the obvious lever, and the driver already has a known
sensitivity there.

## Next up

1. **Parity test** — fixed inputs through the JS dither and through PIL, assert
   identical output. This is what keeps the web version honest without manual
   syncing.
2. **Turn on GitHub Pages** — repo Settings → Pages → source `master` / `/docs`.
   Lands at <https://doodek.github.io/thermal-cam/>. `docs/.nojekyll` is already
   in place so static files are served untouched.
3. **Decide on print duration** — see above.

## Done

- **`pi/test_printer.py` written.** 6 checks, no framework, no hardware — a fake
  serial port captures the bytes the driver would have sent. Mutation-verified:
  raising `ROWS_PER_CHUNK` past the buffer cap, reversing the bit shift, and
  corrupting the chunk header each make it fail.
- **`print("hi")` removed** from `convert_pixel_array_to_binary`.
- **Width guard**: `w > 384` and unsupported pixel types now raise `ValueError`
  naming the problem, instead of returning `False` and surfacing as a
  `TypeError` on a subscript further down.
- **Deleted `pi/epd2in7_V2.py`** (stale fork — `main.py` inserts `lib/ext` ahead
  of the script dir on `sys.path`, so it was always shadowed) and
  **`pi/epd_2in7b_V2_test.py`** (vendor demo for the 3-colour panel we don't
  use; imports a `waveshare_epd` package that isn't present).

## Still needs your go-ahead

Untrack the ESP32 build output — `git rm -r --cached arduino/esp32-trial/build`.
1338 of 1452 tracked files. `.gitignore` now ignores that path but does **not**
untrack what is already committed. Held back because it shows up as a very large
deletion in `git status`.

## Deliberately deferred

- **Throttling the capture loop** (`main.py:436` spins with no sleep). Looks like
  a free win, but Q04 may delete the loop outright.
- **Deleting `pi/lib/int/ui.py`** (empty stub, GPIO 6 does nothing). Q10 decides
  whether it has a future.

Both would risk doing the work twice.

## Uncommitted

Nothing was committed this session. On `master`:

```
 M README.md          # product direction, fixed the phantom test_printer.py reference
?? .gitignore         # new — repo had none
?? docs/              # PRODUCT.md, STATE.md
?? tools/             # serve.py, grill.html, overview.html, README.md
```
