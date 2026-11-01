// Extra motion for the landing page: intro, parallax, rolling ball on the steps,
// confetti on sign-up buttons, scoreboard bulbs. Everything is skipped for reduced motion.
(function () {
  const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const BALL = '<svg viewBox="0 0 64 64" aria-hidden="true"><circle cx="32" cy="32" r="30" fill="url(#ballG)"/><g class="seam-g"><path d="M28.6 2.4Q22.6 32 28.6 61.6" fill="none" stroke="#f3e9d2" stroke-width="1.7"/><path d="M35.4 2.4Q29.4 32 35.4 61.6" fill="none" stroke="#f3e9d2" stroke-width="1.7"/><path d="M24.9 6Q18.9 32 24.9 58" fill="none" stroke="#f3e9d2" stroke-width="1.5" stroke-linecap="round" stroke-dasharray="1.4 2.8"/><path d="M39.1 6Q33.1 32 39.1 58" fill="none" stroke="#f3e9d2" stroke-width="1.5" stroke-linecap="round" stroke-dasharray="1.4 2.8"/></g><circle cx="32" cy="32" r="30" fill="url(#ballS)"/><ellipse cx="21" cy="17" rx="9" ry="5" fill="#fff" opacity=".28" transform="rotate(-35 21 17)"/></svg>';

  // ------------------------------------------------------------ 1. intro on every page load (click to skip)
  if (!reduce) {
    const word = (t, cls = "") => `<span class="iw ${cls}">${[...t].map((c, i) => `<b style="animation-delay:${1.05 + i * 0.045}s">${c}</b>`).join("")}</span>`;
    const intro = document.createElement("div");
    intro.className = "intro";
    intro.innerHTML = `
      <div class="half top"></div><div class="half bottom"></div>
      <div class="stage">
        <div class="trail"></div>
        <div class="intro-ball">${BALL}</div>
        <div class="intro-shadow"></div>
        <i class="shock s1"></i><i class="shock s2"></i>
        <div class="intro-word">${word("SMART")}${word("CRICKET", "r")}</div>
        <div class="intro-tag">AI BATTING COACH</div>
      </div>`;
    document.body.append(intro);
    document.documentElement.classList.add("intro-on");
    let done = false;
    const finish = () => {
      if (done) return;
      done = true;
      intro.classList.add("out");
      document.documentElement.classList.remove("intro-on");
      setTimeout(() => intro.remove(), 900);
    };
    setTimeout(finish, 2050);
    intro.addEventListener("click", finish);
  }

  if (reduce) return;

  // ------------------------------------------------------------ 3. parallax + floating outlines
  const heroText = document.querySelector(".hero-grid > div:first-child");
  const heroScene = document.querySelector(".scene-wrap");
  document.querySelectorAll("#features, #faq").forEach((sec, k) => {
    const deco = document.createElement("div");
    deco.className = "deco";
    deco.innerHTML = k === 0
      ? `<i class="o-ball" data-speed=".18" style="left:-60px;top:12%"></i><i class="o-stumps" data-speed="-.12" style="right:-46px;top:62%"></i>`
      : `<i class="o-ball" data-speed="-.15" style="right:-50px;top:18%"></i><i class="o-bat" data-speed=".12" style="left:3%;top:60%"></i>`;
    sec.prepend(deco);
  });
  const movers = [...document.querySelectorAll(".deco i")];
  let ticking = false;
  addEventListener("scroll", () => {
    if (ticking) return;
    ticking = true;
    requestAnimationFrame(() => {
      const y = scrollY;
      if (y < innerHeight * 1.2) {
        heroText.style.transform = `translateY(${y * 0.18}px)`;
        heroText.style.opacity = String(Math.max(0, 1 - y / (innerHeight * 0.9)));
        heroScene.style.translate = `0 ${y * -0.08}px`;
      }
      movers.forEach(m => {
        const r = m.parentElement.parentElement.getBoundingClientRect();
        m.style.translate = `0 ${(r.top + r.height / 2 - innerHeight / 2) * +m.dataset.speed}px`;
      });
      ticking = false;
    });
  }, { passive: true });

  // ------------------------------------------------------------ 4. rolling ball on the steps rail
  const steps = document.getElementById("steps");
  if (steps) {
    const rb = document.createElement("span");
    rb.className = "rail-ball";
    rb.innerHTML = BALL;
    steps.append(rb);
    new IntersectionObserver((es, o) => es.forEach(e => {
      if (!e.isIntersecting) return;
      steps.classList.add("play");
      const nums = steps.querySelectorAll(".step");
      nums.forEach((s, i) => setTimeout(() => s.classList.add("lit"), 500 + i * 650));
      o.disconnect();
    }), { threshold: 0.4 }).observe(steps);
  }

  // ------------------------------------------------------------ 5. confetti on sign-up buttons
  function burst(x, y) {
    const colors = ["#c8102e", "#f3e9d2", "#0f5c3a", "#ffffff"];
    for (let i = 0; i < 26; i++) {
      const p = document.createElement("i");
      p.className = "confetti";
      const a = Math.random() * Math.PI * 2, d = 60 + Math.random() * 110;
      p.style.cssText = `left:${x}px;top:${y}px;background:${colors[i % 4]};--dx:${Math.cos(a) * d}px;--dy:${Math.sin(a) * d - 40}px;--r:${Math.random() * 720 - 360}deg`;
      document.body.append(p);
      setTimeout(() => p.remove(), 900);
    }
  }
  document.querySelectorAll('a[href*="mode=register"]').forEach(a => a.addEventListener("click", e => {
    if (e.metaKey || e.ctrlKey) return;
    e.preventDefault();
    burst(e.clientX, e.clientY);
    setTimeout(() => (location.href = a.href), 420);
  }));

  // ------------------------------------------------------------ 6. curtain wipe for the live demo
  const demo = document.getElementById("demo");
  if (demo) {
    const cur = document.createElement("div");
    cur.className = "curtain";
    cur.innerHTML = "<i></i><i></i>";
    demo.append(cur);
    new IntersectionObserver((es, o) => es.forEach(e => {
      if (e.isIntersecting) { cur.classList.add("go"); setTimeout(() => cur.remove(), 1400); o.disconnect(); }
    }), { threshold: 0.25 }).observe(demo);
  }
  // 7. feature icon bounce is CSS (.feature.rv.in .ic)
  // ------------------------------------------------------------ 8. scoreboard bulbs
  const board = document.querySelector(".stats");
  if (board) {
    const lights = document.createElement("div");
    lights.className = "bulbs";
    lights.innerHTML = Array.from({ length: 28 }, (_, i) => `<i style="animation-delay:${(i % 4) * 0.25}s"></i>`).join("");
    board.append(lights);  // appended so the stat colours (nth-child) stay the same
  }
})();
