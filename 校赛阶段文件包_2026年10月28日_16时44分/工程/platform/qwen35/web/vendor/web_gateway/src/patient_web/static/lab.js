"use strict";
const labEl = (id) => document.getElementById(id);
async function labCall(body){
  const response = await fetch("/ui/v1/demo-lab", body === undefined ? {} : {
    method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(body)
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error?.message || "联调服务不可用");
  return data;
}
function showLab(data){
  const active = data.active;
  const last = data.history.at(-1);
  const lines = [`待执行：${data.scenarios[data.pending.scenario]}`];
  if (active) lines.push(`进行中：${data.scenarios[active.scenario]}；回答模块${active.adapter_invoked ? "已进入" : "未进入"}`);
  if (last) lines.push(`上一轮：${data.scenarios[last.scenario]}；回答模块${last.adapter_invoked ? "已进入" : "未进入"}；${last.outcome === "CHECKED_RESULT_RETURNED" ? "已返回检查通过的结果" : "没有返回可发布结果"}`);
  lines.push("实际发布及取消结果请以问诊页面为准。");
  labEl("diagnostics").textContent = lines.join("\n");
  labEl("arm").disabled = !!active;
}
labEl("scenario-form").onsubmit = async (event) => {
  event.preventDefault(); labEl("arm").disabled = true;
  try {
    showLab(await labCall({scenario:labEl("scenario").value, delay_s:Number(labEl("delay").value)}));
    labEl("message").textContent = "已应用。请到问诊页面提交下一次提问。";
  } catch (error) { labEl("message").textContent = error.message; labEl("arm").disabled = false; }
};
async function pollLab(){
  try { showLab(await labCall()); }
  catch (error) { labEl("message").textContent = error.message; labEl("arm").disabled = true; }
}
pollLab(); setInterval(pollLab, 1000);
