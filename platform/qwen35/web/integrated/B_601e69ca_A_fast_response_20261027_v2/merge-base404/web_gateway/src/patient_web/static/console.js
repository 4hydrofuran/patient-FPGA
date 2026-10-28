"use strict";
const el = (id) => document.getElementById(id);
let sid = null, stream = null, current = null, service = null, submitting = false;
let pending = null, cancelCommand = null;
let eventLog = [];
let evaluationCache = null, evaluationView = "summary";
const reviewViews = ["summary", "topics", "review", "transcript"];
const reviewPanels = {summary:"chief-summary", topics:"topic-details", review:"review-details", transcript:"transcript-panel"};
const labels = {STARTING:"模型加载中", READY:"等待提问", PROCESSING:"正在处理",
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
  el("cases").disabled = !ready || open || submitting;
  el("question").disabled = !ready || !open || busy || submitting;
  el("send").disabled = !ready || !open || busy || submitting;
  el("cancel").hidden = service?.capabilities?.cancel_turn === false;
  el("cancel").disabled = service?.capabilities?.cancel_turn === false || !busy || current.phase === "CANCELLING";
  el("finish").disabled = !open || busy || submitting;
  el("new-session").disabled = !ready || open || busy || submitting;
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
  const caseOption = Array.from(el("cases").options).find(option => option.value === result.case_id);
  const caseTitle = caseOption?.textContent.replace("（待审核）", "") || result.case_id;
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
  current = snapshot;
  if (el("cases").options.length) el("cases").value = snapshot.case_id;
  el("state").textContent = labels[snapshot.phase] || snapshot.phase;
  el("case-label").textContent = snapshot.closed ? "下次练习" : "病例";
  el("stage-label").textContent = snapshot.closed ? "主任评价" : "文字问诊";
  el("consultation-section").hidden = snapshot.closed;
  document.body.classList.toggle("evaluation-mode", snapshot.closed);
  document.body.classList.toggle("consultation-active", !snapshot.closed);
  el("score-section").hidden = !snapshot.closed;
  el("turns").replaceChildren();
  for (const turn of snapshot.turns) {
    const p = document.createElement("p");
    const question = document.createElement("strong"); question.textContent = `医生：${turn.question}`;
    p.append(question, document.createElement("br"));
    const answer = document.createElement("span");
    answer.textContent = turn.answer ? `患者：${turn.answer}`
      : turn.status === "CANCELLED" ? "本轮已取消，未发布患者回答。"
      : turn.status === "FAILED" ? turn.error?.message || "本轮失败。" : "正在等待回答…";
    p.append(answer); el("turns").append(p);
  }
  transcript.scrollTop = followLatest || newQuestion ? transcript.scrollHeight : previousScroll;
  controls();
}
async function refresh(){
  if (!sid) return;
  const target = sid;
  const snapshot = await api(`/ui/v1/sessions/${target}`);
  if (target !== sid) return;
  if (current?.instance_id === snapshot.instance_id && snapshot.cursor < current.cursor) return;
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
function connect(){
  if (stream) stream.close();
  stream = new EventSource(`/ui/v1/events?session_id=${encodeURIComponent(sid)}`);
  const names = ["session.snapshot","session.created","turn.accepted","response.preparing",
    "generation.started","validation.started","answer.ready","turn.completed","cancel.pending",
    "turn.cancelled","turn.failed","session.finished","evaluation.ready","service.ready","service.failed"];
  for (const name of names) stream.addEventListener(name, (message) => {
    const data = JSON.parse(message.data);
    if (data.session_id && data.session_id !== sid) return;
    if (current && data.epoch < current.epoch) return;
    eventLog.push(`${data.seq}  ${data.event}`); eventLog = eventLog.slice(-100);
    el("events").textContent = eventLog.join("\n");
    if (data.event === "session.snapshot") render(data.data);
    refresh().catch(showError);
  });
  stream.onerror = () => { el("state").textContent = "事件连接中断，正在恢复…"; };
}
async function poll(){
  try {
    service = await api("/ui/v1/status");
    if (current && current.instance_id !== service.instance_id) {
      if (stream) stream.close();
      sid = null; current = null; pending = null; cancelCommand = null;
      sessionStorage.removeItem("patient-web-session");
      el("turns").replaceChildren(); clearEvaluation();
      el("consultation-section").hidden = false; el("stage-label").textContent = "文字问诊";
      el("case-label").textContent = "病例";
      document.body.classList.remove("evaluation-mode");
      document.body.classList.remove("consultation-active");
      showError(new Error("服务已重新启动，上一实例的内存会话已结束。"));
    }
    el("backend").textContent = service.backend.configured === "demo"
      ? service.demo_lab ? "规则演示 · 联调场景已启用 · 未接入模型" : "规则演示 · 未接入模型"
      : service.ready ? service.backend.execution_kind === "FPGA_REAL" ? "板端模型已连接 · PL 参与计算" : "CPU 模型已连接"
      : service.failure?.message || "真实模型正在加载…";
    if (service.ready && !el("cases").options.length) {
      for (const item of (await api("/ui/v1/cases")).cases) {
        const option = document.createElement("option"); option.value = item.case_id;
        option.textContent = `${item.title}（待审核）`; el("cases").append(option);
      }
    }
    const stored = sessionStorage.getItem("patient-web-session");
    if (!sid && stored && service.current_session_id === stored) { sid = stored; await refresh(); connect(); }
    if (!sid && service.current_session_id) { sid = service.current_session_id; await refresh(); connect(); }
    if (sid && current?.closed && !evaluationCache) await refresh();
    if (!sid) el("state").textContent = labels[service.phase] || service.phase;
    controls();
  } catch (error) { showError(error); }
}
el("start").onclick = async () => {
  submitting = true; controls(); showError(null);
  try {
    const result = await api("/ui/v1/sessions", {request_id:id(), case_id:el("cases").value});
    sid = result.session_id; pending = null; cancelCommand = null; eventLog = []; clearEvaluation();
    sessionStorage.setItem("patient-web-session", sid); await refresh(); connect();
  } catch (error) { showError(error); } finally { submitting = false; controls(); }
};
el("question-form").onsubmit = async (event) => {
  event.preventDefault(); if (!sid || submitting) return;
  const text = el("question").value; if (!text.trim()) return;
  // A transport failure reuses the same ID; no automatic duplicate generation.
  if (!pending || pending.text !== text) pending = {request_id:id(), text};
  submitting = true; controls(); showError(null);
  try {
    await api(`/ui/v1/sessions/${sid}/turns`, pending);
    pending = null; el("question").value = ""; await refresh();
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

