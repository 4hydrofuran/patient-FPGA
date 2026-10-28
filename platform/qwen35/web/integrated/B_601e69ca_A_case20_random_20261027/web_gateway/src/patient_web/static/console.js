"use strict";
const el = (id) => document.getElementById(id);
let sid = null, stream = null, current = null, service = null, submitting = false;
let pending = null, cancelCommand = null;
let eventLog = [];
let evaluationCache = null, evaluationView = "summary";
let composing = false, compositionEnded = -Infinity, refreshTimer = null, refreshFlight = null;
let streamHealthy = false;
const turnNodes = new Map(), timings = new Map();
window.patientResponseTimings = () => Array.from(timings.values(), value => ({...value}));
function timingKey(session, request){ return `${session}:${request}`; }
function timingStart(session, request){
  const key = timingKey(session, request);
  if (!timings.has(key)) timings.set(key, {session_id:session, request_id:request,
    submitted_ms:performance.now(), clock:"browser performance.now", measurement:"two rAF after checked answer DOM update"});
  while (timings.size > 100) timings.delete(timings.keys().next().value);
}
function observePaint(snapshot){
  for (const turn of snapshot.turns) {
    const t = timings.get(timingKey(snapshot.session_id, turn.request_id));
    if (!turn.answer || !t || t.paint_scheduled || t.painted_ms !== undefined) continue;
    t.paint_scheduled = true;
    requestAnimationFrame(() => requestAnimationFrame(() => {
      if (sid !== snapshot.session_id || current?.epoch !== snapshot.epoch ||
          !el("turns").querySelector(`[data-request-id="${CSS.escape(turn.request_id)}"]`)) {
        t.paint_scheduled = false; return;
      }
      t.painted_ms = performance.now(); t.submit_to_paint_ms = t.painted_ms - t.submitted_ms;
      t.answer_source = turn.answer_source; t.actual_backend = turn.actual_backend;
      t.visibility_state = document.visibilityState;
    }));
  }
}
function scheduleRefresh(){
  if (refreshTimer !== null) return;
  refreshTimer = setTimeout(() => { refreshTimer = null; refresh().catch(showError); }, 25);
}
const reviewViews = ["summary", "topics", "review", "transcript"];
const reviewPanels = {summary:"chief-summary", topics:"topic-details", review:"review-details", transcript:"transcript-panel"};
const labels = {STARTING:"模型加载中", SWITCHING:"正在切换推理模式…", READY:"等待提问", PROCESSING:"正在处理",
  GENERATING:"患者正在思考", VALIDATING:"正在检查回答", CANCELLING:"正在取消并收尾",
  FINISHED:"问诊已结束", FAILED:"后端不可用", STOPPING:"服务正在停止"};
