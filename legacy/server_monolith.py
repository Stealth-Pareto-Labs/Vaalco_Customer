"""
server.py  -  ENTRY POINT.  Run this file.
==========================================
    python app/server.py     (from the project root)

Serves ONE web app with two tabs backed by a shared analysis core:

  ASK      -> the reactive chatbot (unchanged): you ask, it answers.
  SIGNALS  -> the proactive intelligence layer: it scans the data, decides
              what matters (low/medium/high), shows evidence + next steps,
              keeps a history of runs, and can email/SMS the report.

Endpoints:
  GET  /                 the single-page app (both tabs)
  POST /ask              chatbot tool-calling loop -> answer + trace + charts
  GET  /status           data state + newly-ingested reports (live banner)
  GET  /signals/latest   run the engine now against current data (no send)
  POST /signals/run      run + SAVE to history (optionally deliver)
  GET  /signals/history  list saved runs (newest first)
  GET  /signals/run?id=  load one saved run
  POST /signals/send     deliver a saved (or freshly-run) report via email/SMS
  GET  /signals/preview?id=  the branded HTML report on its own (for print/email view)

On startup it loads any reports already in reports/, starts the folder-watcher,
and registers an auto-trigger so a NEW report dropped in during operation
generates an intelligence run and notification automatically.
"""

import os
import sys
import json
import threading

sys.path.insert(0, os.path.dirname(__file__))

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

import config
import analysis
import watcher
import claude_client
import signals
import intelligence
import report as report_mod
import notify


# ---------------------------------------------------------------------------
# Auto-trigger: when a new report lands, run intelligence + deliver.
# Guarded so we don't fire during the bulk initial load.
# ---------------------------------------------------------------------------
_ready_for_triggers = False
_last_auto_run = {"run": None}


def _on_new_report(day_record):
    if not _ready_for_triggers:
        return
    print(f"  > new report {day_record.get('date')} -> running intelligence…")
    run = intelligence.run(trigger=f"auto: new report {day_record.get('date')}")
    intelligence.save_run(run)
    notify.deliver(run)
    _last_auto_run["run"] = run["run_id"]


def bootstrap():
    records = watcher.initial_load()
    analysis.load(records)
    watcher.set_on_ingest(_on_new_report)
    watcher.start_background()
    global _ready_for_triggers
    _ready_for_triggers = True


