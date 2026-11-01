// AI coach chat panel, shared by the photo and video result pages.
// Expects in the page: #chat, #suggest, #chat-form, #q, #send.

function initCoach(analysisId, messages, greetingText, questions) {
  const $ = id => document.getElementById(id);


  function addMsg(role, text, animate = true) {
    const d = document.createElement("div");
    d.className = `msg ${role}`;
    if (!animate) d.style.animation = "none";
    d.innerHTML = role === "coach" ? coachHtml(text) : esc(text);
    $("chat").append(d);
    $("chat").scrollTop = $("chat").scrollHeight;
  }

  function suggestions() {
    $("suggest").innerHTML = questions.map(q => `<button type="button">${esc(q)}</button>`).join("");
    $("suggest").querySelectorAll("button").forEach(b => (b.onclick = () => ask(b.textContent)));
  }

  async function ask(text) {
    text = text.trim();
    if (!text) return;
    addMsg("user", text);
    $("q").value = "";
    $("send").disabled = true;
    $("suggest").innerHTML = "";
    const t = document.createElement("div");
    t.className = "msg coach typing";
    t.innerHTML = "<i></i><i></i><i></i>";
    $("chat").append(t);
    $("chat").scrollTop = $("chat").scrollHeight;
    try {
      const r = await api(`/api/coach/${analysisId}`, { method: "POST", body: { text } });
      t.remove();
      addMsg("coach", r.reply);
    } catch (err) {
      t.remove();
      addMsg("coach", err.message);
    } finally {
      $("send").disabled = false;
      suggestions();
    }
  }

  $("send").innerHTML = icon("arrow");
  (messages || []).forEach(m => addMsg(m.role, m.text, false));
  if (!(messages || []).length) addMsg("coach", greetingText, false);
  suggestions();
  $("chat-form").onsubmit = e => { e.preventDefault(); ask($("q").value); };
}
