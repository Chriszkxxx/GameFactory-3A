/**
 * DOM overlay HUD layer.
 *
 * A three.js game's HUD is plain DOM on top of the canvas, so the
 * framework provides a minimal declarative layer: named widgets, value
 * binding, and deterministic `data-a3game-*` attributes that end-to-end
 * tests can assert against.
 *
 * The layer owns no gameplay meaning; a generated game declares what its
 * widgets mean.
 */

const STYLE_ID = 'a3game-hud-style';
const BASE_STYLE = `
.a3game-hud-root { position:absolute; inset:0; pointer-events:none;
  font-family: system-ui, -apple-system, "Segoe UI", sans-serif;
  color:#f3f5f8; text-shadow:0 1px 2px rgba(0,0,0,.6); }
.a3game-hud-widget { position:absolute; pointer-events:none;
  font-size:14px; line-height:1.4; }
.a3game-hud-widget[data-a3game-anchor="top-left"] { top:16px; left:16px; }
.a3game-hud-widget[data-a3game-anchor="top-center"] { top:16px; left:50%;
  transform:translateX(-50%); }
.a3game-hud-widget[data-a3game-anchor="top-right"] { top:16px; right:16px; }
.a3game-hud-widget[data-a3game-anchor="center"] { top:50%; left:50%;
  transform:translate(-50%,-50%); }
.a3game-hud-widget[data-a3game-anchor="bottom-left"] { bottom:16px; left:16px; }
.a3game-hud-widget[data-a3game-anchor="bottom-center"] { bottom:16px;
  left:50%; transform:translateX(-50%); }
.a3game-hud-widget[data-a3game-anchor="bottom-right"] { bottom:16px;
  right:16px; }
.a3game-hud-bar { width:180px; height:10px; border-radius:5px;
  background:rgba(255,255,255,.18); overflow:hidden; }
.a3game-hud-bar > i { display:block; height:100%; width:0%;
  background:linear-gradient(90deg,#4ade80,#22d3ee); transition:width .12s; }
.a3game-hud-crosshair { width:18px; height:18px; }
.a3game-hud-crosshair::before, .a3game-hud-crosshair::after {
  content:''; position:absolute; background:rgba(255,255,255,.85); }
.a3game-hud-crosshair::before { left:8px; top:0; width:2px; height:18px; }
.a3game-hud-crosshair::after { top:8px; left:0; height:2px; width:18px; }
`;

const ANCHORS = new Set([
  'top-left',
  'top-center',
  'top-right',
  'center',
  'bottom-left',
  'bottom-center',
  'bottom-right',
]);

const resolveElement = (target) => {
  if (!target) return null;
  if (typeof target === 'string') return document.querySelector(target);
  return target;
};

export class A3GameHudLayer {
  /**
   * @param {{container: string | HTMLElement}} options
   */
  constructor(options = {}) {
    const container = resolveElement(options.container);
    if (!container) {
      throw new Error('A3GameHudLayer requires an existing container');
    }
    this.container = container;
    this.root = document.createElement('div');
    this.root.className = 'a3game-hud-root';
    this.root.dataset.a3gameHud = 'root';
    this.container.appendChild(this.root);
    /** @type {Map<string, {element: HTMLElement, kind: string}>} */
    this.widgets = new Map();
    this.#injectStyle();
  }

  /**
   * Declare a text widget.
   *
   * @param {string} name
   * @param {{anchor?: string, value?: string, className?: string}} [options]
   */
  addText(name, options = {}) {
    const element = this.#createWidget(name, 'text', options);
    element.textContent = String(options.value ?? '');
    return element;
  }

  /**
   * Declare a normalized 0..1 bar widget, for example health or boost.
   *
   * @param {string} name
   * @param {{anchor?: string, value?: number, label?: string}} [options]
   */
  addBar(name, options = {}) {
    const element = this.#createWidget(name, 'bar', options);
    element.innerHTML = '';
    if (options.label) {
      const label = document.createElement('span');
      label.textContent = String(options.label);
      element.appendChild(label);
    }
    const bar = document.createElement('div');
    bar.className = 'a3game-hud-bar';
    bar.appendChild(document.createElement('i'));
    element.appendChild(bar);
    this.setValue(name, Number(options.value ?? 1));
    return element;
  }

  /** Declare a centred crosshair, for FPS-style aiming. */
  addCrosshair(name = 'crosshair') {
    const element = this.#createWidget(name, 'crosshair', {
      anchor: 'center',
    });
    element.classList.add('a3game-hud-crosshair');
    return element;
  }

  /**
   * Update one widget's value.
   *
   * Text widgets receive the stringified value; bar widgets clamp to
   * 0..1. Every update also writes `data-a3game-value` so a Playwright
   * assertion can read HUD state without screenshots.
   */
  setValue(name, value) {
    const widget = this.widgets.get(String(name));
    if (!widget) return false;
    const { element, kind } = widget;
    if (kind === 'bar') {
      const ratio = Math.max(0, Math.min(1, Number(value) || 0));
      const fill = element.querySelector('.a3game-hud-bar > i');
      if (fill) fill.style.width = `${(ratio * 100).toFixed(1)}%`;
      element.dataset.a3gameValue = ratio.toFixed(4);
      return true;
    }
    if (kind === 'text') {
      element.textContent = String(value ?? '');
    }
    element.dataset.a3gameValue = String(value ?? '');
    return true;
  }

  /** Batch-update several widgets. */
  setValues(values = {}) {
    for (const [name, value] of Object.entries(values)) {
      this.setValue(name, value);
    }
    return this;
  }

  setVisible(name, visible) {
    const widget = this.widgets.get(String(name));
    if (!widget) return false;
    widget.element.style.display = visible ? '' : 'none';
    widget.element.dataset.a3gameVisible = visible ? 'true' : 'false';
    return true;
  }

  remove(name) {
    const widget = this.widgets.get(String(name));
    if (!widget) return false;
    widget.element.remove();
    this.widgets.delete(String(name));
    return true;
  }

  /** @returns {object} the readable HUD state, for tests and evidence. */
  getState() {
    const state = {};
    for (const [name, widget] of this.widgets) {
      state[name] = {
        kind: widget.kind,
        value: widget.element.dataset.a3gameValue ?? '',
        visible: widget.element.style.display !== 'none',
      };
    }
    return state;
  }

  dispose() {
    this.widgets.clear();
    this.root.remove();
  }

  #createWidget(name, kind, options) {
    const key = String(name);
    this.remove(key);
    const element = document.createElement('div');
    element.className = `a3game-hud-widget ${options.className ?? ''}`.trim();
    const anchor = ANCHORS.has(options.anchor)
      ? options.anchor
      : 'top-left';
    element.dataset.a3gameWidget = key;
    element.dataset.a3gameKind = kind;
    element.dataset.a3gameAnchor = anchor;
    this.root.appendChild(element);
    this.widgets.set(key, { element, kind });
    return element;
  }

  #injectStyle() {
    if (document.getElementById(STYLE_ID)) return;
    const style = document.createElement('style');
    style.id = STYLE_ID;
    style.textContent = BASE_STYLE;
    document.head.appendChild(style);
  }
}
