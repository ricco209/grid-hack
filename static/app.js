// ============================================================
// GRID // HACK — Mini App frontend logic
// ============================================================

(function () {
  "use strict";

  var tg = window.Telegram && window.Telegram.WebApp ? window.Telegram.WebApp : null;
  if (tg) {
    try {
      tg.ready();
      tg.expand();
      tg.setHeaderColor && tg.setHeaderColor("#0A6E7D");
      tg.setBackgroundColor && tg.setBackgroundColor("#DFF6F1");
    } catch (e) { /* тест вне Telegram */ }
  }

  var INIT_DATA = tg ? tg.initData : "";

  var state = {
    user: null,
    lbScope: "global",
  };

  // ---------- helpers ----------

  function fmt(n) {
    return (n || 0).toLocaleString("en-US");
  }

  function api(path, method) {
    return fetch(path, {
      method: method || "GET",
      headers: { "X-Init-Data": INIT_DATA, "Content-Type": "application/json" },
    }).then(function (r) { return r.json(); });
  }

  var toastEl = document.getElementById("toast");
  var toastTimer = null;
  function toast(msg) {
    if (!toastEl) return;
    toastEl.textContent = msg;
    toastEl.classList.add("show");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function () { toastEl.classList.remove("show"); }, 2200);
  }

  // ---------- loading screen ----------

  function runLoadingSequence(done) {
    var fill = document.getElementById("loading-fill");
    var pct = document.getElementById("loading-pct");
    var sub = document.getElementById("loading-sub");
    var messages = [
      "Heading to the shore…",
      "Collecting seashells…",
      "Waking up the coconuts…",
      "Almost on the sand…",
    ];
    var progress = 0;
    var msgIdx = 0;
    var interval = setInterval(function () {
      progress += Math.random() * 14 + 6;
      if (progress >= 100) progress = 100;
      fill.style.width = progress + "%";
      pct.textContent = Math.floor(progress) + "%";
      if (progress > (msgIdx + 1) * 25 && msgIdx < messages.length - 1) {
        msgIdx += 1;
        sub.textContent = messages[msgIdx];
      }
      if (progress >= 100) {
        clearInterval(interval);
        setTimeout(done, 350);
      }
    }, 220);
  }

  // ---------- ring water level (доля выполненных дневных дел) ----------

  function updateRingProgress(u) {
    var done = 0, total = 3;
    if (u.checked_in_today) done += 1;
    if (u.bonus_claimed_today) done += 1;
    if (u.joined_channel) done += 1;
    var frac = total ? done / total : 0;
    // ring radius=104 -> диапазон 120..240 в координатах viewBox (0..240)
    var top = 120 - frac * 100; // от низа (120) до почти верха (20)
    var water = document.getElementById("ring-water");
    var wave = document.getElementById("ring-wave");
    if (water) water.setAttribute("y", top);
    if (wave) wave.setAttribute("transform", "translate(0," + (top - 30) + ")");
  }

  // ---------- render: profile / balance ----------

  function renderUser(u) {
    state.user = u;
    var name = u.username ? "@" + u.username : (u.first_name || "Player");
    document.getElementById("profile-username").textContent = name;
    document.getElementById("avatar-initial").textContent = (u.first_name || u.username || "P").charAt(0).toUpperCase();
    document.getElementById("balance-value").textContent = fmt(u.balance);
    document.getElementById("rank-value").textContent = u.rank ? "#" + u.rank : "#—";
    updateRingProgress(u);

    var collectBtn = document.getElementById("btn-collect");
    if (u.checked_in_today) {
      collectBtn.disabled = true;
      collectBtn.innerHTML = '<span class="shell-icon">🐚</span> Come back tomorrow';
    } else {
      collectBtn.disabled = false;
      collectBtn.innerHTML = '<span class="shell-icon">🐚</span> Collect Your Daily Shells';
    }

    var bonusState = document.getElementById("bonus-state");
    if (u.bonus_claimed_today) {
      bonusState.textContent = "Claimed";
      bonusState.classList.remove("claimable");
    } else {
      bonusState.textContent = "Claim";
      bonusState.classList.add("claimable");
    }

    // задания
    setTaskState("join_channel", u.joined_channel, "Verify");
    setTaskState("checkin", u.checked_in_today, "Collect");
    setTaskState("invite", u.has_referral, "Invite");

    var chestBtn = document.getElementById("chest-btn");
    if (u.chest_claimed_today) {
      chestBtn.disabled = true;
      chestBtn.textContent = "Claimed";
    } else if (u.chest_eligible) {
      chestBtn.disabled = false;
      chestBtn.textContent = "Claim";
    } else {
      chestBtn.disabled = true;
      chestBtn.textContent = "Locked";
    }
  }

  function setTaskState(taskKey, isDone, activeLabel) {
    var row = document.querySelector('.task-row[data-task="' + taskKey + '"]');
    if (!row) return;
    var btn = row.querySelector(".task-btn");
    if (isDone) {
      btn.textContent = "Verified";
      btn.classList.add("done");
      btn.disabled = taskKey !== "invite"; // "Invite" остаётся кликабельной (открыть Friends)
    } else {
      btn.textContent = activeLabel;
      btn.classList.remove("done");
      btn.disabled = false;
    }
  }

  function refreshMe() {
    return api("/api/me").then(function (res) {
      if (res.ok) renderUser(res.user);
      return res;
    });
  }

  // ---------- actions ----------

  document.getElementById("btn-collect").addEventListener("click", function () {
    api("/api/checkin", "POST").then(function (res) {
      if (res.ok) {
        toast("🐚 +" + fmt(res.reward) + " SAND! Streak: " + res.streak + " days");
        refreshMe();
      } else if (res.error === "already_claimed") {
        toast("Already collected today — come back tomorrow!");
      } else {
        toast("Something went wrong, try again.");
      }
    });
  });

  document.getElementById("bonus-card").addEventListener("click", function () {
    if (state.user && state.user.bonus_claimed_today) return;
    api("/api/bonus/claim", "POST").then(function (res) {
      if (res.ok) {
        toast("🥥 +" + fmt(res.reward) + " bonus SAND!");
        refreshMe();
      } else if (res.error === "already_claimed") {
        toast("Bonus already claimed today.");
      }
    });
  });

  document.getElementById("task-list").addEventListener("click", function (e) {
    var btn = e.target.closest(".task-btn");
    if (!btn || btn.disabled) return;
    var action = btn.getAttribute("data-action");

    if (action === "join_channel") {
      if (tg && tg.openTelegramLink) {
        // при желании подставьте адрес своего канала
      }
      btn.disabled = true;
      btn.textContent = "Checking…";
      api("/api/tasks/join_channel/verify", "POST").then(function (res) {
        if (res.ok) {
          toast(res.already ? "Already verified." : "✈️ +" + fmt(res.reward) + " SAND!");
          refreshMe();
        } else {
          toast("You haven't joined the channel yet.");
          btn.disabled = false;
          btn.textContent = "Verify";
        }
      });
    } else if (action === "checkin") {
      document.getElementById("btn-collect").click();
    } else if (action === "goto-friends") {
      switchScreen("friends");
    }
  });

  document.getElementById("chest-btn").addEventListener("click", function () {
    api("/api/tasks/chest/claim", "POST").then(function (res) {
      if (res.ok) {
        toast("🧰 +" + fmt(res.reward) + " chest SAND!");
        refreshMe();
      } else if (res.error === "already_claimed") {
        toast("Chest already opened today.");
      } else {
        toast("Finish all 3 tasks first!");
      }
    });
  });

  // ---------- friends screen ----------

  function loadFriends() {
    api("/api/friends").then(function (res) {
      if (!res.ok) return;
      var link = res.invite_link || ("Referral code: " + res.referral_code);
      document.getElementById("invite-link").textContent = link;
      var list = document.getElementById("friends-list");
      if (!res.friends.length) {
        list.innerHTML = '<div class="empty-state">No friends invited yet — share your link to start earning!</div>';
        return;
      }
      list.innerHTML = res.friends.map(function (f) {
        return '<div class="friend-row">' +
          '<div class="friend-avatar">' + (f.name || "P").charAt(0).toUpperCase() + '</div>' +
          '<div class="friend-name">' + escapeHtml(f.name) + '</div>' +
          '<div class="friend-balance">🐚 ' + fmt(f.balance) + '</div>' +
        '</div>';
      }).join("");
    });
  }

  document.getElementById("copy-link-btn").addEventListener("click", function () {
    var text = document.getElementById("invite-link").textContent;
    if (navigator.clipboard) {
      navigator.clipboard.writeText(text).then(function () { toast("Link copied!"); });
    } else {
      toast("Copy: " + text);
    }
  });

  document.getElementById("share-link-btn").addEventListener("click", function () {
    var text = document.getElementById("invite-link").textContent;
    if (tg && tg.openTelegramLink) {
      tg.openTelegramLink("https://t.me/share/url?url=" + encodeURIComponent(text) +
        "&text=" + encodeURIComponent("Join me on GRID // HACK Beach! 🏖️"));
    } else if (navigator.share) {
      navigator.share({ text: text });
    } else {
      toast("Share this link: " + text);
    }
  });

  // ---------- island / leaderboard ----------

  function loadLeaderboard(scope) {
    api("/api/leaderboard?scope=" + scope).then(function (res) {
      if (!res.ok) return;
      var list = document.getElementById("lb-list");
      list.innerHTML = res.top.map(function (r) {
        return '<div class="lb-row' + (r.rank === 1 ? ' top1' : '') + '">' +
          '<div class="lb-rank">' + medal(r.rank) + '</div>' +
          '<div class="lb-avatar">' + (r.name || "P").charAt(0).toUpperCase() + '</div>' +
          '<div class="lb-name-wrap"><div class="lb-name">' + escapeHtml(r.name) + (r.is_me ? " (you)" : "") + '</div></div>' +
          '<div class="lb-balance">🐚 ' + fmt(r.balance) + '</div>' +
        '</div>';
      }).join("");

      var meBox = document.getElementById("lb-me");
      if (res.me) {
        meBox.style.display = "flex";
        meBox.innerHTML =
          '<div class="lb-rank">#' + res.me.rank + '</div>' +
          '<div class="lb-avatar">' + (res.me.name || "P").charAt(0).toUpperCase() + '</div>' +
          '<div class="lb-name-wrap"><div class="lb-name">' + escapeHtml(res.me.name) + ' (you)</div></div>' +
          '<div class="lb-balance">🐚 ' + fmt(res.me.balance) + '</div>';
      } else {
        meBox.style.display = "none";
      }
    });
  }

  function medal(rank) {
    if (rank === 1) return "🥇";
    if (rank === 2) return "🥈";
    if (rank === 3) return "🥉";
    return "#" + rank;
  }

  document.querySelectorAll(".lb-tab").forEach(function (tab) {
    tab.addEventListener("click", function () {
      document.querySelectorAll(".lb-tab").forEach(function (t) { t.classList.remove("active"); });
      tab.classList.add("active");
      state.lbScope = tab.getAttribute("data-scope");
      loadLeaderboard(state.lbScope);
    });
  });

  function escapeHtml(s) {
    var d = document.createElement("div");
    d.textContent = s || "";
    return d.innerHTML;
  }

  // ---------- navigation ----------

  function switchScreen(name) {
    document.querySelectorAll(".screen").forEach(function (s) {
      s.classList.toggle("hidden", s.getAttribute("data-screen") !== name);
    });
    document.querySelectorAll(".nav-btn").forEach(function (b) {
      b.classList.toggle("active", b.getAttribute("data-nav") === name);
    });
    if (name === "friends") loadFriends();
    if (name === "island") loadLeaderboard(state.lbScope);
    if (tg && tg.HapticFeedback) tg.HapticFeedback.impactOccurred("light");
  }

  document.querySelectorAll(".nav-btn").forEach(function (btn) {
    btn.addEventListener("click", function () { switchScreen(btn.getAttribute("data-nav")); });
  });

  // ---------- boot ----------

  function boot() {
    refreshMe().finally(function () {
      var loadingScreen = document.getElementById("loading-screen");
      loadingScreen.classList.add("fade-out");
      document.getElementById("app").classList.remove("hidden");
      setTimeout(function () { loadingScreen.style.display = "none"; }, 650);
    });
  }

  runLoadingSequence(boot);
})();