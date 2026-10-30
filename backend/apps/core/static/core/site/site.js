// Site public (WEB.1b) : quelques animations qui servent ; sans ce script, tout reste lisible.
(() => {
  const still = matchMedia("(prefers-reduced-motion: reduce)").matches;

  // Animation 1 — montrer le produit : les autres captures du héros se chargent après la page
  // (premier écran léger), puis s'enchaînent.
  if (!still) {
    addEventListener("load", () => {
      for (const box of document.querySelectorAll(".screens[data-cycle]")) {
        const later = [...box.querySelectorAll("img[data-src]")].map(
          (img) =>
            new Promise((done) => {
              img.onload = img.onerror = done;
              img.src = img.dataset.src;
            }),
        );
        Promise.all(later).then(() => box.classList.add("cycle"));
      }
    });
  }

  // Animation 6 — attirer l'œil sur des faits : les chiffres montent quand la bande arrive à
  // l'écran ; le vrai nombre est dans la page.
  const numbers = document.querySelectorAll("[data-count]");
  if (numbers.length && !still && "IntersectionObserver" in window) {
    const format = new Intl.NumberFormat(document.documentElement.lang);
    const seen = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (!entry.isIntersecting) continue;
          seen.unobserve(entry.target);
          const el = entry.target;
          const end = Number(el.dataset.count);
          const text = el.textContent;
          const start = performance.now();
          const step = (now) => {
            const t = Math.min((now - start) / 1200, 1);
            el.textContent = t < 1 ? format.format(Math.round(end * (1 - (1 - t) ** 3))) : text;
            if (t < 1) requestAnimationFrame(step);
          };
          requestAnimationFrame(step);
        }
      },
      { threshold: 0.4 },
    );
    numbers.forEach((el) => seen.observe(el));
  }

  // Animation 8 — montrer le calcul du bulletin : les points, le total, la place puis le cachet
  // apparaissent quand il arrive à l'écran, et la séquence recommence après une pause.
  const sheet = document.querySelector(".bul");
  if (sheet && !still && "IntersectionObserver" in window) {
    sheet.classList.add("anim");
    let timer = 0;
    const play = () => {
      sheet.classList.remove("play");
      void sheet.offsetWidth; // relance les animations CSS
      sheet.classList.add("play");
      timer = setTimeout(play, 11000);
    };
    new IntersectionObserver(
      ([entry]) => {
        clearTimeout(timer);
        if (entry.isIntersecting) play();
      },
      { threshold: 0.35 },
    ).observe(sheet);
  }

  // Animation 7 — rassurer avant de partir : « Vous allez ouvrir… » suit chaque lettre tapée ;
  // le dernier code est proposé au retour (cet appareil seulement).
  const finder = document.querySelector("form[data-finder]");
  if (finder) {
    const input = finder.elements.code;
    const line = finder.querySelector("[data-goto]");
    const key = "site.school-code";
    try {
      if (!input.value) input.value = localStorage.getItem(key) || "";
    } catch {}
    const show = () => {
      const code = input.value.trim().toLowerCase();
      line.hidden = !/^[a-z0-9-]+$/.test(code);
      line.querySelector("b").textContent = finder.dataset.finder.replace("{code}", code);
    };
    input.addEventListener("input", show);
    finder.addEventListener("submit", () => {
      try {
        localStorage.setItem(key, input.value.trim().toLowerCase());
      } catch {}
    });
    show();
  }
})();
