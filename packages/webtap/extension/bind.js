/**
 * Mini Binding System for WebTap Extension
 *
 * Declarative state→UI binding without a framework.
 * Inspired by Alpine.js but ~100 lines.
 *
 * Data attributes:
 *   data-show="path.to.value"     - Toggle .hidden based on truthiness
 *   data-hide="path.to.value"     - Toggle .hidden (inverse of show)
 *   data-text="path.to.value"     - Set textContent
 *   data-class-X="path.to.value"  - Toggle class X based on truthiness
 *   data-attr-X="path.to.value"   - Set attribute X to value
 *
 * Path expressions support:
 *   - Dot notation: "fetch.enabled"
 *   - Comparisons: "fetch.paused_count > 0"
 *   - Ternary: "connected ? 'Disconnect' : 'Connect'"
 *   - Length: "selections.length"
 */

const Bind = {
  /**
   * Evaluate a path expression against state
   * @param {Object} state - State object
   * @param {string} expr - Path expression
   * @returns {any} Evaluated value
   */
  eval(state, expr) {
    if (!expr || !state) return undefined;

    // Handle ternary: "condition ? trueVal : falseVal"
    const ternaryMatch = expr.match(/^(.+?)\s*\?\s*'([^']*)'\s*:\s*'([^']*)'$/);
    if (ternaryMatch) {
      const [, condition, trueVal, falseVal] = ternaryMatch;
      return this.eval(state, condition.trim()) ? trueVal : falseVal;
    }

    // Handle comparisons: >, <, >=, <=, ===, !==
    const compMatch = expr.match(/^(.+?)\s*(>|<|>=|<=|===|!==|==|!=)\s*(.+)$/);
    if (compMatch) {
      const [, left, op, right] = compMatch;
      const leftVal = this.eval(state, left.trim());
      const rightVal = this._parseValue(right.trim());
      switch (op) {
        case ">": return leftVal > rightVal;
        case "<": return leftVal < rightVal;
        case ">=": return leftVal >= rightVal;
        case "<=": return leftVal <= rightVal;
        case "===":
        case "==": return leftVal === rightVal;
        case "!==":
        case "!=": return leftVal !== rightVal;
      }
    }

    // Handle negation: "!path.to.value"
    if (expr.startsWith("!")) {
      return !this.eval(state, expr.slice(1).trim());
    }

    // Handle dot notation path: "fetch.enabled"
    return this._getPath(state, expr);
  },

  /**
   * Get value at dot-notation path
   * @private
   */
  _getPath(obj, path) {
    const parts = path.split(".");
    let current = obj;
    for (const part of parts) {
      if (current == null) return undefined;
      // Handle Object.keys().length pattern
      if (part === "length" && typeof current === "object" && !Array.isArray(current)) {
        return Object.keys(current).length;
      }
      current = current[part];
    }
    return current;
  },

  /**
   * Parse a literal value (number, string, boolean)
   * @private
   */
  _parseValue(str) {
    if (str === "true") return true;
    if (str === "false") return false;
    if (str === "null") return null;
    if (/^-?\d+$/.test(str)) return parseInt(str, 10);
    if (/^-?\d*\.\d+$/.test(str)) return parseFloat(str);
    // Remove quotes if present
    if ((str.startsWith("'") && str.endsWith("'")) ||
        (str.startsWith('"') && str.endsWith('"'))) {
      return str.slice(1, -1);
    }
    return str;
  },

  /**
   * Apply all bindings to DOM based on state
   * @param {Object} state - Current state
   * @param {Element} root - Root element (default: document)
   */
  apply(state, root = document) {
    if (!state) return;

    // data-show: toggle .hidden based on truthiness
    root.querySelectorAll("[data-show]").forEach(el => {
      const val = this.eval(state, el.dataset.show);
      el.classList.toggle("hidden", !val);
    });

    // data-hide: toggle .hidden (inverse)
    root.querySelectorAll("[data-hide]").forEach(el => {
      const val = this.eval(state, el.dataset.hide);
      el.classList.toggle("hidden", !!val);
    });

    // data-text: set textContent
    root.querySelectorAll("[data-text]").forEach(el => {
      const val = this.eval(state, el.dataset.text);
      if (val !== undefined) {
        el.textContent = String(val);
      }
    });

    // data-class-X: toggle class X
    root.querySelectorAll("[data-class]").forEach(el => {
      // Format: "className:expression"
      const parts = el.dataset.class.split(",");
      parts.forEach(part => {
        const [className, expr] = part.split(":").map(s => s.trim());
        if (className && expr) {
          el.classList.toggle(className, !!this.eval(state, expr));
        }
      });
    });

    // data-disabled: set disabled attribute
    root.querySelectorAll("[data-disabled]").forEach(el => {
      const val = this.eval(state, el.dataset.disabled);
      el.disabled = !!val;
    });
  },

  /**
   * Create a binding context that auto-applies on state changes
   * @param {WebTapClient} client - Client with state and events
   * @returns {Object} Binding context with manual apply()
   */
  connect(client) {
    const ctx = {
      apply: () => this.apply(client.state),
    };

    // Auto-apply on state changes
    client.on("state", () => ctx.apply());

    return ctx;
  }
};

