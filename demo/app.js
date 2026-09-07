const STORAGE_KEY = "tilki-ai-os-demo-v003";
const $ = (id) => document.getElementById(id);

const defaults = {
  models: [
    { name: "qwen3:4b", vram: 4.2, loaded: true, family: "Qwen3", quant: "Q4_K_M" },
    { name: "nomic-embed-text", vram: 0.7, loaded: false, family: "Nomic", quant: "F16" }
  ],
  agents: [
    { name: "researcher", command: "python researcher.py", running: true, pid: 18442 },
    { name: "coder", command: "python coder.py", running: false, pid: null }
  ],
  events: [],
  cpu: 18,
  ram: 12.8
};

let state = loadState();
let terminalHistory = [];

function cloneDefaults() { return JSON.parse(JSON.stringify(defaults)); }
function loadState() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return cloneDefaults();
    const parsed = JSON.parse(raw);
    return { ...cloneDefaults(), ...parsed };
  } catch { return cloneDefaults(); }
}
function save() { localStorage.setItem(STORAGE_KEY, JSON.stringify(state)); }
function now() { return new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" }); }
function escapeHtml(value) { return String(value).replace(/[&<>'"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c])); }

function event(message, type = "RUNTIME") {
  state.events.unshift({ time: now(), type, message });
  state.events = state.events.slice(0, 120);
  save();
  renderEvents();
  renderTelemetry();
}

function usedVram() { return state.models.filter(m => m.loaded).reduce((sum, m) => sum + Number(m.vram || 0), 0); }
function availableVram() { return Math.max(0, 24 - usedVram()); }

function renderTelemetry() {
  const used = usedVram();
  const runningAgents = state.agents.filter(a => a.running).length;
  $("gpuUsed").textContent = used.toFixed(1);
  $("gpuBar").style.width = `${Math.min(100, (used / 24) * 100)}%`;
  $("gpuUtil").textContent = `${Math.min(96, Math.round(9 + used * 3.2 + runningAgents * 5))}% util`;
  $("gpuTemp").textContent = `${Math.round(39 + used * 1.15)}°C`;
  $("gpuStatus").textContent = used > 21 ? "VRAM PRESSURE" : "NVIDIA READY";
  $("gpuStatus").className = `status ${used > 21 ? "warn" : "good"}`;
  $("modelCount").textContent = state.models.length;
  $("agentCount").textContent = state.agents.length;
  $("eventCount").textContent = state.events.length;
  $("loadedCount").textContent = state.models.filter(m => m.loaded).length;
  $("runningCount").textContent = runningAgents;
  state.cpu = Math.max(9, Math.min(95, Math.round(14 + runningAgents * 9 + Math.random() * 5)));
  state.ram = Math.max(8, Math.min(30, 9.5 + runningAgents * 1.3 + state.models.length * 0.7));
  $("cpuValue").textContent = `${state.cpu}%`;
  $("ramValue").textContent = `${state.ram.toFixed(1)} / 32 GB`;
}

function renderModels() {
  const host = $("modelList");
  if (!state.models.length) { host.innerHTML = '<div class="empty">No models installed. Pull one to begin.</div>'; return; }
  host.innerHTML = state.models.map(model => `
    <div class="item">
      <div>
        <div class="item-title">${escapeHtml(model.name)} ${model.loaded ? '<span class="status good">LOADED</span>' : ''}</div>
        <div class="item-meta">${escapeHtml(model.family || 'Local model')} · ${escapeHtml(model.quant || 'unknown')} · ~${Number(model.vram).toFixed(1)} GB VRAM</div>
      </div>
      <div class="item-actions">
        ${model.loaded ? `<button class="stop" data-model-stop="${escapeHtml(model.name)}">UNLOAD</button>` : `<button class="run" data-model-run="${escapeHtml(model.name)}">LOAD</button>`}
        <button data-model-inspect="${escapeHtml(model.name)}">INSPECT</button>
        <button class="danger" data-model-remove="${escapeHtml(model.name)}">REMOVE</button>
      </div>
    </div>`).join("");
}

function renderAgents() {
  const host = $("agentList");
  if (!state.agents.length) { host.innerHTML = '<div class="empty">No agents registered. Add one to begin.</div>'; return; }
  host.innerHTML = state.agents.map(agent => `
    <div class="item">
      <div>
        <div class="item-title">${escapeHtml(agent.name)} ${agent.running ? '<span class="status good">RUNNING</span>' : '<span class="status">STOPPED</span>'}</div>
        <div class="item-meta">${escapeHtml(agent.command)}${agent.pid ? ` · pid ${agent.pid}` : ''}</div>
      </div>
      <div class="item-actions">
        ${agent.running ? `<button class="stop" data-agent-stop="${escapeHtml(agent.name)}">STOP</button>` : `<button class="run" data-agent-run="${escapeHtml(agent.name)}">RUN</button>`}
        <button data-agent-logs="${escapeHtml(agent.name)}">LOGS</button>
        <button class="danger" data-agent-remove="${escapeHtml(agent.name)}">REMOVE</button>
      </div>
    </div>`).join("");
}

function renderEvents() {
  const host = $("eventStream");
  if (!state.events.length) { host.innerHTML = '<div class="empty">Runtime events will appear here.</div>'; return; }
  host.innerHTML = state.events.map(e => `<div class="event"><time>${escapeHtml(e.time)}</time><span><b>${escapeHtml(e.type)}</b> ${escapeHtml(e.message)}</span></div>`).join("");
}

function renderAll() { renderModels(); renderAgents(); renderEvents(); renderTelemetry(); }

function print(text, kind = "") {
  const div = document.createElement("div");
  div.className = `terminal-line ${kind}`;
  div.textContent = text;
  $("terminalOutput").appendChild(div);
  $("terminalOutput").scrollTop = $("terminalOutput").scrollHeight;
}

function modelByName(name) { return state.models.find(m => m.name === name); }
function agentByName(name) { return state.agents.find(a => a.name === name); }

function loadModel(name) {
  const model = modelByName(name);
  if (!model) throw new Error(`Model '${name}' is not installed`);
  if (model.loaded) return `${name} is already loaded`;
  if (model.vram > availableVram()) throw new Error(`Not enough VRAM: need ${model.vram.toFixed(1)} GB, ${availableVram().toFixed(1)} GB available`);
  model.loaded = true; save(); renderAll(); event(`Loaded ${name} into GPU memory`, "MODEL");
  return `Loaded ${name} · estimated VRAM ${model.vram.toFixed(1)} GB`;
}
function unloadModel(name) {
  const model = modelByName(name); if (!model) throw new Error(`Model '${name}' is not installed`);
  model.loaded = false; save(); renderAll(); event(`Unloaded ${name} from GPU memory`, "MODEL"); return `Unloaded ${name}`;
}
function removeModel(name) {
  const model = modelByName(name); if (!model) throw new Error(`Model '${name}' is not installed`);
  if (model.loaded) throw new Error(`Unload '${name}' before removing it`);
  state.models = state.models.filter(m => m.name !== name); save(); renderAll(); event(`Removed ${name}`, "MODEL"); return `Removed ${name}`;
}
function startAgent(name) {
  const agent = agentByName(name); if (!agent) throw new Error(`Agent '${name}' is not registered`);
  if (agent.running) return `${name} is already running (pid ${agent.pid})`;
  agent.running = true; agent.pid = 18000 + Math.floor(Math.random() * 5000); save(); renderAll(); event(`Supervisor started ${name} (pid ${agent.pid})`, "AGENT"); return `Started ${name} · pid ${agent.pid}`;
}
function stopAgent(name) {
  const agent = agentByName(name); if (!agent) throw new Error(`Agent '${name}' is not registered`);
  if (!agent.running) return `${name} is already stopped`;
  const pid = agent.pid; agent.running = false; agent.pid = null; save(); renderAll(); event(`Stopped ${name} (pid ${pid})`, "AGENT"); return `Stopped ${name}`;
}

function tokenize(input) {
  const out = []; let current = ""; let quote = null;
  for (let i=0;i<input.length;i++) { const c=input[i]; if (quote) { if (c===quote) quote=null; else current+=c; } else if (c==='"' || c==="'") quote=c; else if (/\s/.test(c)) { if (current) { out.push(current); current=""; } } else current+=c; }
  if (current) out.push(current); return out;
}

function execute(raw) {
  const input = raw.trim().replace(/^tilki\s+/, "");
  if (!input) return;
  terminalHistory.push(input);
  print(`› tilki ${input}`, "cmd");
  const args = tokenize(input); const [root, action, name] = args;
  try {
    if (root === "help") {
      print("status\ngpu\nmodel list | running | pull NAME | run NAME | stop NAME | inspect NAME | remove NAME\nagent list | add NAME --command \"CMD\" | run NAME | stop NAME | status NAME | logs NAME\nclear", "dim");
    } else if (root === "clear") {
      $("terminalOutput").innerHTML = "";
    } else if (root === "status") {
      print(`TILKI AI OS v0.0.3\nGPU      ${usedVram().toFixed(1)} / 24.0 GB VRAM\nMODELS   ${state.models.filter(m=>m.loaded).length} loaded / ${state.models.length} installed\nAGENTS   ${state.agents.filter(a=>a.running).length} running / ${state.agents.length} registered\nOLLAMA   API OK`, "ok");
    } else if (root === "gpu") {
      print(`GPU 0  NVIDIA RTX 4090 | VRAM ${usedVram().toFixed(1)}/24.0 GB | util ${$("gpuUtil").textContent} | ${$("gpuTemp").textContent}`, "ok");
    } else if (root === "model") {
      if (action === "list") print(state.models.length ? state.models.map(m=>`${m.name}  ${m.loaded?'[loaded]':''}  ~${m.vram.toFixed(1)}GB`).join("\n") : "No models installed.");
      else if (action === "running") print(state.models.filter(m=>m.loaded).map(m=>`${m.name}  ${m.vram.toFixed(1)}GB`).join("\n") || "No models loaded.");
      else if (action === "run") print(loadModel(name), "ok");
      else if (action === "stop") print(unloadModel(name), "ok");
      else if (action === "remove") print(removeModel(name), "ok");
      else if (action === "inspect") { const m=modelByName(name); if(!m) throw new Error(`Model '${name}' is not installed`); print(`${m.name}\nfamily: ${m.family}\nquantization: ${m.quant}\nestimated_vram_gb: ${m.vram.toFixed(1)}\nfits_now: ${m.vram <= availableVram() || m.loaded}\nloaded: ${m.loaded}`, "ok"); }
      else if (action === "pull") { if (!name) throw new Error("Usage: model pull NAME"); if(modelByName(name)) throw new Error(`Model '${name}' already exists`); state.models.push({name,vram:3.6,loaded:false,family:"Local",quant:"Q4_K_M"}); save(); renderAll(); event(`Pulled ${name}`,"MODEL"); print(`Pulled ${name}`,"ok"); }
      else throw new Error("Unknown model command. Try: help");
    } else if (root === "agent") {
      if (action === "list") print(state.agents.length ? state.agents.map(a=>`${a.name}  [${a.running?'running':'stopped'}]  ${a.command}`).join("\n") : "No agents registered.");
      else if (action === "run") print(startAgent(name), "ok");
      else if (action === "stop") print(stopAgent(name), "ok");
      else if (action === "status") { const a=agentByName(name); if(!a) throw new Error(`Agent '${name}' is not registered`); print(`${a.name}\nstatus: ${a.running?'running':'stopped'}\npid: ${a.pid || 'n/a'}\ncommand: ${a.command}`, "ok"); }
      else if (action === "logs") { const a=agentByName(name); if(!a) throw new Error(`Agent '${name}' is not registered`); print(`[supervisor] agent=${a.name}\n[runtime] command=${a.command}\n[runtime] status=${a.running?'running':'stopped'}${a.pid?` pid=${a.pid}`:''}`, "dim"); }
      else if (action === "add") { if(!name) throw new Error("Usage: agent add NAME --command \"CMD\""); const idx=args.indexOf("--command"); const cmd=idx>=0?args.slice(idx+1).join(" "):"python agent.py"; if(agentByName(name)) throw new Error(`Agent '${name}' already exists`); state.agents.push({name,command:cmd,running:false,pid:null}); save(); renderAll(); event(`Registered ${name}`,"AGENT"); print(`Registered ${name}`,"ok"); }
      else throw new Error("Unknown agent command. Try: help");
    } else throw new Error(`Unknown command '${root}'. Try: help`);
  } catch (err) { print(`Error: ${err.message}`, "err"); }
}

$("terminalForm").addEventListener("submit", e => { e.preventDefault(); const input=$("terminalInput"); execute(input.value); input.value=""; input.focus(); });
document.querySelectorAll(".quick-commands button").forEach(btn => btn.addEventListener("click", () => execute(btn.dataset.cmd)));
$("pullModelBtn").addEventListener("click", () => $("modelDialog").showModal());
$("addAgentBtn").addEventListener("click", () => $("agentDialog").showModal());
$("modelForm").addEventListener("submit", e => { if (e.submitter?.value === "cancel") return; e.preventDefault(); const name=$("modelName").value.trim(); const vram=Number($("modelVram").value); if(!name || !vram) return; if(modelByName(name)){ print(`Error: Model '${name}' already exists`,"err"); $("modelDialog").close(); return; } state.models.push({name,vram,loaded:false,family:"Local",quant:"Q4_K_M"}); save(); renderAll(); event(`Pulled ${name} into local model store`,"MODEL"); $("modelDialog").close(); });
$("agentForm").addEventListener("submit", e => { if (e.submitter?.value === "cancel") return; e.preventDefault(); const name=$("agentName").value.trim(); const command=$("agentCommand").value.trim(); if(!name||!command) return; if(agentByName(name)){ print(`Error: Agent '${name}' already exists`,"err"); $("agentDialog").close(); return; } state.agents.push({name,command,running:false,pid:null}); save(); renderAll(); event(`Registered ${name}: ${command}`,"AGENT"); $("agentDialog").close(); });
$("resetBtn").addEventListener("click", () => { state=cloneDefaults(); save(); $("terminalOutput").innerHTML=""; renderAll(); event("Sandbox reset to baseline", "SYSTEM"); print("Sandbox reset. Type 'help' for commands.","ok"); });
$("clearEventsBtn").addEventListener("click", () => { state.events=[]; save(); renderEvents(); renderTelemetry(); });
document.addEventListener("click", e => { const t=e.target; if(!(t instanceof HTMLElement)) return; const val=(key)=>t.getAttribute(key); try { if(val("data-model-run")) print(loadModel(val("data-model-run")),"ok"); else if(val("data-model-stop")) print(unloadModel(val("data-model-stop")),"ok"); else if(val("data-model-remove")) print(removeModel(val("data-model-remove")),"ok"); else if(val("data-model-inspect")) execute(`model inspect ${val("data-model-inspect")}`); else if(val("data-agent-run")) print(startAgent(val("data-agent-run")),"ok"); else if(val("data-agent-stop")) print(stopAgent(val("data-agent-stop")),"ok"); else if(val("data-agent-remove")) { const n=val("data-agent-remove"); const a=agentByName(n); if(a?.running) throw new Error(`Stop '${n}' before removing it`); state.agents=state.agents.filter(x=>x.name!==n); save(); renderAll(); event(`Removed ${n}`,"AGENT"); print(`Removed ${n}`,"ok"); } else if(val("data-agent-logs")) execute(`agent logs ${val("data-agent-logs")}`); } catch(err){ print(`Error: ${err.message}`,"err"); } });

setInterval(() => renderTelemetry(), 2500);
renderAll();
if (!state.events.length) event("Command Center sandbox booted", "SYSTEM");
print("TILKI AI OS Command Center v0.0.3", "ok");
print("Sandbox runtime online. Type 'help' or use the quick commands below.", "dim");