# ===========================================================================
# The single-page app (two tabs, shared shell). No build step.
# ===========================================================================
PAGE = r"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Navigator Z — Vessel Intelligence</title>
<style>
:root{
  --bg:#0b0e10;--surface:#161b1e;--surface2:#1b2226;--line:#252c31;--line2:#30393f;
  --ink:#eef2f4;--mut:#869199;--mut2:#5f6a72;
  --teal:#46b89a;--blue:#4a90e2;--amber:#d99a3c;--red:#e0584f;
  --navy:#0B3A5B;--orange:#E8563F;
  --hi:#e0584f;--hi-bg:rgba(224,88,79,.12);
  --med:#d99a3c;--med-bg:rgba(217,154,60,.12);
  --lo:#4a9cb0;--lo-bg:rgba(74,156,176,.12);
}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--ink);font-family:-apple-system,'Inter',system-ui,sans-serif;font-size:15px;line-height:1.55}
.app{max-width:860px;margin:0 auto;min-height:100vh;display:flex;flex-direction:column;padding:0 20px}
/* ---- top bar ---- */
.top{display:flex;align-items:center;gap:12px;padding:18px 0 0}
.mk{width:34px;height:34px;border-radius:9px;background:var(--surface);display:grid;place-items:center;color:var(--teal);flex:none}
.mk svg{width:18px;height:18px}
.top h1{font-size:16px;font-weight:600;line-height:1.2}
.top .sub{font-size:12px;color:var(--mut)}
.status{margin-left:auto;font-size:12px;color:var(--mut);display:flex;align-items:center;gap:7px;background:var(--surface);border:1px solid var(--line);padding:6px 11px;border-radius:20px}
.status .dot{width:8px;height:8px;border-radius:50%;background:var(--teal)}
.status .dot.off{background:var(--red)}
/* ---- tabs ---- */
.tabs{display:flex;gap:4px;padding:16px 0 0;border-bottom:1px solid var(--line)}
.tab{padding:10px 16px;font-size:14px;font-weight:600;color:var(--mut);cursor:pointer;border:0;background:none;border-bottom:2px solid transparent;font-family:inherit;display:flex;align-items:center;gap:8px}
.tab:hover{color:var(--ink)}
.tab.active{color:var(--ink);border-bottom-color:var(--teal)}
.tab .badge{font-size:11px;font-weight:700;background:var(--hi);color:#fff;border-radius:10px;padding:1px 7px;min-width:18px;text-align:center}
.tab .badge.zero{display:none}
.view{flex:1;display:none;flex-direction:column}
.view.active{display:flex}
/* =================== ASK TAB =================== */
#thread{flex:1;display:flex;flex-direction:column;gap:14px;padding:18px 0;overflow-y:auto}
.m{padding:11px 14px;border-radius:13px;max-width:82%;line-height:1.55}
.u{background:#1e3a4d;align-self:flex-end}
.b{background:var(--surface);align-self:flex-start;border:1px solid var(--line)}
.trace{font-family:ui-monospace,'SF Mono',monospace;font-size:11px;color:var(--teal);margin-bottom:7px;padding-bottom:7px;border-bottom:1px solid var(--line);opacity:.85}
.trace .tt{display:block}
.ingest{align-self:center;font-size:12px;color:var(--amber);background:rgba(217,154,60,.08);border:1px solid rgba(217,154,60,.25);border-radius:8px;padding:7px 12px;display:flex;align-items:center;gap:7px}
.ingest svg{width:13px;height:13px}
.hint{align-self:center;color:var(--mut);font-size:12.5px;text-align:center;max-width:460px;line-height:1.5}
.row{display:flex;gap:9px;padding:14px 0;border-top:1px solid var(--line)}
#q{flex:1;padding:12px 14px;border-radius:11px;border:1px solid var(--line);background:var(--surface);color:var(--ink);font-size:15px;font-family:inherit}
#q:focus{outline:none;border-color:var(--teal)}
button.send{padding:12px 20px;border-radius:11px;border:none;background:var(--teal);color:#06231c;font-weight:600;cursor:pointer;font-size:15px;font-family:inherit}
button.send:disabled{opacity:.5;cursor:default}
.chips{display:flex;gap:7px;flex-wrap:wrap;padding-bottom:16px}
.chip{font-size:12.5px;color:var(--mut);background:var(--surface);border:1px solid var(--line);border-radius:16px;padding:6px 12px;cursor:pointer}
.chip:hover{border-color:var(--teal);color:var(--ink)}
.think{color:var(--mut)}
.dots i{display:inline-block;width:5px;height:5px;border-radius:50%;background:var(--mut);animation:tp 1.2s infinite;margin:0 1px}
.dots i:nth-child(2){animation-delay:.2s}.dots i:nth-child(3){animation-delay:.4s}
@keyframes tp{0%,60%,100%{opacity:.3}30%{opacity:1}}
.chart-box{background:var(--surface);border:1px solid var(--line);border-radius:12px;padding:14px;margin-top:10px;max-width:82%;align-self:flex-start}
.chart-box canvas{max-height:260px}
/* =================== SIGNALS TAB =================== */
.sig-wrap{padding:18px 0 40px;overflow-y:auto;flex:1}
.sig-head{display:flex;align-items:flex-start;gap:14px;flex-wrap:wrap;margin-bottom:18px}
.sig-title{font-size:15px;font-weight:600}
.sig-title .as-of{color:var(--mut);font-weight:400;font-size:13px;margin-left:6px}
.sig-actions{margin-left:auto;display:flex;gap:8px;flex-wrap:wrap}
.btn{padding:8px 14px;border-radius:9px;border:1px solid var(--line2);background:var(--surface);color:var(--ink);font-size:13px;font-weight:600;cursor:pointer;font-family:inherit;display:flex;align-items:center;gap:7px}
.btn:hover{border-color:var(--teal)}
.btn.primary{background:var(--teal);color:#06231c;border-color:var(--teal)}
.btn.primary:hover{filter:brightness(1.06)}
.btn:disabled{opacity:.5;cursor:default}
.btn svg{width:14px;height:14px}
.counts{display:flex;gap:10px;margin-bottom:18px;flex-wrap:wrap}
.count{flex:1;min-width:90px;background:var(--surface);border:1px solid var(--line);border-radius:10px;padding:14px 16px;border-top:3px solid var(--mut2)}
.count.hi{border-top-color:var(--hi)}.count.med{border-top-color:var(--med)}.count.lo{border-top-color:var(--lo)}
.count .n{font-size:28px;font-weight:700;line-height:1}
.count.hi .n{color:var(--hi)}.count.med .n{color:var(--med)}.count.lo .n{color:var(--lo)}
.count .l{font-size:11px;color:var(--mut);text-transform:uppercase;letter-spacing:.06em;margin-top:6px}
.exec{background:var(--surface);border:1px solid var(--line);border-left:3px solid var(--orange);border-radius:10px;padding:16px 18px;margin-bottom:20px}
.exec .lab{color:var(--orange);font-size:11px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;margin-bottom:7px}
.exec .txt{font-size:14.5px;line-height:1.6;color:var(--ink)}
.card{background:var(--surface);border:1px solid var(--line);border-radius:12px;margin-bottom:14px;overflow:hidden;border-left:4px solid var(--mut2)}
.card.hi{border-left-color:var(--hi)}.card.med{border-left-color:var(--med)}.card.lo{border-left-color:var(--lo)}
.card-h{padding:15px 18px 12px;display:flex;align-items:center;gap:10px;flex-wrap:wrap}
.pill{font-size:11px;font-weight:700;letter-spacing:.05em;color:#fff;padding:4px 9px;border-radius:4px}
.pill.hi{background:var(--hi)}.pill.med{background:var(--med)}.pill.lo{background:var(--lo)}
.card-h .ct{font-size:15.5px;font-weight:600;color:var(--ink)}
.card-h .cat{margin-left:auto;font-size:11px;color:var(--mut);text-transform:uppercase;letter-spacing:.05em}
.card-b{padding:0 18px 16px}
.expl{font-size:14px;line-height:1.55;color:var(--ink);margin-bottom:12px}
.evidence{background:var(--surface2);border-radius:8px;padding:12px 14px;margin-bottom:12px}
.evidence .lab,.steps .lab{color:var(--mut);font-size:11px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;margin-bottom:8px}
.ev-row{display:flex;gap:12px;padding:3px 0;font-size:13px}
.ev-row .k{color:var(--mut);flex:none;min-width:150px}
.ev-row .v{color:var(--ink);font-weight:600}
.steps ul{margin:0;padding-left:18px}
.steps li{font-size:13.5px;line-height:1.5;margin-bottom:6px;color:var(--ink)}
.card-f{padding:10px 18px;border-top:1px solid var(--line);display:flex;justify-content:flex-end}
.probe{font-size:12.5px;color:var(--teal);background:none;border:1px solid var(--line2);border-radius:8px;padding:6px 12px;cursor:pointer;font-family:inherit;display:flex;align-items:center;gap:6px}
.probe:hover{border-color:var(--teal);background:rgba(70,184,154,.08)}
.probe svg{width:13px;height:13px}
.empty{background:var(--surface);border:1px solid var(--line);border-radius:12px;padding:40px 24px;text-align:center;color:var(--mut)}
.sig-loading{text-align:center;padding:50px 0;color:var(--mut)}
/* history */
.history{margin-top:26px}
.history h3{font-size:13px;color:var(--mut);text-transform:uppercase;letter-spacing:.06em;margin-bottom:12px;font-weight:700}
.hrow{display:flex;align-items:center;gap:12px;padding:11px 14px;border:1px solid var(--line);border-radius:9px;margin-bottom:8px;cursor:pointer;background:var(--surface)}
.hrow:hover{border-color:var(--teal)}
.hrow .hdate{font-size:13.5px;font-weight:600;flex:none;min-width:150px}
.hrow .hhead{font-size:13px;color:var(--mut);flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.hrow .hc{display:flex;gap:5px;flex:none}
.dotc{font-size:11px;font-weight:700;padding:2px 7px;border-radius:9px}
.dotc.hi{background:var(--hi-bg);color:var(--hi)}.dotc.med{background:var(--med-bg);color:var(--med)}.dotc.lo{background:var(--lo-bg);color:var(--lo)}
.toast{position:fixed;bottom:22px;left:50%;transform:translateX(-50%);background:var(--surface2);border:1px solid var(--line2);color:var(--ink);padding:12px 18px;border-radius:10px;font-size:13.5px;box-shadow:0 10px 30px rgba(0,0,0,.4);z-index:50;max-width:90%}
.toast.err{border-color:var(--red)}
.banner{background:var(--surface2);border:1px solid var(--line2);border-radius:9px;padding:10px 14px;font-size:12.5px;color:var(--mut);margin-bottom:16px;display:flex;gap:9px;align-items:center}
.banner svg{width:15px;height:15px;color:var(--teal);flex:none}
@media(max-width:560px){.ev-row .k{min-width:110px}.hrow .hdate{min-width:auto}.hrow .hhead{display:none}}
</style>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>
</head><body>
<div class="app">
  <div class="top">
    <div class="mk"><svg viewBox="0 0 24 24" fill="none"><path d="M12 3l7 4v5c0 4.5-3 7.5-7 9-4-1.5-7-4.5-7-9V7l7-4z" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/><circle cx="12" cy="11" r="2.4" stroke="currentColor" stroke-width="2"/></svg></div>
    <div><h1>Navigator Z — Vessel Intelligence</h1><div class="sub">Fuel · DP efficiency · maintenance · HSE</div></div>
    <div class="status"><span class="dot" id="sdot"></span><span id="stext">connecting…</span></div>
  </div>

  <div class="tabs">
    <button class="tab active" id="tab-ask" onclick="switchTab('ask')">
      <svg width="15" height="15" viewBox="0 0 24 24" fill="none"><path d="M21 12a8 8 0 0 1-11.6 7.1L4 20l1-5A8 8 0 1 1 21 12z" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/></svg>
      Ask
    </button>
    <button class="tab" id="tab-signals" onclick="switchTab('signals')">
      <svg width="15" height="15" viewBox="0 0 24 24" fill="none"><path d="M12 3v2m0 14v2m9-9h-2M5 12H3m14.5-6.5-1.4 1.4M6.9 17.1l-1.4 1.4m12.6 0-1.4-1.4M6.9 6.9 5.5 5.5" stroke="currentColor" stroke-width="2" stroke-linecap="round"/><circle cx="12" cy="12" r="3.2" stroke="currentColor" stroke-width="2"/></svg>
      Signals
      <span class="badge zero" id="sig-badge">0</span>
    </button>
  </div>

  <!-- ================= ASK VIEW ================= -->
  <div class="view active" id="view-ask">
    <div id="thread">
      <div class="hint">Answers are computed by the vessel's analysis functions; the AI decides which to run and explains the result. Numbers always come from the code, never invented.</div>
    </div>
    <div class="row">
      <input id="q" placeholder="Why was fuel high on the 22nd?" onkeydown="if(event.key==='Enter')send()" autocomplete="off">
      <button class="send" id="ask" onclick="send()">Ask</button>
    </div>
    <div class="chips">
      <span class="chip" onclick="askChip(this)">How's our fuel overall?</span>
      <span class="chip" onclick="askChip(this)">Why was fuel high on the 22nd?</span>
      <span class="chip" onclick="askChip(this)">How efficient is our DP?</span>
      <span class="chip" onclick="askChip(this)">Anything overdue for maintenance?</span>
    </div>
  </div>

  <!-- ================= SIGNALS VIEW ================= -->
  <div class="view" id="view-signals">
    <div class="sig-wrap">
      <div class="banner">
        <svg viewBox="0 0 24 24" fill="none"><path d="M12 3l7 4v5c0 4.5-3 7.5-7 9-4-1.5-7-4.5-7-9V7l7-4z" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/></svg>
        The engine scans the data automatically when a new report arrives and emails/texts this report to the team. You can also re-run it here, preview the email, or send it now.
      </div>
      <div id="sig-body"><div class="sig-loading">Loading latest analysis…</div></div>
      <div class="history" id="history-wrap" style="display:none">
        <h3>Report history</h3>
        <div id="history-list"></div>
      </div>
    </div>
  </div>
</div>
<div id="toast-holder"></div>

<script>
/* ---------------- shared ---------------- */
function toast(msg, isErr){
  const t=document.createElement('div'); t.className='toast'+(isErr?' err':''); t.textContent=msg;
  document.getElementById('toast-holder').appendChild(t);
  setTimeout(()=>{t.style.opacity='0';t.style.transition='opacity .4s';setTimeout(()=>t.remove(),400);},3200);
}
function esc(s){return (s==null?'':String(s)).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');}
let currentTab='ask';
function switchTab(name){
  currentTab=name;
  document.getElementById('tab-ask').classList.toggle('active',name==='ask');
  document.getElementById('tab-signals').classList.toggle('active',name==='signals');
  document.getElementById('view-ask').classList.toggle('active',name==='ask');
  document.getElementById('view-signals').classList.toggle('active',name==='signals');
  if(name==='signals' && !signalsLoaded){ loadLatestSignals(); loadHistory(); signalsLoaded=true; }
}

/* ---------------- ASK ---------------- */
const thread=document.getElementById('thread'); let history=[];
function el(cls,html){const d=document.createElement('div');d.className=cls;d.innerHTML=html;thread.appendChild(d);thread.scrollTop=thread.scrollHeight;return d;}
function askChip(chip){document.getElementById('q').value=chip.textContent;send();}
function askFromProbe(text){
  switchTab('ask');
  document.getElementById('q').value=text;
  send();
}
async function send(){
  const q=document.getElementById('q'),btn=document.getElementById('ask');
  const text=q.value.trim(); if(!text)return;
  el('m u',esc(text)); q.value=''; btn.disabled=true;
  const b=el('m b','<span class="think"><span class="dots"><i></i><i></i><i></i></span> thinking</span>');
  try{
    const r=await fetch('/ask',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({message:text,history})});
    const data=await r.json();
    let trace='';
    if(data.trace&&data.trace.length) trace='<div class="trace">'+data.trace.map(t=>'<span class="tt">→ called '+esc(t.tool)+'('+esc(JSON.stringify(t.arguments))+')</span>').join('')+'</div>';
    let clean=(data.answer||'')
      .replace(/!\[[^\]]*\]\((?:data:[^)]*|[^)]*)\)/g,'')
      .replace(/data:image\/[^\s)]+/g,'')
      .replace(/\n{3,}/g,'\n\n').trim();
    b.innerHTML=trace+esc(clean).replace(/\n/g,'<br>');
    if(data.charts && data.charts.length){ data.charts.forEach(spec=>renderChart(spec)); }
    history.push({role:'user',content:text}); history.push({role:'assistant',content:data.answer});
  }catch(e){ b.innerHTML='<span style="color:var(--red)">Error: '+esc(e)+'</span>'; }
  btn.disabled=false; q.focus();
}
let _chartN=0;
function renderChart(spec){
  const box=document.createElement('div'); box.className='chart-box';
  if(typeof Chart==='undefined'){
    let html='<div style="font-size:13px;color:var(--mut);margin-bottom:8px">'+esc(spec.title||spec.field)+'</div>';
    html+='<table style="width:100%;font-size:13px;border-collapse:collapse">';
    spec.labels.forEach((l,i)=>{ html+='<tr><td style="padding:3px 8px;color:var(--mut)">'+esc(l)+'</td><td style="padding:3px 8px;text-align:right">'+esc(spec.values[i])+'</td></tr>'; });
    html+='</table>'; box.innerHTML=html; thread.appendChild(box); thread.scrollTop=thread.scrollHeight; return;
  }
  const cv=document.createElement('canvas'); cv.id='chart_'+(_chartN++);
  box.appendChild(cv); thread.appendChild(box); thread.scrollTop=thread.scrollHeight;
  const accent=getComputedStyle(document.documentElement).getPropertyValue('--teal').trim()||'#46b89a';
  new Chart(cv.getContext('2d'),{
    type: spec.type==='bar'?'bar':'line',
    data:{labels:spec.labels,datasets:[{label:spec.y_label||spec.field,data:spec.values,
      borderColor:accent,backgroundColor:spec.type==='bar'?accent:'rgba(70,184,154,.15)',
      borderWidth:2,pointRadius:3,tension:.25,fill:spec.type!=='bar'}]},
    options:{responsive:true,plugins:{legend:{display:false},
      title:{display:!!spec.title,text:spec.title,color:'#cdd6db'}},
      scales:{x:{ticks:{color:'#8a959c'},grid:{color:'rgba(255,255,255,.05)'}},
              y:{ticks:{color:'#8a959c'},grid:{color:'rgba(255,255,255,.05)'}}}}
  });
}

/* ---------------- SIGNALS ---------------- */
let signalsLoaded=false;
let currentRun=null;      // the run object currently displayed
let currentRunId=null;    // its saved id, if saved

function priClass(p){return p==='high'?'hi':p==='medium'?'med':'lo';}
function priLabel(p){return p.toUpperCase();}

function renderRun(run){
  currentRun=run;
  const c=run.counts||{high:0,medium:0,low:0,total:0};
  const savedNote = currentRunId ? '' : '';
  let h='';
  h+='<div class="sig-head"><div class="sig-title">Latest analysis'
    +'<span class="as-of">as of '+esc(run.as_of||'')+' · '+ (run.reports_loaded||0) +' reports</span></div>'
    +'<div class="sig-actions">'
    +'<button class="btn" id="btn-rerun" onclick="rerun()"><svg viewBox="0 0 24 24" fill="none"><path d="M4 12a8 8 0 0 1 13.7-5.7L20 8m0 0V3m0 5h-5M20 12a8 8 0 0 1-13.7 5.7L4 16m0 0v5m0-5h5" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>Re-run</button>'
    +'<button class="btn" onclick="previewEmail()"><svg viewBox="0 0 24 24" fill="none"><path d="M3 6.5A1.5 1.5 0 0 1 4.5 5h15A1.5 1.5 0 0 1 21 6.5v11A1.5 1.5 0 0 1 19.5 19h-15A1.5 1.5 0 0 1 3 17.5v-11z" stroke="currentColor" stroke-width="2"/><path d="M4 7l8 5 8-5" stroke="currentColor" stroke-width="2"/></svg>Preview email</button>'
    +'<button class="btn primary" id="btn-send" onclick="sendReport()"><svg viewBox="0 0 24 24" fill="none"><path d="M4 12l16-7-7 16-2-6-7-3z" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/></svg>Send now</button>'
    +'</div></div>';

  h+='<div class="counts">'
    +'<div class="count hi"><div class="n">'+(c.high||0)+'</div><div class="l">High priority</div></div>'
    +'<div class="count med"><div class="n">'+(c.medium||0)+'</div><div class="l">Medium</div></div>'
    +'<div class="count lo"><div class="n">'+(c.low||0)+'</div><div class="l">Low</div></div>'
    +'</div>';

  h+='<div class="exec"><div class="lab">Executive summary</div><div class="txt">'+esc(run.executive_summary||'')+'</div></div>';

  const sigs=run.signals||[];
  if(!sigs.length){
    h+='<div class="empty">No signals were raised for this window. All monitored metrics are within their configured thresholds.</div>';
  } else {
    sigs.forEach(s=>{ h+=renderCard(s); });
  }
  document.getElementById('sig-body').innerHTML=h;
}

function renderCard(s){
  const pc=priClass(s.priority);
  let ev='';
  (s.evidence||[]).forEach(e=>{ ev+='<div class="ev-row"><div class="k">'+esc(e.label)+'</div><div class="v">'+esc(e.value)+'</div></div>'; });
  let st='';
  (s.next_steps||[]).forEach(x=>{ st+='<li>'+esc(x)+'</li>'; });
  const probe = s.probe ? '<div class="card-f"><button class="probe" onclick="askFromProbe('+JSON.stringify(s.probe).replace(/"/g,'&quot;')+')"><svg viewBox="0 0 24 24" fill="none"><path d="M21 12a8 8 0 0 1-11.6 7.1L4 20l1-5A8 8 0 1 1 21 12z" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/></svg>Ask about this</button></div>' : '';
  return '<div class="card '+pc+'">'
    +'<div class="card-h"><span class="pill '+pc+'">'+priLabel(s.priority)+'</span>'
    +'<span class="ct">'+esc(s.title)+'</span><span class="cat">'+esc(s.category)+'</span></div>'
    +'<div class="card-b">'
    +'<div class="expl">'+esc(s.explanation||s.summary||'')+'</div>'
    +'<div class="evidence"><div class="lab">Evidence</div>'+ev+'</div>'
    +'<div class="steps"><div class="lab">Recommended next steps</div><ul>'+st+'</ul></div>'
    +'</div>'+probe+'</div>';
}

async function loadLatestSignals(){
  document.getElementById('sig-body').innerHTML='<div class="sig-loading">Running analysis…</div>';
  try{
    const r=await fetch('/signals/latest'); const run=await r.json();
    currentRunId=null;              // freshly computed, not yet saved
    renderRun(run);
    updateBadge(run.counts);
  }catch(e){ document.getElementById('sig-body').innerHTML='<div class="empty">Could not load analysis: '+esc(e)+'</div>'; }
}

async function rerun(){
  const btn=document.getElementById('btn-rerun'); if(btn){btn.disabled=true;btn.textContent='Running…';}
  try{
    const r=await fetch('/signals/run',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({trigger:'manual: re-run from console',deliver:false})});
    const data=await r.json();
    currentRunId=data.run_id||null;
    renderRun(data.run||data);
    updateBadge((data.run||data).counts);
    loadHistory();
    toast('Analysis re-run and saved to history.');
  }catch(e){ toast('Re-run failed: '+e,true); }
}

async function sendReport(){
  const btn=document.getElementById('btn-send'); if(btn){btn.disabled=true;btn.textContent='Sending…';}
  try{
    const r=await fetch('/signals/send',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({run_id:currentRunId})});
    const data=await r.json();
    currentRunId=data.run_id||currentRunId;
    const em=data.delivery&&data.delivery.email, sm=data.delivery&&data.delivery.sms;
    let msg;
    if(em&&em.sent){ msg='Report emailed to '+ (em.to?em.to.length:0) +' recipient(s).'; }
    else if(em&&em.simulated){ msg='Email not sent (SMTP not configured) — saved to outbox for review. See README to enable.'; }
    else { msg='Email: '+((em&&em.detail)||'unknown'); }
    if(sm){ if(sm.sent) msg+=' SMS sent.'; else if(sm.simulated) msg+=' SMS simulated (disabled).'; }
    toast(msg);
    loadHistory();
  }catch(e){ toast('Send failed: '+e,true); }
  if(btn){btn.disabled=false;btn.innerHTML='<svg viewBox="0 0 24 24" fill="none"><path d="M4 12l16-7-7 16-2-6-7-3z" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/></svg>Send now';}
}

function previewEmail(){
  // ensure we have a saved id so preview can fetch it; if not saved yet, save via run then open
  if(currentRunId){ window.open('/signals/preview?id='+encodeURIComponent(currentRunId),'_blank'); return; }
  fetch('/signals/run',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({trigger:'preview',deliver:false})})
    .then(r=>r.json()).then(data=>{ currentRunId=data.run_id; window.open('/signals/preview?id='+encodeURIComponent(currentRunId),'_blank'); loadHistory(); })
    .catch(e=>toast('Preview failed: '+e,true));
}

