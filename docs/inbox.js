/* thermal-cam inbox widget
 *
 * A floating button on every page. Type an idea, drop a file, paste a
 * screenshot, send. Fire and forget -- it appends to tools/INBOX.md and returns
 * immediately, so nothing you send interrupts work in progress.
 *
 * No server (e.g. on GitHub Pages)? It queues to localStorage instead and keeps
 * offering to copy the queue out, so an idea is never lost just because the
 * local server happens to be down.
 *
 * Drop <script src="inbox.js" defer></script> into any page. No dependencies.
 */
(function () {
  "use strict";
  if (window.__inboxLoaded) return;
  window.__inboxLoaded = true;

  var QUEUE = "thermal-cam-inbox-queue";
  var KINDS = ["idea", "task", "bug", "feedback"];
  var atts = [];
  var kind = "idea";

  var css = document.createElement("style");
  css.textContent = [
    "#ibBtn{position:fixed;right:max(1rem,env(safe-area-inset-right));bottom:max(1rem,env(safe-area-inset-bottom));",
    "  z-index:9998;width:3.5rem;height:3.5rem;border-radius:50%;border:none;cursor:pointer;",
    "  background:#b4451f;color:#fff;font-size:1.6rem;line-height:1;box-shadow:0 4px 16px rgba(0,0,0,.28);",
    "  display:grid;place-items:center;-webkit-tap-highlight-color:transparent;transition:transform .12s}",
    "#ibBtn:hover{transform:scale(1.06)} #ibBtn:active{transform:scale(.96)}",
    "#ibBtn .dot{position:absolute;top:-.15rem;right:-.15rem;min-width:1.25rem;height:1.25rem;border-radius:99px;",
    "  background:#16150f;color:#fff;font:700 .68rem/1.25rem ui-monospace,Consolas,monospace;display:none;padding:0 .3rem}",
    "#ibWrap{position:fixed;inset:0;z-index:9999;display:none;align-items:flex-end;justify-content:center;",
    "  background:rgba(0,0,0,.42);backdrop-filter:blur(2px)}",
    "#ibWrap.on{display:flex}",
    "@media(min-width:34rem){#ibWrap{align-items:center}}",
    "#ibCard{background:#fff;color:#16150f;width:100%;max-width:32rem;border-radius:14px 14px 0 0;",
    "  padding:1.1rem 1.15rem calc(1.1rem + env(safe-area-inset-bottom));box-shadow:0 -8px 40px rgba(0,0,0,.3)}",
    "@media(min-width:34rem){#ibCard{border-radius:14px;margin:1rem}}",
    "@media(prefers-color-scheme:dark){#ibCard{background:#1c1c16;color:#eceadf}}",
    "#ibCard h3{margin:0 0 .2rem;font:640 1.05rem system-ui,sans-serif}",
    "#ibCard .sub{margin:0 0 .8rem;font:.8rem system-ui,sans-serif;opacity:.62}",
    "#ibKinds{display:flex;gap:.35rem;margin-bottom:.6rem;flex-wrap:wrap}",
    "#ibKinds button{font:600 .76rem system-ui,sans-serif;padding:.35rem .7rem;border-radius:99px;",
    "  border:1px solid rgba(128,128,128,.4);background:transparent;color:inherit;cursor:pointer}",
    "#ibKinds button.on{background:#b4451f;color:#fff;border-color:#b4451f}",
    "#ibText{width:100%;min-height:6rem;resize:vertical;border-radius:9px;padding:.65rem .75rem;",
    "  border:1.5px dashed rgba(128,128,128,.4);background:transparent;color:inherit;",
    "  font:inherit;font-size:.95rem;outline:none}",
    "#ibText:focus{border-color:#b4451f;border-style:solid}",
    "#ibWrap.over #ibText{border-color:#b4451f;background:rgba(180,69,31,.08)}",
    "#ibAtts{display:flex;flex-wrap:wrap;gap:.4rem;margin-top:.5rem}",
    "#ibAtts span{display:flex;align-items:center;gap:.35rem;font:.72rem ui-monospace,Consolas,monospace;",
    "  background:rgba(128,128,128,.14);border-radius:5px;padding:.25rem .4rem;max-width:12rem}",
    "#ibAtts img{width:1.6rem;height:1.6rem;object-fit:cover;border-radius:3px}",
    "#ibAtts b{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-weight:400}",
    "#ibAtts i{cursor:pointer;font-style:normal;opacity:.6;padding:0 .15rem}",
    "#ibRow{display:flex;gap:.5rem;align-items:center;margin-top:.85rem;flex-wrap:wrap}",
    "#ibRow button{font:600 .88rem system-ui,sans-serif;padding:.6rem 1.1rem;border-radius:8px;cursor:pointer;border:1px solid #b4451f}",
    "#ibSend{background:#b4451f;color:#fff;flex:1 1 8rem}",
    "#ibClose{background:transparent;color:#b4451f}",
    "#ibMsg{flex-basis:100%;font:.78rem system-ui,sans-serif;opacity:.75;min-height:1.1rem}",
    "#ibHint{font:.72rem system-ui,sans-serif;opacity:.55;margin-top:.5rem}"
  ].join("");
  document.head.appendChild(css);

  var btn = document.createElement("button");
  btn.id = "ibBtn";
  btn.title = "Drop an idea, task or bug (i)";
  btn.innerHTML = '<span>&#43;</span><span class="dot" id="ibDot"></span>';
  document.body.appendChild(btn);

  var wrap = document.createElement("div");
  wrap.id = "ibWrap";
  wrap.innerHTML =
    '<div id="ibCard">' +
      '<h3>Drop it here</h3>' +
      '<p class="sub">Queued, not interrupting. Read at the next checkpoint.</p>' +
      '<div id="ibKinds"></div>' +
      '<textarea id="ibText" placeholder="An idea, a task, something that looks wrong&hellip;"></textarea>' +
      '<div id="ibAtts"></div>' +
      '<div id="ibHint">Drop files anywhere here, or paste a screenshot.</div>' +
      '<div id="ibRow">' +
        '<button id="ibSend" type="button">Send</button>' +
        '<button id="ibClose" type="button">Close</button>' +
        '<span id="ibMsg"></span>' +
      '</div>' +
    '</div>';
  document.body.appendChild(wrap);

  var $ = function (id) { return document.getElementById(id); };
  var text = $("ibText"), msg = $("ibMsg"), dot = $("ibDot");

  KINDS.forEach(function (k, i) {
    var b = document.createElement("button");
    b.type = "button"; b.textContent = k;
    if (i === 0) b.className = "on";
    b.onclick = function () {
      kind = k;
      [].forEach.call($("ibKinds").children, function (c) { c.className = c === b ? "on" : ""; });
    };
    $("ibKinds").appendChild(b);
  });

  function queued() {
    try { return JSON.parse(localStorage.getItem(QUEUE) || "[]"); } catch (e) { return []; }
  }
  function setQueued(list) {
    try { localStorage.setItem(QUEUE, JSON.stringify(list)); } catch (e) {}
    dot.textContent = list.length;
    dot.style.display = list.length ? "block" : "none";
  }

  function open_() {
    wrap.classList.add("on");
    setTimeout(function () { text.focus(); }, 40);
    var q = queued();
    msg.textContent = q.length ? q.length + " unsent — will retry on send" : "";
  }
  function close_() { wrap.classList.remove("on"); }

  btn.onclick = open_;
  $("ibClose").onclick = close_;
  wrap.onclick = function (e) { if (e.target === wrap) close_(); };
  addEventListener("keydown", function (e) {
    var t = document.activeElement.tagName;
    if (e.key === "Escape" && wrap.classList.contains("on")) close_();
    else if (e.key.toLowerCase() === "i" && !/^(INPUT|SELECT|TEXTAREA)$/.test(t) && !wrap.classList.contains("on")) {
      e.preventDefault(); open_();
    }
  });

  function renderAtts() {
    var box = $("ibAtts");
    box.innerHTML = "";
    atts.forEach(function (a, i) {
      var s = document.createElement("span");
      if (/^image\//.test(a.type)) {
        var im = document.createElement("img"); im.src = a.data; s.appendChild(im);
      }
      var b = document.createElement("b"); b.textContent = a.name; s.appendChild(b);
      var x = document.createElement("i"); x.textContent = "×";
      x.onclick = function () { atts.splice(i, 1); renderAtts(); };
      s.appendChild(x);
      box.appendChild(s);
    });
  }

  function addFiles(files) {
    [].forEach.call(files, function (f) {
      var r = new FileReader();
      r.onload = function () {
        atts.push({ name: f.name || "pasted.png", type: f.type || "application/octet-stream", data: r.result });
        renderAtts();
      };
      r.readAsDataURL(f);
    });
  }

  ["dragenter", "dragover"].forEach(function (ev) {
    wrap.addEventListener(ev, function (e) { e.preventDefault(); wrap.classList.add("over"); });
  });
  ["dragleave", "dragend", "drop"].forEach(function (ev) {
    wrap.addEventListener(ev, function () { wrap.classList.remove("over"); });
  });
  wrap.addEventListener("drop", function (e) {
    e.preventDefault();
    if (e.dataTransfer && e.dataTransfer.files.length) addFiles(e.dataTransfer.files);
  });
  text.addEventListener("paste", function (e) {
    var f = [];
    var items = (e.clipboardData || {}).items || [];
    for (var i = 0; i < items.length; i++)
      if (items[i].kind === "file") { var g = items[i].getAsFile(); if (g) f.push(g); }
    if (f.length) { e.preventDefault(); addFiles(f); }
  });

  function payloadFor(entry) {
    return {
      kind: entry.kind, text: entry.text, page: entry.page, at: entry.at,
      answers: [{ id: "inbox", question: entry.kind, selected: [], text: entry.text,
                  attachments: entry.atts }]
    };
  }

  function post(entry) {
    return fetch("/inbox", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payloadFor(entry))
    }).then(function (r) { return r.json(); }).then(function (j) {
      if (!j.ok) throw new Error(j.error || "refused");
      return j;
    });
  }

  // Try to drain anything stranded from a previous, server-less session.
  function drain() {
    var q = queued();
    if (!q.length) return Promise.resolve(0);
    return q.reduce(function (p, entry) {
      return p.then(function (okCount) {
        return post(entry).then(function () { return okCount + 1; }, function () { throw okCount; });
      });
    }, Promise.resolve(0)).then(function (n) {
      setQueued([]); return n;
    }, function (n) {
      setQueued(q.slice(n)); return n;
    });
  }

  $("ibSend").onclick = function () {
    var body = text.value.trim();
    if (!body && !atts.length) { msg.textContent = "Nothing to send."; return; }
    var entry = { kind: kind, text: body, atts: atts.slice(),
                  page: location.pathname.split("/").pop() || "index.html",
                  at: new Date().toISOString() };
    msg.textContent = "Sending…";

    post(entry).then(function (j) {
      text.value = ""; atts = []; renderAtts();
      msg.textContent = "Queued in " + j.path + (j.attachments ? " (+" + j.attachments + ")" : "");
      return drain();
    }).then(function () {
      setTimeout(close_, 700);
    }).catch(function () {
      // No server. Keep it locally rather than lose it.
      var q = queued(); q.push(entry); setQueued(q);
      text.value = ""; atts = []; renderAtts();
      msg.textContent = "No server — saved locally (" + q.length + "). Sends when serve.py is up.";
    });
  };

  setQueued(queued());
  // Opportunistic drain on load, so a queue from an offline session clears itself.
  if (queued().length) drain().catch(function () {});
})();
