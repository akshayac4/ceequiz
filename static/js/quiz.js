(function () {
  "use strict";

  function getCookie(name) {
    const match = document.cookie.match(new RegExp("(^| )" + name + "=([^;]+)"));
    return match ? decodeURIComponent(match[2]) : null;
  }

  function postForm(url, data) {
    const body = new URLSearchParams(data || {});
    return fetch(url, {
      method: "POST",
      headers: {
        "X-CSRFToken": getCookie("csrftoken"),
        "Content-Type": "application/x-www-form-urlencoded",
      },
      body: body,
    });
  }

  function confirmText(lang, unanswered) {
    if (lang === "en") {
      return unanswered > 0
        ? "You have " + unanswered + " unanswered question(s). Submit anyway?"
        : "Submit your test?";
    }
    return unanswered > 0
      ? unanswered + " પ્રશ્નો હજુ જવાબ વિના છે. તેમ છતાં સબમિટ કરવું?"
      : "તમારી કસોટી સબમિટ કરવી છે?";
  }

  function startTimer(el, submitUrl) {
    const remaining = el.getAttribute("data-remaining");
    if (remaining === null || remaining === "") return;
    let seconds = parseInt(remaining, 10);
    const lang = document.documentElement.lang === "en" ? "en" : "gu";
    let warned = false;

    function render() {
      const m = Math.floor(seconds / 60);
      const s = seconds % 60;
      el.textContent = (m < 10 ? "0" : "") + m + ":" + (s < 10 ? "0" : "") + s;
    }

    render();
    const interval = setInterval(function () {
      seconds -= 1;
      if (seconds <= 60 && !warned) {
        warned = true;
        el.classList.add("timer-warning");
      }
      if (seconds <= 0) {
        clearInterval(interval);
        seconds = 0;
        render();
        if (submitUrl) {
          postForm(submitUrl).then(function () {
            window.location.reload();
          });
        } else {
          window.location.reload();
        }
        return;
      }
      render();
    }, 1000);
  }

  function initQuestion(card) {
    if (!card) return;
    const lang = document.documentElement.lang === "en" ? "en" : "gu";
    const timerEl = document.getElementById("timer");
    const cardSubmitUrl = card.getAttribute("data-submit-url");
    if (timerEl) startTimer(timerEl, cardSubmitUrl);

    const phase = card.getAttribute("data-phase");
    const saveUrl = card.getAttribute("data-save-url");
    const locked = card.getAttribute("data-locked") === "1";
    const buttons = card.querySelectorAll(".option-btn");

    if (!locked) {
      buttons.forEach(function (btn) {
        btn.addEventListener("click", function () {
          const label = btn.getAttribute("data-label");
          buttons.forEach(function (b) {
            b.classList.remove("option-selected");
          });
          if (phase === "pre") {
            btn.classList.add("option-selected");
          }
          postForm(saveUrl, { option: label }).then(function (resp) {
            return resp.json();
          }).then(function (data) {
            if (data.error) return;
            if (phase === "post") {
              buttons.forEach(function (b) {
                b.disabled = true;
                const l = b.getAttribute("data-label");
                if (l === data.correct_label) b.classList.add("option-correct");
                if (l === data.selected_label && !data.is_correct) b.classList.add("option-wrong");
              });
              const area = document.getElementById("post-next-area");
              if (area) {
                const total = parseInt(card.getAttribute("data-total"), 10);
                const order = parseInt(card.getAttribute("data-order"), 10);
                const isLast = order >= total;
                const advanceBtn = document.createElement("button");
                advanceBtn.type = "button";
                advanceBtn.id = isLast ? "finish-btn" : "next-btn";
                advanceBtn.className = "btn-primary";
                advanceBtn.textContent = isLast
                  ? (lang === "en" ? "Finish" : "પૂર્ણ કરો")
                  : (lang === "en" ? "Next" : "આગળ");
                area.appendChild(advanceBtn);
                if (isLast) {
                  advanceBtn.setAttribute("data-submit-url", card.getAttribute("data-submit-url"));
                  bindFinish(advanceBtn);
                } else {
                  advanceBtn.addEventListener("click", function () {
                    window.location.href = card.getAttribute("data-next-question-url");
                  });
                }
              }
            }
          });
        });
      });
    }

    const submitBtn = document.getElementById("submit-btn");
    if (submitBtn) {
      submitBtn.addEventListener("click", function () {
        fetch(card.getAttribute("data-progress-url"))
          .then(function (resp) { return resp.json(); })
          .then(function (progress) {
            const unanswered = progress.unanswered || 0;
            if (window.confirm(confirmText(lang, unanswered))) {
              postForm(submitBtn.getAttribute("data-submit-url")).then(function () {
                window.location.reload();
              });
            }
          });
      });
    }

    function bindFinish(btn) {
      btn.addEventListener("click", function () {
        postForm(btn.getAttribute("data-submit-url")).then(function () {
          window.location.reload();
        });
      });
    }

    const finishBtn = document.getElementById("finish-btn");
    if (finishBtn) bindFinish(finishBtn);
  }

  function pollWaiting(card) {
    if (!card) return;
    const statusUrl = card.getAttribute("data-status-url");
    const entryUrl = card.getAttribute("data-entry-url");
    setInterval(function () {
      fetch(statusUrl).then(function (r) {
        return r.json();
      }).then(function (data) {
        if (data.status !== "pre_closed") {
          window.location.href = entryUrl;
        }
      });
    }, 15000);
  }

  window.CEEQuiz = { initQuestion: initQuestion, pollWaiting: pollWaiting };
})();