/**
 * Reusable Dropdown Component
 *
 * Usage:
 *   const dropdown = new Dropdown("#myDropdown", {
 *     onSelect: (value, item) => console.log("Selected:", value)
 *   });
 *
 * HTML structure expected:
 *   <div class="dropdown" id="myDropdown">
 *     <button class="dropdown-toggle">Label</button>
 *     <div class="dropdown-menu hidden">
 *       <button class="dropdown-item" data-value="opt1">Option 1</button>
 *       <button class="dropdown-item" data-value="opt2">Option 2</button>
 *     </div>
 *   </div>
 */
class Dropdown {
  constructor(selector, options = {}) {
    this.root = typeof selector === "string" ? document.querySelector(selector) : selector;
    if (!this.root) {
      console.warn(`Dropdown: element not found: ${selector}`);
      return;
    }

    this.toggle = this.root.querySelector(".dropdown-toggle");
    this.menu = this.root.querySelector(".dropdown-menu");
    this.onSelect = options.onSelect || (() => {});

    this._boundClose = this._handleOutsideClick.bind(this);
    this._init();
  }

  _init() {
    // Toggle on click
    this.toggle.addEventListener("click", (e) => {
      e.stopPropagation();
      this.isOpen ? this.close() : this.open();
    });

    // Item selection
    this.menu.querySelectorAll(".dropdown-item").forEach(item => {
      item.addEventListener("click", (e) => {
        e.stopPropagation();
        const value = item.dataset.value || item.dataset.mode || item.textContent;
        this._selectItem(item, value);
      });
    });

    // Keyboard navigation
    this.root.addEventListener("keydown", (e) => {
      if (e.key === "Escape") this.close();
    });
  }

  get isOpen() {
    return !this.menu.classList.contains("hidden");
  }

  open() {
    this.menu.classList.remove("hidden");
    document.addEventListener("click", this._boundClose);
  }

  close() {
    this.menu.classList.add("hidden");
    document.removeEventListener("click", this._boundClose);
  }

  _handleOutsideClick(e) {
    if (!this.root.contains(e.target)) {
      this.close();
    }
  }

  _selectItem(item, value) {
    // Update active state
    this.menu.querySelectorAll(".dropdown-item").forEach(i => {
      i.classList.toggle("active", i === item);
    });
    this.close();
    this.onSelect(value, item);
  }

  /** Set active item by value without triggering callback */
  setActive(value) {
    this.menu.querySelectorAll(".dropdown-item").forEach(item => {
      const itemValue = item.dataset.value || item.dataset.mode || item.textContent;
      item.classList.toggle("active", itemValue === value);
    });
  }

  /** Update toggle button text */
  setText(text) {
    this.toggle.textContent = text;
  }
}

/**
 * Generic List Renderer
 *
 * Efficiently renders lists with minimal DOM updates.
 * Supports keyed items for stable identity.
 *
 * Usage:
 *   const list = new ListRenderer("#myList", {
 *     render: (item, key) => {
 *       const el = document.createElement("div");
 *       el.textContent = item.name;
 *       return el;
 *     },
 *     getKey: (item) => item.id,  // optional, defaults to index
 *     onEmpty: () => document.createElement("div")  // optional empty state
 *   });
 *
 *   list.update([{id: 1, name: "Item 1"}, {id: 2, name: "Item 2"}]);
 */
class ListRenderer {
  constructor(selector, options = {}) {
    this.container = typeof selector === "string"
      ? document.querySelector(selector)
      : selector;

    if (!this.container) {
      console.warn(`ListRenderer: element not found: ${selector}`);
      return;
    }

    this.render = options.render || ((item) => {
      const el = document.createElement("div");
      el.textContent = String(item);
      return el;
    });

    this.getKey = options.getKey || ((item, index) => index);
    this.onEmpty = options.onEmpty || null;
    this._items = new Map(); // key -> { element, item }
  }

  /**
   * Update list with new items
   * @param {Array|Object} items - Array or object of items to render
   */
  update(items) {
    if (!this.container) return;

    // Normalize object to array of [key, value] entries
    const entries = Array.isArray(items)
      ? items.map((item, i) => [this.getKey(item, i), item])
      : Object.entries(items);

    // Handle empty state
    if (entries.length === 0) {
      this.container.innerHTML = "";
      this._items.clear();
      if (this.onEmpty) {
        this.container.appendChild(this.onEmpty());
      }
      return;
    }

    // Build new elements
    const newKeys = new Set();
    const fragment = document.createDocumentFragment();

    entries.forEach(([key, item]) => {
      newKeys.add(key);
      const existing = this._items.get(key);

      if (existing) {
        // Reuse existing element
        fragment.appendChild(existing.element);
      } else {
        // Create new element
        const element = this.render(item, key);
        this._items.set(key, { element, item });
        fragment.appendChild(element);
      }
    });

    // Remove stale items
    for (const [key, { element }] of this._items) {
      if (!newKeys.has(key)) {
        element.remove();
        this._items.delete(key);
      }
    }

    // Update DOM
    this.container.innerHTML = "";
    this.container.appendChild(fragment);
  }

  /** Clear the list */
  clear() {
    if (this.container) {
      this.container.innerHTML = "";
    }
    this._items.clear();
  }
}

// Export for use in extension
if (typeof module !== "undefined" && module.exports) {
  module.exports = { Bind, Dropdown, ListRenderer };
}
