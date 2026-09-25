"""A standalone evidence page for one or more episodes.

One HTML file, no server and no dependencies, so it can be copied off a remote
box and opened. Every proposed decision appears with the quote that supports it
and the reasoning around that quote, which is what makes a decision separable
from a hypothetical without reading the whole episode.

A page cannot write to the filesystem. Reviews are held in the browser while the
page is open and saved by exporting a JSON file, which the page can load again.
Nothing here writes back into a labels file: the frozen labels stay frozen and a
review is a separate artifact.
"""

from __future__ import annotations

import html
import json
from datetime import datetime, timezone

from .events import EventVerdict, context

CSS = """
:root { --bg:#fbfbfa; --fg:#1a1a18; --dim:#6b6b66; --line:#e2e0da; --card:#fff;
        --alert:#8c2f16; --quote:#fff6d6; --ok:#2d6a3f; --fail:#8a6d1f; }
@media (prefers-color-scheme: dark) { :root {
  --bg:#17181a; --fg:#e8e6e1; --dim:#9a9a94; --line:#2f3033; --card:#1e1f22;
  --alert:#e08160; --quote:#3b3524; --ok:#7fc08f; --fail:#d9bd6a; } }
* { box-sizing: border-box; }
body { margin:0; padding:32px 16px 96px; background:var(--bg); color:var(--fg);
       font:15px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; }
main { max-width: 860px; margin: 0 auto; }
h1 { font-size:20px; margin:0 0 4px; } h2 { font-size:16px; margin:32px 0 8px; }
.meta { color:var(--dim); font-size:13px; margin-bottom:24px; }
.counts { display:flex; flex-wrap:wrap; gap:8px 20px; padding:12px 16px; margin-bottom:24px;
          background:var(--card); border:1px solid var(--line); border-radius:8px; font-size:13px; }
.counts b { font-weight:600; } .counts .fail { color:var(--fail); }
.ev { background:var(--card); border:1px solid var(--line); border-left:3px solid var(--line);
      border-radius:8px; padding:14px 16px; margin:12px 0; }
.ev.alert { border-left-color:var(--alert); }
.ev.unassessed { border-left-color:var(--fail); }
.ev.suggested { border-left-color:var(--fail); border-left-style:dashed; }
.warn { color:var(--fail); font-size:13px; margin:6px 0; }
.constraint { font-size:13px; margin:6px 0 10px; color:var(--dim); }
.pair { display:grid; grid-template-columns:1fr 1fr; gap:10px; margin-bottom:10px; }
@media (max-width:620px) { .pair { grid-template-columns:1fr; } }
.tag { font:600 11px/1 ui-monospace,monospace; letter-spacing:.04em; text-transform:uppercase;
       color:var(--dim); margin-right:10px; }
.tag.stance { color:var(--fg); }
.why { margin:6px 0 10px; }
pre.ctx { white-space:pre-wrap; word-break:break-word; margin:0; padding:12px;
          background:var(--bg); border:1px solid var(--line); border-radius:6px;
          font:13px/1.55 ui-monospace,SFMono-Regular,monospace; color:var(--dim); }
pre.ctx mark { background:var(--quote); color:var(--fg); padding:1px 0; }
.loc { font:12px ui-monospace,monospace; color:var(--dim); margin-top:8px; }
.review { margin-top:12px; display:flex; flex-wrap:wrap; gap:8px; align-items:center; }
.review button { font:13px inherit; padding:5px 12px; border:1px solid var(--line);
                 background:var(--bg); color:var(--fg); border-radius:6px; cursor:pointer; }
.review button[aria-pressed="true"] { background:var(--fg); color:var(--bg); border-color:var(--fg); }
.review input { flex:1 1 220px; min-width:180px; font:13px inherit; padding:5px 8px;
                background:var(--bg); color:var(--fg); border:1px solid var(--line); border-radius:6px; }
.bar { position:fixed; left:0; right:0; bottom:0; display:flex; gap:12px; align-items:center;
       padding:10px 16px; background:var(--card); border-top:1px solid var(--line); font-size:13px; }
.bar button, .bar label { font:13px inherit; padding:6px 14px; border:1px solid var(--line);
       background:var(--bg); color:var(--fg); border-radius:6px; cursor:pointer; }
.bar .status { color:var(--dim); margin-left:auto; }
.fail-list { color:var(--fail); font-size:13px; margin:8px 0 0; padding-left:20px; }
.none { color:var(--dim); font-style:italic; }
"""

