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

  // Une journée : la liste est doublée pour défiler sans fin ; un clic ouvre la fenêtre de détail.
  const track = document.querySelector(".reeltrack");
  const dialog = document.getElementById("reel-dialog");
  if (track && dialog) {
    if (!still) {
      for (const card of [...track.children]) {
        const copy = card.cloneNode(true);
        copy.setAttribute("aria-hidden", "true");
        copy.querySelector("button").tabIndex = -1;
        track.append(copy);
      }
    }
    track.addEventListener("click", (event) => {
      const card = event.target.closest("[data-reel]");
      if (!card) return;
      const body = dialog.querySelector(".reelbody");
      const img = card.querySelector("img").cloneNode(true);
      img.removeAttribute("loading");
      img.removeAttribute("srcset");
      img.removeAttribute("sizes");
      img.removeAttribute("width");
      img.removeAttribute("height");
      const text = document.createElement("div");
      text.className = "rt";
      text.innerHTML = card.querySelector(".t").outerHTML + card.querySelector("h3").outerHTML +
        card.querySelector("p").outerHTML;
      text.querySelector("p").style.cssText = "display:block;-webkit-line-clamp:unset";
      body.replaceChildren(img, text);
      dialog.showModal();
    });
    dialog.addEventListener("click", (event) => {
      if (event.target === dialog) dialog.close();
    });
  }
  // Témoignages — la rangée avance seule toutes les 6 s (arrêtée au survol, au focus ou si la
  // personne l'a déplacée), un clic ouvre le texte entier dans une fenêtre.
  const voices = document.querySelector("[data-voices]");
  if (voices) {
    for (const card of voices.querySelectorAll("[data-voice]")) {
      card.addEventListener("click", () =>
        document.getElementById(`voice-${card.dataset.voice}`)?.showModal(),
      );
    }
    for (const dialog of document.querySelectorAll(".vdialog")) {
      dialog.addEventListener("click", (event) => event.target === dialog && dialog.close());
    }
    if (!still) {
      let paused = false;
      for (const event of ["mouseenter", "focusin", "touchstart"]) {
        voices.addEventListener(event, () => (paused = true), { passive: true });
      }
      for (const event of ["mouseleave", "focusout"]) {
        voices.addEventListener(event, () => (paused = false));
      }
      setInterval(() => {
        if (paused || document.hidden) return;
        const step = voices.querySelector("li").offsetWidth + 24;
        const end = voices.scrollLeft + voices.clientWidth >= voices.scrollWidth - 4;
        voices.scrollTo({ left: end ? 0 : voices.scrollLeft + step, behavior: "smooth" });
      }, 6000);
    }
  }

  // Bulle de contact : le message part sans recharger la page ; sans ce script, la bulle reste
  // cachée et le lien WhatsApp du pied de page suffit.
  const chat = document.getElementById("chat");
  if (chat) {
    chat.hidden = false;
    const box = chat.querySelector(".chat-box");
    const opener = chat.querySelector(".chat-open");
    const form = box.querySelector("form");
    const toggle = (open) => {
      box.hidden = !open;
      opener.setAttribute("aria-expanded", String(open));
      if (open) form.elements.name.focus();
    };
    opener.addEventListener("click", () => toggle(box.hidden));
    box.querySelector("[data-chat-close]").addEventListener("click", () => {
      toggle(false);
      opener.focus();
    });
    chat.addEventListener("keydown", (event) => {
      if (event.key === "Escape" && !box.hidden) toggle(false);
    });
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const [invalid, failed] = [".formerr[data-invalid]", ".formerr[data-failed]"].map((q) =>
        form.querySelector(q),
      );
      invalid.hidden = failed.hidden = true;
      if (!form.checkValidity()) {
        invalid.hidden = false;
        return;
      }
      try {
        const response = await fetch(chat.dataset.action, {
          method: "POST",
          body: new FormData(form),
        });
        if (response.status === 400) invalid.hidden = false;
        else if (!response.ok) failed.hidden = false;
        else {
          form.hidden = true;
          box.querySelector(".chat-done").hidden = false;
        }
      } catch {
        failed.hidden = false;
      }
    });
  }
})();
