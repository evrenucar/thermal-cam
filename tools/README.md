# tools/ — the review loop

A way to go back and forth on design decisions without pasting walls of text
into a chat window, and without losing the images.

```bash
python3 tools/serve.py          # http://127.0.0.1:8765/
```

It prints every page it finds. Open one, answer, hit **Submit**. Answers land in
`tools/answers/` as JSON, with any attached or pasted files written out beside
them as real files. Then tell Claude to read the answers.

## Pages

| Page | What it is |
|---|---|
| `overview.html` | Code read of the repo: architecture, the printer driver, findings, TODO |
| `grill.html` | Product-direction interview — 13 questions with recommendations |

## Sharing a machine with other agents / servers

`serve.py` walks up from the requested port until it owns one outright, and
prints the directory it is serving:

```
  note: 8765 was taken by something else, using 8766
  serving  C:\...\thermal-cam\tools
```

Check that `serving` line if a page looks stale or wrong — it means you are
talking to a different server than you think.

This matters more on Windows than it looks. `http.server` sets
`allow_reuse_address = 1`, and Windows `SO_REUSEADDR` will happily let a second
process bind a port that is *already in use*, leaving two servers on one port
with no way to tell which answered. `serve.py` sets `allow_reuse_address =
False` specifically to make that fail loudly instead.

## If the server isn't running

The pages are static — `overview.html` works from `file://` with no server at
all. Only **Submit** needs `serve.py`.

If Submit fails, hit **Copy as text** instead: answers go to the clipboard as
plain text you can paste straight into chat. Attachments are listed by name
only, so images still need either the server or a manual paste. Your typed
answers survive a dead server regardless — drafts persist in `localStorage`,
independently of anything on the network.

Run it in your own shell so nothing else can reap it:

```bash
python3 -u tools/serve.py 8765     # -u so the log isn't buffered
```

## Answering

- **Tick options**, or ignore them and write your own — free text wins over the checkboxes.
- **Drop files** anywhere on a question card.
- **Paste images** straight into an answer box with Ctrl/Cmd+V. Screenshots, photos of the rig, bad printouts.
- Drafts save to `localStorage` as you type, so a reload won't lose your work. Big attachments can blow the storage quota; the draft silently stops persisting if that happens, but Submit still works.

## Adding a page

Drop any `.html` file in this folder; `serve.py` lists it on startup. To make it
submit answers, POST to `/save`:

```js
fetch("/save", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    form: "my-form",                 // becomes the filename stem
    answers: [{
      id: "q1",
      question: "...",
      selected: ["..."],
      text: "...",
      attachments: [{ name: "shot.png", type: "image/png", data: "data:image/png;base64,..." }]
    }]
  })
});
```

Attachments arrive as `data:` URIs and are decoded to real files, so images can
be opened rather than read as base64. `form` is stripped to `[A-Za-z0-9_-]` and
used as the filename stem — it cannot escape `tools/answers/`.

## Why it's stdlib-only

`serve.py` imports nothing outside the standard library, so it runs on a fresh
Pi with no `pip install` step. Bound to `127.0.0.1` — it is a local dev tool, not
a server, and has no authentication of any kind. Don't expose it.

`tools/answers/` is gitignored.