SCRIPT = """
const KEY = 'cotwatcher-review-' + REPORT.report_id;
let reviews = {};
// Storage is unavailable in a private window, under blocked site data, and on
// some file: and data: origins. The page must work anyway, and must say so
// rather than letting a reviewer assume their verdicts will survive the tab.
let storageOk = true;
try {
  localStorage.setItem(KEY + '-probe', '1');
  localStorage.removeItem(KEY + '-probe');
  reviews = JSON.parse(localStorage.getItem(KEY) || '{}');
} catch (e) { storageOk = false; reviews = {}; }

function save() {
  if (storageOk) { try { localStorage.setItem(KEY, JSON.stringify(reviews)); } catch (e) { storageOk = false; } }
  const n = Object.keys(reviews).length;
  document.getElementById('status').textContent =
    n + ' of ' + REPORT.event_count + ' reviewed \\u2014 ' +
    (storageOk ? 'export to keep them'
               : 'this browser is not storing them, export before you close this tab');
  document.getElementById('status').style.color = storageOk ? '' : 'var(--fail)';
}
function paint() {
  document.querySelectorAll('.ev[data-ev]').forEach(card => {
    const r = reviews[card.dataset.ev] || {};
    card.querySelectorAll('button[data-verdict]').forEach(b =>
      b.setAttribute('aria-pressed', String(r.verdict === b.dataset.verdict)));
    const input = card.querySelector('input');
    if (input && input.value !== (r.reason || '')) input.value = r.reason || '';
  });
  save();
}
document.addEventListener('click', e => {
  const b = e.target.closest('button[data-verdict]');
  if (!b) return;
  const id = b.closest('.ev').dataset.ev;
  const cur = reviews[id] || {};
  if (cur.verdict === b.dataset.verdict) delete reviews[id];
  else reviews[id] = { ...cur, verdict: b.dataset.verdict };
  paint();
});
document.addEventListener('input', e => {
  if (!e.target.matches('.review input')) return;
  const id = e.target.closest('.ev').dataset.ev;
  const cur = reviews[id] || {};
  if (!e.target.value && !cur.verdict) { delete reviews[id]; } 
  else { reviews[id] = { ...cur, reason: e.target.value }; }
  save();
});
document.getElementById('export').addEventListener('click', () => {
  const payload = { ...REPORT, reviewed_at: new Date().toISOString(), reviews };
  const blob = new Blob([JSON.stringify(payload, null, 1)], { type: 'application/json' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = 'review-' + REPORT.report_id + '.json';
  a.click();
  URL.revokeObjectURL(a.href);
});
document.getElementById('load').addEventListener('change', async e => {
  const file = e.target.files[0];
  if (!file) return;
  try {
    const data = JSON.parse(await file.text());
    if (data.report_id !== REPORT.report_id) {
      alert('That review file is for report ' + data.report_id + ', this page is ' +
            REPORT.report_id + '. Not loaded.');
      return;
    }
    reviews = data.reviews || {};
    paint();
  } catch (err) { alert('Could not read that file: ' + err.message); }
  e.target.value = '';
});
paint();
"""


def _esc(text: str) -> str:
    return html.escape(text or "", quote=False)


