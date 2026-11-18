/* prototypes/local_view_spike.js
 *
 * Client-side frame animation for a trame "local view" (vtk.js in the browser).
 *
 * The server pushes ONE vtkPolyData whose single point-data array holds every
 * time frame as a separate component (1364 points x 2400 components).  From
 * then on this script owns the animation: it picks component k out of the
 * already-uploaded buffer, hands that column to the vtk.js array as a
 * 1-component array and re-renders.  No server message, no image encoding,
 * no round-trip per frame.
 *
 * Entry point: window.localViewSpike.init(cfg), called by an inline script
 * injected by prototypes/local_view_spike.py.
 */
(function (global) {
  "use strict";

  var S = {
    cfg: null,
    view: null,
    polydata: null,
    array: null,
    ncomp: 0,
    flat: null,
    scratch: null,
    frame: 0,
    playing: true,
    started: false,
    labelEl: null,
    sliderEl: null,
    buttonEl: null,
    lastT: 0,
    acc: 0
  };

  function maxOf(values) {
    var m = 0;
    for (var i = 0; i < values.length; i += 1) {
      if (values[i] > m) {
        m = values[i];
      }
    }
    return m;
  }

  /* Same text as prototypes/local_view_spike.py:label_for_frame(). */
  function labelFor(k) {
    var steps = S.cfg.frameIndex;
    var total = S.cfg.stepTotal || maxOf(steps);
    return "Step " + steps[k] + " / " + total + " (Stride " + S.cfg.stride + ")";
  }

  /* Walk renderWindow -> renderer -> actor -> mapper -> polydata. */
  function resolvePolydata(view) {
    var rw = view && view.renderWindow;
    if (!rw) {
      return null;
    }
    var renderers = rw.getRenderers();
    if (!renderers) {
      return null;
    }
    for (var i = 0; i < renderers.getNumberOfItems(); i += 1) {
      var actors = renderers.getItem(i).getActors();
      if (!actors) {
        continue;
      }
      for (var j = 0; j < actors.getNumberOfItems(); j += 1) {
        var actor = actors.getItem(j);
        var mapper = actor.getMapper ? actor.getMapper() : null;
        var input = mapper && mapper.getInputData ? mapper.getInputData() : null;
        if (input && input.getPointData) {
          return input;
        }
      }
    }
    return null;
  }

  /* Bind to the trame ref once the local view has produced its polydata. */
  function bind() {
    var refs = global.trame && global.trame.refs;
    var view = refs ? refs[S.cfg.ref] : null;
    if (!view) {
      return false;
    }
    var polydata = resolvePolydata(view);
    if (!polydata) {
      return false;
    }
    var pointData = polydata.getPointData();
    var array = pointData.getArrayByName
      ? pointData.getArrayByName(S.cfg.arrayName)
      : null;
    if (!array) {
      array = pointData.getArray(S.cfg.arrayName);
    }
    if (!array) {
      return false;
    }
    S.view = view;
    S.polydata = polydata;
    S.array = array;
    S.ncomp = array.getNumberOfComponents() || 1;
    S.flat = array.getData();
    S.scratch = new Float32Array(array.getNumberOfTuples());
    S.started = true;
    return true;
  }

  /* Strided pick of component k -> 1-component array -> render. */
  function showFrame(k) {
    var n = S.cfg.nframes;
    var comp = S.ncomp > 1 ? ((k % n) + n) % n : 0;
    var flat = S.flat;
    var scratch = S.scratch;
    var stride = S.ncomp;
    for (var p = 0; p < scratch.length; p += 1) {
      scratch[p] = flat[p * stride + comp];
    }
    S.array.setData(scratch, 1);
    S.array.modified();
    S.polydata.modified();
    S.view.renderWindow.render();
    S.frame = comp;
    paint();
  }

  function installOverlay() {
    var host = (S.view && S.view.container) || document.body;
    var box = document.createElement("div");
    box.className = "local-view-spike-overlay";
    box.style.cssText =
      "position:absolute;left:12px;bottom:12px;z-index:20;display:flex;" +
      "gap:8px;align-items:center;font:13px/1.2 sans-serif;color:#fff;" +
      "background:rgba(0,0,0,.55);padding:6px 8px;border-radius:6px;";
    S.buttonEl = document.createElement("button");
    S.buttonEl.type = "button";
    S.buttonEl.addEventListener("click", toggle);
    S.labelEl = document.createElement("span");
    S.sliderEl = document.createElement("input");
    S.sliderEl.type = "range";
    S.sliderEl.min = "0";
    S.sliderEl.max = String(S.cfg.nframes - 1);
    S.sliderEl.step = "1";
    S.sliderEl.value = "0";
    S.sliderEl.addEventListener("input", function () {
      S.playing = false;
      showFrame(parseInt(S.sliderEl.value, 10) || 0);
    });
    box.appendChild(S.buttonEl);
    box.appendChild(S.labelEl);
    box.appendChild(S.sliderEl);
    if (host.style && global.getComputedStyle(host).position === "static") {
      host.style.position = "relative";
    }
    host.appendChild(box);
  }

  function paint() {
    if (S.labelEl) {
      S.labelEl.textContent = labelFor(S.frame);
    }
    if (S.sliderEl) {
      S.sliderEl.value = String(S.frame);
    }
    if (S.buttonEl) {
      S.buttonEl.textContent = S.playing ? "Pause" : "Play";
    }
  }

  function toggle() {
    S.playing = !S.playing;
    paint();
  }

  function tick(t) {
    if (!S.started) {
      global.requestAnimationFrame(tick);
      return;
    }
    if (S.playing) {
      var period = 1000 / (S.cfg.fps || 24);
      S.acc += S.lastT ? t - S.lastT : period;
      if (S.acc >= period) {
        var advance = Math.floor(S.acc / period);
        S.acc -= advance * period;
        showFrame(S.frame + advance);
      }
    }
    S.lastT = t;
    global.requestAnimationFrame(tick);
  }

  function boot() {
    if (S.started || !bind()) {
      global.requestAnimationFrame(boot);
      return;
    }
    installOverlay();
    showFrame(0);
    global.requestAnimationFrame(tick);
  }

  function init(cfg) {
    S.cfg = cfg;
    S.frame = 0;
    S.playing = cfg.autoplay !== false;
    S.started = false;
    boot();
  }

  global.localViewSpike = {
    init: init,
    label: labelFor,
    show: showFrame,
    toggle: toggle,
    state: S
  };
})(typeof window !== "undefined" ? window : this);
