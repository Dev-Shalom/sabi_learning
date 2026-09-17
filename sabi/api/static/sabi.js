/* Progressive enhancement only. Everything here is an upgrade on behaviour that
   already works without it: the composer is a real form POST and the source
   panels are <details> elements.

   What it adds, and why each one earns its bytes on a 3G connection:
   - a visible working state, because a blank wait on a slow network looks broken
   - a one-tap reason on a down-vote, without a second page load
   - a visible, honest failure when the request times out */

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
})();
