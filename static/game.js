(function () {
  "use strict";

  // ---------- Telegram WebApp bootstrap ----------
  var tg = window.Telegram && window.Telegram.WebApp ? window.Telegram.WebApp : null;
  var user = { id: "guest", username: "guest" };
  if (tg) {
    tg.ready();
    tg.expand();
    var u = tg.initDataUnsafe && tg.initDataUnsafe.user;
    if (u) {
      user.id = String(u.id);
      user.username = u.username || u.first_name || "agent";
    }
  } else {
    // Fallback for testing outside Telegram
    user.id = "local-" + Math.floor(Math.random() * 100000);
    user.username = "guest";
  }

  document.getElementById("handle").textContent = "@" + user.username;
  document.getElementById("avatar").textContent = user.username.charAt(0).toUpperCase();

  // ---------- Matrix rain background ----------
  var canvas = document.getElementById("rain");
  var ctx = canvas.getContext("2d");
  var GLYPHS = "01アカサタナハマヤラワABCDEFGHIJKLMNOPQRSTUVWXYZ";
  var fontSize = 16;
  var columns, drops;

  function resizeCanvas() {
    canvas.width = window.innerWidth;
    canvas.height = window.innerHeight;
    columns = Math.floor(canvas.width / fontSize);
    drops = new Array(columns).fill(1);
  }
  window.addEventListener("resize", resizeCanvas);
  resizeCanvas();

  function drawRain() {
    ctx.fillStyle = "rgba(4, 20, 10, 0.15)";
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.fillStyle = "#4dff9e";
    ctx.font = fontSize + "px monospace";
    for (var i = 0; i < drops.length; i++) {
      var text = GLYPHS.charAt(Math.floor(Math.random() * GLYPHS.length));
      ctx.fillText(text, i * fontSize, drops[i] * fontSize);
      if (drops[i] * fontSize > canvas.height && Math.random() > 0.975) {
        drops[i] = 0;
      }
      drops[i]++;
    }
    requestAnimationFrame(drawRain);
  }
  requestAnimationFrame(drawRain);

  // ---------- Screen navigation ----------
  var screens = document.querySelectorAll(".screen");
  var tabs = document.querySelectorAll(".tab");

  function showScreen(id) {
    for (var i = 0; i < screens.length; i++) {
      screens[i].classList.toggle("active", screens[i].id === id);
    }
    for (var j = 0; j < tabs.length; j++) {
      tabs[j].classList.toggle("active", tabs[j].dataset.screen === id);
    }
    if (id === "screen-board") loadLeaderboard();
  }

  for (var t = 0; t < tabs.length; t++) {
    tabs[t].addEventListener("click", function (e) {
      showScreen(e.currentTarget.dataset.screen);
    });
  }
  document.getElementById("btn-home").addEventListener("click", function () {
    showScreen("screen-home");
  });
  document.getElementById("btn-quit").addEventListener("click", function () {
    endGame();
    showScreen("screen-home");
  });

  // ---------- Splash sequence ----------
  var splashFill = document.getElementById("splash-fill");
  var splashStatus = document.getElementById("splash-status");
  var steps = ["initializing terminal…", "loading glyph table…", "linking grid…", "ready."];
  var pct = 0;
  var splashTimer = setInterval(function () {
    pct += 25;
    splashFill.style.width = pct + "%";
    splashStatus.textContent = steps[Math.min(Math.floor(pct / 25), steps.length - 1)];
    if (pct >= 100) {
      clearInterval(splashTimer);
      setTimeout(function () {
        loadBestScore();
        showScreen("screen-home");
      }, 300);
    }
  }, 260);

  // ---------- Best score (local) ----------
  var LOCAL_KEY = "gridhack_best_score";
  function getLocalBest() {
    var v = parseInt(localGet(LOCAL_KEY) || "0", 10);
    return isNaN(v) ? 0 : v;
  }
  // In-memory fallback store (artifacts/webviews may restrict localStorage)
  var memoryStore = {};
  function localGet(key) {
    try { return window.localStorage.getItem(key); } catch (e) { return memoryStore[key]; }
  }
  function localSet(key, val) {
    try { window.localStorage.setItem(key, val); } catch (e) { memoryStore[key] = val; }
  }

  var DIAL_CIRC = 553;
  function loadBestScore() {
    var best = getLocalBest();
    document.getElementById("best-score").textContent = best;
    var ratio = Math.min(best / 500, 1); // purely visual fill, 500 = full ring
    document.getElementById("dial-fill").style.strokeDashoffset = String(DIAL_CIRC * (1 - ratio));
  }

  // ---------- Game logic ----------
  var grid = document.getElementById("grid");
  var hudScore = document.getElementById("hud-score");
  var hudLives = document.getElementById("hud-lives");
  var targetGlyphEl = document.getElementById("target-glyph");
  var GAME_GLYPHS = "アカサタナハマヤラワ01XYZΔΣΞ".split("");

  var state = null; // active game state
  var spawnTimer = null;
  var moveTimer = null;

  function startGame() {
    grid.innerHTML = "";
    state = {
      score: 0,
      lives: 3,
      speed: 1.4,      // px per tick
      spawnRate: 950,   // ms between spawns
      target: pickTarget(),
      glyphs: []        // {el, x, y}
    };
    hudScore.textContent = "0";
    hudLives.textContent = "●●●";
    targetGlyphEl.textContent = state.target;
    showScreen("screen-game");

    spawnTimer = setInterval(spawnGlyph, state.spawnRate);
    moveTimer = setInterval(tick, 30);
  }

  function pickTarget() {
    return GAME_GLYPHS[Math.floor(Math.random() * GAME_GLYPHS.length)];
  }

  function spawnGlyph() {
    if (!state) return;
    var el = document.createElement("div");
    el.className = "glyph";
    var isTarget = Math.random() < 0.35;
    var ch = isTarget ? state.target : GAME_GLYPHS[Math.floor(Math.random() * GAME_GLYPHS.length)];
    el.textContent = ch;
    var gw = grid.clientWidth || 300;
    var x = Math.random() * (gw - 30);
    el.style.left = x + "px";
    el.style.top = "-24px";
    el.dataset.isTarget = isTarget ? "1" : "0";
    el.addEventListener("click", function () { onGlyphTap(el); });
    grid.appendChild(el);
    state.glyphs.push({ el: el, y: -24 });
  }

  function onGlyphTap(el) {
    if (!state) return;
    var isTarget = el.dataset.isTarget === "1";
    if (isTarget) {
      el.classList.add("hit");
      state.score += 10;
      hudScore.textContent = String(state.score);
      state.target = pickTarget();
      targetGlyphEl.textContent = state.target;
      // Re-tag remaining on-screen glyphs against the new target
      for (var i = 0; i < state.glyphs.length; i++) {
        var g = state.glyphs[i];
        if (g.el !== el) {
          g.el.dataset.isTarget = (g.el.textContent === state.target) ? "1" : "0";
        }
      }
      if (state.score % 60 === 0 && state.speed < 4) {
        state.speed += 0.35;
        state.spawnRate = Math.max(450, state.spawnRate - 60);
        clearInterval(spawnTimer);
        spawnTimer = setInterval(spawnGlyph, state.spawnRate);
      }
    } else {
      el.classList.add("wrong");
      loseLife();
    }
    setTimeout(function () { removeGlyph(el); }, 120);
  }

  function loseLife() {
    if (!state) return;
    state.lives -= 1;
    hudLives.textContent = "●".repeat(Math.max(state.lives, 0)) + "○".repeat(3 - Math.max(state.lives, 0));
    if (state.lives <= 0) {
      finishGame();
    }
  }

  function removeGlyph(el) {
    if (!state) return;
    for (var i = 0; i < state.glyphs.length; i++) {
      if (state.glyphs[i].el === el) {
        state.glyphs.splice(i, 1);
        break;
      }
    }
    if (el.parentNode) el.parentNode.removeChild(el);
  }

  function tick() {
    if (!state) return;
    var gh = grid.clientHeight || 400;
    for (var i = state.glyphs.length - 1; i >= 0; i--) {
      var g = state.glyphs[i];
      g.y += state.speed;
      g.el.style.top = g.y + "px";
      if (g.y > gh) {
        var wasTarget = g.el.dataset.isTarget === "1";
        removeGlyph(g.el);
        if (wasTarget) loseLife();
      }
    }
  }

  function endGame() {
    clearInterval(spawnTimer);
    clearInterval(moveTimer);
    state = null;
    grid.innerHTML = "";
  }

  function finishGame() {
    var finalScore = state ? state.score : 0;
    endGame();

    var best = getLocalBest();
    var isNewBest = finalScore > best;
    if (isNewBest) {
      localSet(LOCAL_KEY, String(finalScore));
    }

    document.getElementById("result-score").textContent = finalScore;
    document.getElementById("result-note").textContent = isNewBest
      ? "New personal best on this device."
      : "Personal best on this device: " + Math.max(best, finalScore) + ".";

    submitScore(finalScore);
    loadBestScore();
    showScreen("screen-result");
  }

  function submitScore(score) {
    fetch("/api/score", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ user_id: user.id, username: user.username, score: score })
    }).catch(function () { /* offline is fine, local best still saved */ });
  }

  function loadLeaderboard() {
    var list = document.getElementById("board-list");
    list.innerHTML = '<li class="muted">Loading…</li>';
    fetch("/api/leaderboard")
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (!data.ok || !data.leaderboard.length) {
          list.innerHTML = '<li class="muted">No scores yet. Be the first.</li>';
          return;
        }
        list.innerHTML = "";
        data.leaderboard.forEach(function (row, idx) {
          var li = document.createElement("li");
          li.innerHTML = '<span><span class="rank">' + (idx + 1) + '.</span>@' + row.username + '</span><span>' + row.best_score + '</span>';
          list.appendChild(li);
        });
      })
      .catch(function () {
        list.innerHTML = '<li class="muted">Leaderboard unavailable right now.</li>';
      });
  }

  document.getElementById("btn-play").addEventListener("click", startGame);
  document.getElementById("btn-again").addEventListener("click", startGame);
})();