async function loadHistory(){
  try{
    const r=await fetch('/signals/history'); const runs=await r.json();
    const wrap=document.getElementById('history-wrap'), list=document.getElementById('history-list');
    if(!runs.length){ wrap.style.display='none'; return; }
    wrap.style.display='block';
    list.innerHTML=runs.map(run=>{
      const c=run.counts||{};
      let chips='';
      if(c.high) chips+='<span class="dotc hi">'+c.high+' H</span>';
      if(c.medium) chips+='<span class="dotc med">'+c.medium+' M</span>';
      if(c.low) chips+='<span class="dotc lo">'+c.low+' L</span>';
      if(!chips) chips='<span class="dotc lo">clear</span>';
      const when=(run.generated_at||'').replace('T',' ').slice(0,16);
      return '<div class="hrow" onclick="openRun('+JSON.stringify(run.run_id).replace(/"/g,'&quot;')+')">'
        +'<div class="hdate">'+esc(run.as_of||when)+'</div>'
        +'<div class="hhead">'+esc(run.headline||'')+' · '+esc(run.trigger||'')+'</div>'
        +'<div class="hc">'+chips+'</div></div>';
    }).join('');
  }catch(e){ /* history is best-effort */ }
}

async function openRun(id){
  try{
    const r=await fetch('/signals/run?id='+encodeURIComponent(id)); const run=await r.json();
    currentRunId=id; renderRun(run); updateBadge(run.counts);
    document.querySelector('.sig-wrap').scrollTop=0;
    toast('Loaded report from '+(run.as_of||id));
  }catch(e){ toast('Could not open report: '+e,true); }
}

function updateBadge(counts){
  const b=document.getElementById('sig-badge');
  const n=(counts&&counts.high)||0;
  b.textContent=n; b.classList.toggle('zero',n===0);
}

/* ---------------- status poll ---------------- */
async function poll(){
  try{
    const r=await fetch('/status'); const s=await r.json();
    document.getElementById('sdot').className='dot'+(s.api_key?'':' off');
    document.getElementById('stext').textContent=(s.api_key?'':'no API key · ')+s.days+' reports loaded';
    (s.new_reports||[]).forEach(n=>{
      if(currentTab==='ask'){
        el('m ingest','<svg viewBox="0 0 24 24" fill="none"><path d="M12 3v12m0 0l-4-4m4 4l4-4M5 21h14" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg> New report ingested — '+esc(n.date)+' ('+esc(n.fuel_L)+' L). Ask me about it.');
      }
      toast('New report ingested — '+n.date+'. Signals updated.');
      // refresh signals if that tab has been opened
      if(signalsLoaded){ loadLatestSignals(); loadHistory(); }
    });
  }catch(e){ document.getElementById('sdot').className='dot off'; document.getElementById('stext').textContent='disconnected'; }
}
poll(); setInterval(poll,2500);
</script>
</body></html>"""


# ---------------------------------------------------------------------------
# HTTP handling
# ---------------------------------------------------------------------------
def _ensure_saved(run_id):
    """Return (run_obj, run_id). If run_id given and exists, load it; else run
    fresh and save it."""
    if run_id:
        r = intelligence.load_run(run_id)
        if r:
            return r, run_id
    run = intelligence.run(trigger="manual: send from console")
    intelligence.save_run(run)
    return run, run["run_id"]


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, ctype, body):
        self.send_response(code)
        self.send_header("content-type", ctype)
        self.end_headers()
        self.wfile.write(body if isinstance(body, bytes) else body.encode())

    def _json(self, code, obj):
        self._send(code, "application/json", json.dumps(obj, default=str))

    def _read_body(self):
        length = int(self.headers.get("content-length", 0))
        if not length:
            return {}
        try:
            return json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            return {}

    # ---- GET ----
    def do_GET(self):
        parsed = urlparse(self.path)
        path, qs = parsed.path, parse_qs(parsed.query)

        if path == "/status":
            self._json(200, {
                "api_key": config.api_key_present(),
                "days": analysis.day_count(),
                "new_reports": watcher.drain_events(),
            })
        elif path == "/signals/latest":
            run = intelligence.run(trigger="view: console open")
            self._json(200, run)
        elif path == "/signals/history":
            self._json(200, intelligence.list_runs())
        elif path == "/signals/run":
            rid = (qs.get("id") or [None])[0]
            run = intelligence.load_run(rid) if rid else None
            if run:
                self._json(200, run)
            else:
                self._json(404, {"error": "run not found"})
        elif path == "/signals/preview":
            rid = (qs.get("id") or [None])[0]
            run = intelligence.load_run(rid) if rid else None
            if not run:
                run = intelligence.run(trigger="preview")
                intelligence.save_run(run)
            self._send(200, "text/html; charset=utf-8", report_mod.render_html(run))
        else:
            self._send(200, "text/html; charset=utf-8", PAGE)

    # ---- POST ----
    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/ask":
            data = self._read_body()
            result = claude_client.answer_question(data.get("message", ""), data.get("history", []))
            self._json(200, result)

        elif path == "/signals/run":
            data = self._read_body()
            run = intelligence.run(trigger=data.get("trigger", "manual"))
            intelligence.save_run(run)
            delivery = None
            if data.get("deliver"):
                delivery = notify.deliver(run)
            self._json(200, {"run_id": run["run_id"], "run": run, "delivery": delivery})

        elif path == "/signals/send":
            data = self._read_body()
            run, rid = _ensure_saved(data.get("run_id"))
            delivery = notify.deliver(run)
            self._json(200, {"run_id": rid, "delivery": delivery})

        else:
            self._send(404, "text/plain", "not found")


def main():
    bootstrap()
    print("\n" + "=" * 62)
    print("  Navigator Z — Vessel Intelligence  (Ask + Signals)")
    print("=" * 62)
    print(f"  Reports loaded : {analysis.day_count()}  (from ./{config.REPORTS_DIR}/)")
    m = analysis.model_summary()
    print(f"  Fuel model     : {m['base_L']} L base + {m['rate']} L/DP-hr")
    print(f"  Model          : {config.MODEL}")
    print(f"  API key        : {'SET' if config.api_key_present() else 'NOT SET — add it in app/config.py'}")
    print(f"  Email (SMTP)   : {'configured' if config.smtp_configured() else 'not configured (reports saved to reports_out/outbox/)'}")
    print(f"  SMS (Twilio)   : {'enabled' if config.sms_configured() else 'off (digests saved to reports_out/outbox/)'}")
    print(f"  Recipients     : {len(config.RECIPIENTS)}")
    print(f"  Open           : http://localhost:{config.PORT}")
    print("=" * 62)
    print("  Drop a new .xlsx into ./reports/ while running:")
    print("   - the chatbot ingests it, AND")
    print("   - the intelligence engine runs and emails/texts the report.")
    print("  Ctrl+C to stop.\n")
    ThreadingHTTPServer((config.HOST, config.PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