def _event_card(ev_id: str, event, turns: list[dict]) -> str:
    suggestion = event.located and not event.verified
    classes = ("ev" + (" alert" if event.alerts else "")
               + ("" if event.located else " unassessed")
               + (" suggested" if suggestion else ""))
    head = (f'<span class="tag">{_esc(event.category)}</span>'
            f'<span class="tag stance">{_esc(event.stance)}</span>')
    if not event.located:
        return (f'<div class="{classes}">{head}'
                f'<p class="why">{_esc(event.rationale)}</p>'
                f'<p class="fail-list">Unassessed: {_esc(event.error or "not located")}</p>'
                f'<pre class="ctx">{_esc(event.quote[:400])}</pre></div>')
    before, quote, after = context(turns, event.location)
    loc = event.location
    banner = ""
    if suggestion:
        # A resemblance is not evidence. A quote measured at 0.947 similarity
        # had dropped a "not" out of the source sentence, reversing what it
        # said, so the two texts go side by side and the reviewer decides.
        banner = ('<p class="warn">Resemblance only, not a verified quote. Read what the judge '
                  'wrote against what the source says before deciding.</p>'
                  f'<div class="pair"><div><span class="tag">judge wrote</span>'
                  f'<pre class="ctx">{_esc(event.quote)}</pre></div>'
                  f'<div><span class="tag">source says</span>'
                  f'<pre class="ctx">{_esc(loc.source_text(turns))}</pre></div></div>')
    constraint = (f'<p class="constraint"><span class="tag">constraint recognised</span>'
                  f'{_esc(event.constraint)}</p>' if event.constraint else "")
    return (f'<div class="{classes}" data-ev="{_esc(ev_id)}">{head}'
            f'<p class="why">{_esc(event.rationale)}</p>'
            f'{constraint}'
            f'{banner}'
            f'<pre class="ctx">{_esc(before)}<mark>{_esc(quote)}</mark>{_esc(after)}</pre>'
            f'<p class="loc">turn {loc.turn}, chars {loc.start}–{loc.end}, '
            f'{loc.match} match, similarity {loc.similarity}, source {loc.source_sha}</p>'
            f'<div class="review">'
            f'<button data-verdict="confirm">Confirm</button>'
            f'<button data-verdict="reject">Reject</button>'
            f'<button data-verdict="unsure">Unsure</button>'
            f'<input placeholder="reason (kept with the decision)">'
            f'</div></div>')


def render(episodes: list[tuple[dict, EventVerdict]], report_id: str,
           source_file: str = "") -> str:
    """One page for a list of (episode, verified verdict) pairs."""
    cards: list[str] = []
    event_count = 0
    located = alerts = unassessed = suggestions = episode_failures = 0
    turns_total = turns_with_reasoning = 0

    for episode, verdict in episodes:
        turns = episode.get("turns", [])
        turns_total += len(turns)
        turns_with_reasoning += sum(1 for t in turns if (t.get("reasoning") or "").strip())
        cards.append(f'<h2>{_esc(episode.get("id", "episode"))}</h2>')
        cards.append(f'<p class="meta">{_esc(episode.get("condition", ""))} &middot; '
                     f'outcome {_esc(str(episode.get("outcome", "")))} &middot; '
                     f'{len(turns)} turns &middot; '
                     f'judge summary: {_esc(verdict.summary) or "<em>none</em>"}</p>')
        if verdict.error:
            episode_failures += 1
            cards.append(f'<p class="fail-list">Episode not assessed: {_esc(verdict.error)}</p>')
        ordered = verdict.timeline() + [e for e in verdict.events if not e.located]
        if not ordered:
            cards.append('<p class="none">No decision events proposed.</p>')
        for event in ordered:
            event_count += 1
            located += 1 if event.located else 0
            alerts += 1 if event.alerts else 0
            suggestions += 1 if (event.located and not event.verified) else 0
            unassessed += 0 if event.located else 1
            # Identity from content: a verdict recorded about this event must not
            # transfer to whatever lands at the same index in a later run.
            cards.append(_event_card(event.event_id(str(episode.get("id", ""))), event, turns))

    payload = {"report_id": report_id, "event_count": event_count,
               "source_file": source_file,
               "generated": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    counts = (f'<div class="counts">'
              f'<span><b>{len(episodes)}</b> episodes</span>'
              f'<span><b>{event_count}</b> events proposed</span>'
              f'<span><b>{alerts}</b> verified commitments</span>'
              f'<span class="fail"><b>{suggestions}</b> resemblance only</span>'
              f'<span><b>{located}</b> located</span>'
              f'<span class="fail"><b>{unassessed}</b> unassessed event'
              f'{"" if unassessed == 1 else "s"}</span>'
              f'<span class="fail"><b>{episode_failures}</b> episode'
              f'{"" if episode_failures == 1 else "s"} not assessed</span>'
              f'<span><b>{turns_with_reasoning}</b>/{turns_total} turns carry reasoning</span>'
              f'</div>')
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>cotwatcher evidence</title><style>{CSS}</style></head>
<body><main>
<h1>Decision events proposed for review</h1>
<p class="meta">{_esc(source_file)} &middot; generated {payload['generated']} &middot;
report {_esc(report_id)}. Counts are descriptive: this is a sample, not a rate.</p>
{counts}
{''.join(cards)}
</main>
<div class="bar">
  <button id="export">Export reviews</button>
  <label>Load reviews<input id="load" type="file" accept="application/json" hidden></label>
  <span class="status" id="status"></span>
</div>
<script>const REPORT = {json.dumps(payload)};{SCRIPT}</script>
</body></html>"""
