/* Progressive enhancement only. Everything here is an upgrade on behaviour that
   already works without it: the composer is a real form POST and the source
   panels are <details> elements.

   What it adds, and why each one earns its bytes on a 3G connection:
   - a visible working state, because a blank wait on a slow network looks broken
   - a one-tap reason on a down-vote, without a second page load
   - a visible, honest failure when the request times out
   - swapping between log in and sign up without fetching the page again */

(function () {
  "use strict";

  var TIMEOUT_MS = 20000;

  // --- composer: show that something is happening, and say so if it fails ---
  var form = document.getElementById("ask-form");
  var working = document.getElementById("working");

  if (form && working) {
    var textarea = form.querySelector("textarea");

    // Grow with the question rather than scrolling a two-line box.
    if (textarea) {
      var grow = function () {
        textarea.style.height = "auto";
        textarea.style.height = Math.min(textarea.scrollHeight, 140) + "px";
      };
      textarea.addEventListener("input", grow);
    }

    form.addEventListener("submit", function () {
      working.classList.add("on");
      var started = Date.now();
      // The browser owns the navigation; this only reports on it.
      window.setTimeout(function () {
        if (document.visibilityState === "visible" && Date.now() - started >= TIMEOUT_MS) {
          working.textContent =
            "This is taking longer than it should. Your connection may have " +
            "dropped. Nothing was lost — press Ask again when you have signal.";
        }
      }, TIMEOUT_MS);
    });
  }

  // --- down-vote: reveal the reasons in place ---
  var noButton = document.getElementById("no-button");
  var reasons = document.getElementById("reasons");
  var reasonField = document.getElementById("reason-field");
  var feedbackForm = document.getElementById("feedback-form");

  if (noButton && reasons && reasonField && feedbackForm) {
    noButton.addEventListener("click", function (event) {
      if (reasons.classList.contains("open")) return; // second press submits
      event.preventDefault();
      reasons.classList.add("open");
      var first = reasons.querySelector("button");
      if (first) first.focus();
    });

    reasons.addEventListener("click", function (event) {
      var button = event.target.closest("button[data-reason]");
      if (button) reasonField.value = button.getAttribute("data-reason");
    });

    // Submit in the background so the answer stays on screen. Falls back to a
    // normal POST if fetch is unavailable or the request fails.
    feedbackForm.addEventListener("submit", function (event) {
      if (!window.fetch) return;
      var submitter = event.submitter;
      if (!submitter || !submitter.value) return;

      event.preventDefault();
      var data = new FormData(feedbackForm);
      data.set("vote", submitter.value);

      fetch("/feedback", { method: "POST", body: data, headers: { Accept: "application/json" } })
        .then(function (r) {
          if (!r.ok) throw new Error("bad status");
          feedbackForm.innerHTML =
            '<span class="voted">Thank you. That is recorded against this answer.</span>';
        })
        .catch(function () {
          feedbackForm.submit();
        });
    });
  }

  // --- auth: swap between log in and sign up in place ---
  // Both panels are already in the page, so switching between them is a class
  // change rather than a whole round trip on a metered connection. With
  // JavaScript off the links are ordinary hrefs and the server renders the
  // right panel, so this can only ever save a load, never cause one.
  var auth = document.getElementById("auth");

  if (auth) {
    var reduced = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)");

    auth.addEventListener("click", function (event) {
      var link = event.target.closest("a.auth-switch-link");
      if (!link) return;

      var name = link.getAttribute("data-panel");
      var target = document.getElementById("panel-" + name);
      var current = auth.querySelector(".auth-panel:not([hidden])");
      if (!target || !current || target === current) return;

      event.preventDefault();

      // Sign up sits to the right of log in, so each panel arrives from the
      // side it would have come from if the two were laid out side by side.
      var moves = !(reduced && reduced.matches);
      if (moves) {
        target.style.setProperty("--from", name === "signup" ? "1rem" : "-1rem");
        target.classList.add("entering");
      }

      current.hidden = true;
      target.hidden = false;
      auth.setAttribute("data-panel", name);

      if (moves) {
        // Force a layout read so the offset start state is real before the
        // class comes off; without it there is nothing to transition from.
        void target.offsetWidth;
        window.requestAnimationFrame(function () {
          target.classList.remove("entering");
        });
      }

      // The panel that just appeared owns the keyboard now.
      var field = target.querySelector("input:not([type=hidden])");
      if (field) field.focus();

      // Keep the address bar honest, so a reload or a share lands on the panel
      // that is actually on screen.
      if (window.history && window.history.replaceState) {
        window.history.replaceState(null, "", link.href);
      }
    });
  }

  // --- the opening cover ---
  // A two-line script in the head put `data-loading` on <html> before the
  // first paint; this takes it off once the page is actually ready. The
  // timeout is the important half: if a font or an image stalls on a bad
  // connection, the cover must still come off. A flourish that can trap
  // someone on a blank screen is not a flourish, it is an outage.
  var OPENING_MAX_MS = 1400;
  var OPENING_MIN_MS = 420;

  function uncover() {
    var root = document.documentElement;
    if (!root.hasAttribute("data-loading")) return;
    var cover = document.querySelector(".opening");
    root.removeAttribute("data-loading");
    if (!cover) return;
    cover.classList.add("is-done");
    // Removed rather than left lying on top of the page: it is fixed and
    // full-screen, and a stray one would swallow every click.
    window.setTimeout(function () {
      if (cover.parentNode) cover.parentNode.removeChild(cover);
    }, 700);
  }

  if (document.documentElement.hasAttribute("data-loading")) {
    var opened = Date.now();
    var lift = function () {
      // Hold it just long enough that the dye line is seen to draw, rather
      // than flashing on a fast connection.
      var waited = Date.now() - opened;
      window.setTimeout(uncover, Math.max(0, OPENING_MIN_MS - waited));
    };
    if (document.readyState === "complete") lift();
    else window.addEventListener("load", lift);
    window.setTimeout(uncover, OPENING_MAX_MS);
  }

  // --- reveal on scroll ---
  // Content settles in as it arrives. Anything already on screen is revealed
  // immediately, so the first thing a student sees is never waiting on a
  // scroll that has not happened. Without IntersectionObserver the CSS
  // leaves everything visible, so old browsers simply get no animation.
  var revealables = document.querySelectorAll(".reveal");

  if (revealables.length && window.IntersectionObserver) {
    var watcher = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (entry) {
          if (!entry.isIntersecting) return;
          entry.target.classList.add("is-in");
          watcher.unobserve(entry.target);
        });
      },
      { rootMargin: "0px 0px -8% 0px", threshold: 0.08 }
    );
    Array.prototype.forEach.call(revealables, function (el) {
      watcher.observe(el);
    });
  } else {
    Array.prototype.forEach.call(revealables, function (el) {
      el.classList.add("is-in");
    });
  }

  // --- counting the figures up ---
  // One moment, once, when they first come into view. Tabular figures in the
  // CSS keep the width steady so the sentence around them does not reflow
  // while the number climbs. The markup already contains the final value, so
  // with JavaScript off the sentence simply reads correctly.
  var counters = document.querySelectorAll("[data-count-to]");
  var stillCount =
    window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)");

  if (counters.length && window.IntersectionObserver && !(stillCount && stillCount.matches)) {
    var countUp = function (el) {
      var target = parseInt(el.getAttribute("data-count-to"), 10);
      if (!target) return;
      var started = null;
      var RUN_MS = 900;
      var step = function (now) {
        if (started === null) started = now;
        var through = Math.min(1, (now - started) / RUN_MS);
        // Ease out, so it arrives rather than stopping dead.
        var eased = 1 - Math.pow(1 - through, 3);
        el.textContent = String(Math.round(target * eased));
        if (through < 1) window.requestAnimationFrame(step);
        else el.textContent = String(target);
      };
      window.requestAnimationFrame(step);
    };

    var countWatcher = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (entry) {
          if (!entry.isIntersecting) return;
          countUp(entry.target);
          countWatcher.unobserve(entry.target);
        });
      },
      { threshold: 0.6 }
    );
    Array.prototype.forEach.call(counters, function (el) {
      countWatcher.observe(el);
    });
  }

  // --- the hero deck ---
  // Four worked answers, one face up. Every card stays in the same grid cell
  // whether it is showing or not, so the window is sized by the tallest and
  // turning the deck over cannot change the height of the page. Cards used to
  // be hidden with the `hidden` attribute, which is display:none, which drops
  // them out of the grid -- and the whole page moved on every rotation.
  //
  // It auto-advances but stops the moment somebody shows they are reading:
  // hover, focus, a tab in the background, or a tap on a dot.
  var deck = document.querySelector("[data-deck]");

  if (deck) {
    var cards = deck.querySelectorAll(".deck-card");
    var controls = deck.querySelector("[data-deck-controls]");
    var dots = deck.querySelectorAll(".deck-dot");
    var index = 0;
    var timer = null;
    var held = false;
    var DEAL_EVERY_MS = 6000;
    var stillDeck =
      window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)");

    if (cards.length > 1 && controls) {
      // Tells the stylesheet the deck is live, which is what switches the
      // inactive cards from display:none to invisible-but-measured.
      document.documentElement.setAttribute("data-deck-ready", "");
      controls.hidden = false;

      // A card nobody can see must not be reachable by tab or read aloud.
      var setInert = function (card, out) {
        if (out) {
          card.setAttribute("aria-hidden", "true");
          card.setAttribute("inert", "");
        } else {
          card.removeAttribute("aria-hidden");
          card.removeAttribute("inert");
        }
      };

      Array.prototype.forEach.call(cards, function (card, i) {
        setInert(card, i !== 0);
      });

      var show = function (next) {
        if (next === index) return;
        var leaving = cards[index];
        var arriving = cards[next];

        var moves = !(stillDeck && stillDeck.matches);

        leaving.classList.remove("is-current");
        setInert(leaving, true);

        arriving.classList.remove("is-leaving");
        arriving.classList.add("is-current");
        setInert(arriving, false);

        if (moves) {
          // The outgoing card is held on screen at zero opacity while it
          // travels. Under reduced motion there is no travel, so it is not
          // held at all -- otherwise an invisible card would sit over the
          // new one for half a second for no reason anybody asked for.
          leaving.classList.add("is-leaving");
          window.setTimeout(function () {
            leaving.classList.remove("is-leaving");
          }, 640);
        }

        Array.prototype.forEach.call(dots, function (dot, i) {
          dot.classList.toggle("is-current", i === next);
          dot.setAttribute("aria-current", i === next ? "true" : "false");
        });

        index = next;
      };

      var advance = function () {
        show((index + 1) % cards.length);
      };

      var start = function () {
        if (timer || held) return;
        if (stillDeck && stillDeck.matches) return;
        timer = window.setInterval(advance, DEAL_EVERY_MS);
      };

      var stop = function () {
        if (timer) window.clearInterval(timer);
        timer = null;
      };

      Array.prototype.forEach.call(dots, function (dot, i) {
        dot.addEventListener("click", function () {
          // A deliberate choice outranks the rotation: once somebody picks a
          // card, it stays picked.
          held = true;
          stop();
          show(i);
        });
      });

      deck.addEventListener("mouseenter", stop);
      deck.addEventListener("mouseleave", start);
      deck.addEventListener("focusin", function () {
        held = true;
        stop();
      });

      // Nothing should be dealing to an empty room.
      document.addEventListener("visibilitychange", function () {
        if (document.hidden) stop();
        else start();
      });

      start();
    }
  }

})();