function id(){ return crypto.randomUUID(); }
function showError(error){ el("error").textContent = error?.message || ""; }
async function api(path, body){
  const response = await fetch(path, body === undefined ? {} : {
    method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(body)
  });
  const data = await response.json();
  if (!response.ok) {
    const error = new Error(data.error?.message || "请求失败");
    error.code = data.error?.code; error.httpStatus = response.status; throw error;
  }
  return data;
}
function controls(){
  const ready = !!service?.ready;
  const open = !!current && !current.closed;
  const busy = !!current?.active_request_id;
  el("start").disabled = !ready || open || submitting;
  el("question").disabled = !ready || !open || busy || submitting;
  el("send").disabled = !ready || !open || busy || submitting;
  el("cancel").hidden = service?.capabilities?.cancel_turn === false;
  el("cancel").disabled = service?.capabilities?.cancel_turn === false || !busy || current.phase === "CANCELLING";
  el("finish").disabled = !open || busy || submitting;
  el("new-session").disabled = !ready || open || busy || submitting;
  el("backend-choice").disabled = busy || submitting || ["STARTING", "SWITCHING", "STOPPING"].includes(service?.phase);
  if (service?.phase === "SWITCHING") el("state").textContent = labels.SWITCHING;
}
function clearEvaluation(){
  evaluationCache = null;
  el("score-section").hidden = true; el("evaluation-result").hidden = true;
  el("evaluation-loading").hidden = false;
  el("evaluation-loading").textContent = "正在读取本场评价…";
  setEvaluationView("summary");
}
function chiefPose(evaluating){
  el("chief-portrait").src = evaluating ? "/display/chief-physician-speaking.png" : "/display/chief-physician.png";
  el("chief-state").textContent = evaluating ? "评阅中" : "查阅记录";
}
function setEvaluationView(view, focusTab=false){
  if (!reviewViews.includes(view)) return;
  evaluationView = view;
  for (const name of reviewViews) {
    const selected = name === view;
    el(`tab-${name}`).setAttribute("aria-selected", String(selected));
    el(`tab-${name}`).tabIndex = selected ? 0 : -1;
    el(reviewPanels[name]).hidden = !selected;
  }
  el("evaluation-overview").hidden = view === "transcript";
  el("evaluation-scroll").scrollTop = 0;
  if (evaluationCache) chiefPose(view === "summary");
  if (focusTab) el(`tab-${view}`).focus({preventScroll:true});
}
function evidenceList(entries){
  const list = document.createElement("ol"); list.className = "evidence-list";
  const status = {COMPLETED:"本轮已完成", CANCELLED:"本轮已取消", FAILED:"本轮回答失败"};
  for (const item of entries) {
    const row = document.createElement("li");
    const quote = document.createElement("p"); quote.className = "evidence-quote";
    quote.textContent = `第 ${item.question_number} 问　${item.question}`;
    const note = document.createElement("p"); note.className = "muted";
    note.textContent = item.reason_label || status[item.turn_status] || item.turn_status;
    if (!item.answer_published) note.textContent += "；本轮没有患者回答。";
    row.append(quote, note); list.append(row);
  }
  return list;
}
function renderEvaluation(result){
  if (evaluationCache?.evaluation_id === result.evaluation_id) return;
  evaluationCache = result;
  el("evaluation-loading").hidden = true; el("evaluation-result").hidden = false;
  el("total-score").textContent = result.rule_score.score;
  el("max-score").textContent = ` / ${result.rule_score.max_score}`;
  el("coverage-count").textContent = `已覆盖 ${result.covered_topics.length} 项，尚缺 ${result.missing_topics.length} 项`;
  const caseTitle = "随机病例";
  el("evaluation-case").textContent = `${caseTitle}　·　本场 ${result.frozen_turn_count} 次提问`;
  // The exact frozen score is already above the reading pane; avoid repeating that sentence.
  el("summary-text").textContent = result.summary_text.split("\n").filter((line, index) =>
    index !== 0 || !line.startsWith("本次问诊话题覆盖得分为 ")).join("\n");
  el("evaluation-disclaimer").textContent = result.disclaimer;
  el("scoring-note").textContent = result.scoring_note;
  el("topics").replaceChildren();
  for (const topic of result.topics) {
    const row = document.createElement("div"); row.className = `topic-row${topic.covered ? " covered" : ""}`;
    const name = document.createElement("h3"); name.textContent = topic.label;
    const points = document.createElement("span"); points.className = "topic-points";
    points.textContent = `${topic.points} / ${topic.max_points}`;
    const state = document.createElement("p"); state.className = "topic-status";
    state.textContent = topic.covered ? "已覆盖" : "未覆盖";
    row.append(name, points, state);
    if (topic.evidence.length) {
      const details = document.createElement("details"); details.className = "topic-evidence";
      const summary = document.createElement("summary");
      summary.textContent = `提问依据 · ${topic.evidence.length} 条`;
      details.append(summary, evidenceList(topic.evidence));
      details.addEventListener("toggle", () => { if (details.open) chiefPose(false); });
      row.append(details);
    }
    el("topics").append(row);
  }
  el("review-title").textContent = `需复核的提问 · ${result.review_items.length} 条`;
  el("review-count").textContent = result.review_items.length ? ` ${result.review_items.length}` : "";
  el("review-items").replaceChildren();
  if (result.review_items.length) el("review-items").append(evidenceList(result.review_items));
  else { const p = document.createElement("p"); p.textContent = "本场没有被标记为待复核的提问。"; el("review-items").append(p); }
  el("evaluation-transcript").replaceChildren(...Array.from(el("turns").children, node => node.cloneNode(true)));
  if (!result.frozen_turn_count) { const p = document.createElement("p"); p.textContent = "本场尚无提问记录。"; el("evaluation-transcript").append(p); }
  setEvaluationView("summary");
}
function render(snapshot){
  const transcript = el("turns");
  const previousScroll = transcript.scrollTop;
  const followLatest = transcript.scrollHeight - previousScroll - transcript.clientHeight < 48;
  const newQuestion = current?.session_id !== snapshot.session_id || snapshot.turns.length > current.turns.length;
  if (current?.session_id !== snapshot.session_id) {
    turnNodes.clear(); transcript.replaceChildren();
    if (snapshot.chief_complaint) {
      const opening = document.createElement("p");
      opening.className = "patient-chief-complaint";
      opening.textContent = `患者主诉：${snapshot.chief_complaint}`;
      opening.dataset.source = snapshot.chief_complaint_source;
      transcript.append(opening);
    }
  }
  current = snapshot;
  el("state").textContent = labels[snapshot.phase] || snapshot.phase;
  el("case-label").textContent = snapshot.closed ? "下场随机抽取" : "病例随机抽取";
  el("stage-label").textContent = snapshot.closed ? "主任评价" : "文字问诊";
  el("consultation-section").hidden = snapshot.closed;
  document.body.classList.toggle("evaluation-mode", snapshot.closed);
  document.body.classList.toggle("consultation-active", !snapshot.closed);
  el("score-section").hidden = !snapshot.closed;
  for (const turn of snapshot.turns) {
    const signature = JSON.stringify([turn.question, turn.answer, turn.answer_source, turn.actual_backend, turn.status, turn.error]);
    const old = turnNodes.get(turn.request_id);
    if (old?.signature === signature) continue;
    const p = document.createElement("p");
    p.dataset.requestId = turn.request_id;
    const question = document.createElement("strong"); question.textContent = `医生：${turn.question}`;
    p.append(question, document.createElement("br"));
    const answer = document.createElement("span");
    answer.textContent = turn.answer ? `患者：${turn.answer}`
      : turn.status === "CANCELLED" ? "本轮已取消，未发布患者回答。"
      : turn.status === "FAILED" ? turn.error?.message || "本轮失败。" : "正在等待回答…";
    p.append(answer);
    if (turn.answer_source === "MODEL_CACHE") {
      const badge = document.createElement("small"); badge.className = "answer-cache-source";
      badge.textContent = "　已核验模型答案 · 缓存";
      badge.title = "本轮未重新运行模型；原模型生成已通过EOS和内容核验，本轮已重新核验病例事实。";
      p.append(badge);
    }
    if (turn.answer && turn.answer_source !== "MODEL_CACHE") {
      const kind = turn.delivery_receipt?.actual_backend;
      const note = document.createElement("small"); note.className = "turn-backend";
      note.textContent = kind === "FPGA_REAL" ? "FPGA" : kind === "CPU_REFERENCE" ? "CPU"
        : turn.answer_source === "DEMO_RULE" ? "规则演示" : "规则模板";
      p.append(document.createElement("br"), note);
    }
    if (old) old.node.replaceWith(p); else transcript.append(p);
    turnNodes.set(turn.request_id, {node:p, signature});
  }
  transcript.scrollTop = followLatest || newQuestion ? transcript.scrollHeight : previousScroll;
  controls();
  observePaint(snapshot);
}
async function refreshOnce(){
  if (!sid) return;
  const target = sid;
  const snapshot = await api(`/ui/v1/sessions/${target}`);
  if (target !== sid) return;
  if (current?.instance_id === snapshot.instance_id && current.session_id === snapshot.session_id && snapshot.cursor < current.cursor) return;
  if (current?.instance_id === snapshot.instance_id && current.session_id === snapshot.session_id && snapshot.epoch < current.epoch) return;
  render(snapshot);
  if (current.closed) {
    if (evaluationCache?.session_id === target) return;
    try {
      const evaluation = await api(`/ui/v1/sessions/${target}/evaluation`);
      if (target !== sid) return;
      renderEvaluation(evaluation);
    } catch (error) {
      if (target === sid) el("evaluation-loading").textContent = "评价暂未读取成功，正在重试…";
      throw error;
    }
  }
}
async function refresh(){
  if (refreshFlight?.target === sid) return refreshFlight.promise;
  const flight = {target:sid};
  flight.promise = refreshOnce().finally(() => { if (refreshFlight === flight) refreshFlight = null; });
  refreshFlight = flight;
  return flight.promise;
}
function connect(){
  if (stream) stream.close();
  streamHealthy = false;
  const target = sid, connection = new EventSource(`/ui/v1/events?session_id=${encodeURIComponent(sid)}`);
  stream = connection;
  connection.onopen = () => { if (stream === connection) streamHealthy = true; };
  const names = ["session.snapshot","session.created","turn.accepted","response.preparing",
    "generation.started","validation.started","answer.ready","turn.completed","cancel.pending",
    "turn.cancelled","turn.failed","session.finished","evaluation.ready","service.ready","service.failed"];
  for (const name of names) stream.addEventListener(name, (message) => {
    const data = JSON.parse(message.data);
    if (stream !== connection || sid !== target || (current && data.instance_id !== current.instance_id)) return;
    if (data.session_id && data.session_id !== sid) return;
    if (current && data.epoch < current.epoch) return;
    eventLog.push(`${data.seq}  ${data.event}`); eventLog = eventLog.slice(-100);
    el("events").textContent = eventLog.join("\n");
    streamHealthy = true;
    if (data.event === "session.snapshot") {
      if (!current || data.data.cursor >= current.cursor) render(data.data);
      if (data.data.closed && !evaluationCache) scheduleRefresh();
      return;
    }
    if (data.event === "answer.ready") {
      const t = timings.get(timingKey(sid, data.request_id));
      if (t && t.answer_ready_ms === undefined) t.answer_ready_ms = performance.now();
      if (current?.turns.some(turn => turn.request_id === data.request_id)) {
        render({...current, cursor:Math.max(current.cursor, data.seq), turns:current.turns.map(turn =>
          turn.request_id === data.request_id ? {...turn, answer:data.data.text,
            answer_source:data.data.answer_source, actual_backend:data.data.actual_backend,
            delivery_kind:data.data.delivery_kind, delivery_receipt:data.data.delivery_receipt,
            cache_provenance:data.data.cache_provenance} : turn)});
      }
    }
    scheduleRefresh();
  });
  connection.onerror = () => { if (stream !== connection) return; streamHealthy = false;
    el("state").textContent = "事件连接中断，正在恢复…"; scheduleRefresh(); };
}
async function poll(){
  try {
    service = await api("/ui/v1/status");
    const options = service.backend_options || [];
    el("backend-control").hidden = options.length < 2;
    if (JSON.stringify(options) !== el("backend-choice").dataset.options) {
      el("backend-choice").replaceChildren(...options.map(item => {
        const option = document.createElement("option"); option.value = item.id;
        option.textContent = item.label; return option;
      }));
      el("backend-choice").dataset.options = JSON.stringify(options);
    }
    el("backend-choice").value = service.backend.configured;
    if (current && current.instance_id !== service.instance_id) {
      if (stream) stream.close();
      sid = null; current = null; pending = null; cancelCommand = null;
      sessionStorage.removeItem("patient-web-session");
      el("turns").replaceChildren(); clearEvaluation();
      el("consultation-section").hidden = false; el("stage-label").textContent = "文字问诊";
      el("case-label").textContent = "病例随机抽取";
      document.body.classList.remove("evaluation-mode");
      document.body.classList.remove("consultation-active");
      showError(new Error("服务已重新启动，上一实例的内存会话已结束。"));
    }
    el("backend").textContent = service.backend.execution_kind === "DEMO_RULE" || service.backend.configured === "demo"
      ? service.demo_lab ? "规则演示 · 联调场景已启用 · 未接入模型" : "规则演示 · 未接入模型"
      : service.ready ? service.answer_cache ? "模型服务已就绪 · 支持已核验答案复用"
        : service.backend.execution_kind === "FPGA_REAL" ? "板端模型已连接 · PL 参与计算" : "CPU 模型已连接"
      : service.failure?.message || "真实模型正在加载…";
    el("case-pool").textContent = ` · 每场从${service.capabilities?.case_count || 20}例中随机抽取`;
    const stored = sessionStorage.getItem("patient-web-session");
    if (!sid && stored && service.current_session_id === stored) { sid = stored; await refresh(); connect(); }
    if (!sid && service.current_session_id) { sid = service.current_session_id; await refresh(); connect(); }
    if (sid && (!streamHealthy || (current?.closed && !evaluationCache))) await refresh();
    if (!sid || service.phase === "SWITCHING") el("state").textContent = labels[service.phase] || service.phase;
    controls();
  } catch (error) { showError(error); }
}
el("start").onclick = async () => {
  submitting = true; controls(); showError(null);
  try {
    const result = await api("/ui/v1/sessions", {request_id:id()});
    sid = result.session_id; pending = null; cancelCommand = null; eventLog = []; clearEvaluation();
    sessionStorage.setItem("patient-web-session", sid); await refresh(); connect();
  } catch (error) { showError(error); } finally { submitting = false; controls(); }
};
el("question").addEventListener("compositionstart", () => { composing = true; });
el("question").addEventListener("compositionend", () => { composing = false; compositionEnded = performance.now(); });
el("question").addEventListener("keydown", event => {
  if (event.key === "Enter" && (composing || event.isComposing || event.keyCode === 229)) event.preventDefault();
});
el("backend-choice").onchange = async () => {
  const backend = el("backend-choice").value;
  submitting = true; controls(); showError(null);
  try { await api("/ui/v1/backend", {request_id:id(), backend}); await poll(); }
  catch (error) { showError(error); el("backend-choice").value = service.backend.configured; }
  finally { submitting = false; controls(); }
};
el("question-form").onsubmit = async (event) => {
  event.preventDefault(); if (!sid || submitting || current?.active_request_id || composing || event.isComposing || performance.now()-compositionEnded < 40) return;
  const text = el("question").value; if (!text.trim()) return;
  // A transport failure reuses the same ID; no automatic duplicate generation.
  if (!pending || pending.text !== text) pending = {request_id:id(), text};
  timingStart(sid, pending.request_id);
  submitting = true; controls(); showError(null);
  el("state").textContent = "已接收，正在处理…";
  try {
    await api(`/ui/v1/sessions/${sid}/turns`, pending);
    pending = null; el("question").value = ""; scheduleRefresh();
  } catch (error) { showError(error); } finally { submitting = false; controls(); }
};
el("cancel").onclick = async () => {
  if (!current?.active_request_id) return;
  if (!cancelCommand || cancelCommand.target_request_id !== current.active_request_id)
    cancelCommand = {request_id:id(), target_request_id:current.active_request_id};
  try { await api(`/ui/v1/sessions/${sid}/cancel`, cancelCommand); await refresh(); }
  catch (error) { showError(error); }
};
el("finish").onclick = async () => {
  submitting = true; controls(); showError(null);
  try {
    await api(`/ui/v1/sessions/${sid}/finish`, {request_id:id()}); await refresh();
    el("evaluation-title").focus({preventScroll:true});
  }
  catch (error) { showError(error); } finally { submitting = false; controls(); }
};
el("new-session").onclick = () => { if (!el("start").disabled) el("start").click(); };
for (const view of reviewViews) {
  el(`tab-${view}`).onclick = () => setEvaluationView(view);
  el(`tab-${view}`).onkeydown = (event) => {
    if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
    event.preventDefault();
    let next = reviewViews.indexOf(view);
    if (event.key === "Home") next = 0;
    else if (event.key === "End") next = reviewViews.length-1;
    else next = (next + (event.key === "ArrowRight" ? 1 : -1) + reviewViews.length) % reviewViews.length;
    setEvaluationView(reviewViews[next], true);
  };
}
poll(); setInterval(poll, 2000);

