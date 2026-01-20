/**
 * DataTable - Reusable table component with efficient DOM reuse
 *
 * Supports: sorting, selection (single/multi), checkboxes, custom formatters,
 * dynamic middle truncation
 */

import { truncateMiddle } from "./lib/ui.js";

function shallowEqual(a, b) {
  if (a === b) return true;
  if (!a || !b) return false;
  const keysA = Object.keys(a);
  const keysB = Object.keys(b);
  if (keysA.length !== keysB.length) return false;
  for (const key of keysA) {
    if (a[key] !== b[key]) return false;
  }
  return true;
}

class DataTable {
  constructor(selector, options = {}) {
    this.container = typeof selector === 'string'
      ? document.querySelector(selector)
      : selector;
    this.columns = options.columns || [];
    this.selectable = options.selectable || false;
    this.multiSelect = options.multiSelect || false;
    this.checkboxes = options.checkboxes || false;
    this.onRowClick = options.onRowClick || null;
    this.onRowDoubleClick = options.onRowDoubleClick || null;
    this.onSelectionChange = options.onSelectionChange || null;
    this.onCheckChange = options.onCheckChange || null;
    this.getKey = options.getKey || ((row, i) => i);
    this.getChecked = options.getChecked || (() => false);
    this.getRowClass = options.getRowClass || null;
    this.emptyText = options.emptyText || "No data";
    this.compact = options.compact || false;
    this.autoScroll = options.autoScroll || false;

    this._data = [];
    this._dataMap = new Map();  // Key -> current item (for fresh data in click handlers)
    this._selectedKeys = new Set();
    this._elements = new Map();

    // Track cells needing dynamic truncation: Map<cell, {col, item}>
    this._dynamicCells = new Map();
    this._resizeObserver = null;
    this._charWidth = null; // Cached character width

    // Auto-scroll: track if user scrolled away from bottom
    this._userScrolledAway = false;
    this._prevDataLength = 0;

    this._render();
    this._setupResizeObserver();
    this._setupAutoScroll();
  }

  _setupAutoScroll() {
    if (!this.autoScroll) return;

    // Track when user scrolls away from bottom
    this.container.addEventListener('scroll', () => {
      const { scrollTop, scrollHeight, clientHeight } = this.container;
      const atBottom = scrollHeight - scrollTop - clientHeight < 50;
      this._userScrolledAway = !atBottom;
    });
  }

  _setupResizeObserver() {
    // Check if any column uses dynamic truncateMiddle
    const hasDynamic = this.columns.some(c => c.truncateMiddle === true);
    if (!hasDynamic) return;

    this._rafId = null;  // Track requestAnimationFrame ID

    this._resizeObserver = new ResizeObserver((entries) => {
      // Debounce with requestAnimationFrame
      if (this._rafId) {
        cancelAnimationFrame(this._rafId);
      }

      this._rafId = requestAnimationFrame(() => {
        this._rafId = null;
        for (const entry of entries) {
          const cell = entry.target;
          const info = this._dynamicCells.get(cell);
          if (info) {
            this._applyDynamicTruncation(cell, info.col, info.item, entry.contentRect.width);
          }
        }
      });
    });
  }

  _measureCharWidth() {
    if (this._charWidth) return this._charWidth;

    // Create a measuring element
    const measure = document.createElement("span");
    measure.style.cssText = "position:absolute;visibility:hidden;white-space:nowrap;font:inherit;";
    measure.textContent = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789";
    this.container.appendChild(measure);
    this._charWidth = measure.offsetWidth / measure.textContent.length;
    measure.remove();

    return this._charWidth;
  }

  _applyDynamicTruncation(cell, col, item, width) {
    const value = item[col.key];
    if (typeof value !== "string") return;

    const charWidth = this._measureCharWidth();
    const padding = 16; // Account for cell padding
    const availableWidth = width - padding;
    const maxChars = Math.max(10, Math.floor(availableWidth / charWidth));

    cell.textContent = truncateMiddle(value, maxChars);
  }

  _render() {
    this.container.innerHTML = "";
    this.container.className = "data-table" + (this.compact ? " data-table--compact" : "");

    // Build grid-template-columns from column definitions
    this.container.style.gridTemplateColumns = this._buildGridColumns();

    // Header (if columns have headers)
    if (this.columns.some(c => c.header)) {
      this._header = document.createElement("div");
      this._header.className = "data-table-header";
      this._header.appendChild(this._createHeaderRow());
      this.container.appendChild(this._header);
    }

    // Body
    this._body = document.createElement("div");
    this._body.className = "data-table-body";
    this.container.appendChild(this._body);
  }

  _buildGridColumns() {
    const cols = [];

    // Checkbox column if enabled
    if (this.checkboxes) {
      cols.push("24px");
    }

    // Data columns
    for (const col of this.columns) {
      if (col.width === "auto") {
        cols.push("auto");
      } else if (col.width) {
        cols.push(col.width);
      } else {
        // Flex column - use minmax for proper truncation
        cols.push("minmax(0, 1fr)");
      }
    }

    return cols.join(" ");
  }

  _createHeaderRow() {
    const row = document.createElement("div");
    row.className = "data-table-row";

    if (this.checkboxes) {
      const cell = document.createElement("div");
      cell.className = "data-table-cell data-table-cell--checkbox";
      row.appendChild(cell);
    }

    for (const col of this.columns) {
      const cell = document.createElement("div");
      cell.className = "data-table-cell";
      if (col.center) cell.classList.add("data-table-cell--center");
      cell.textContent = col.header || "";
      row.appendChild(cell);
    }
    return row;
  }

  update(data) {
    this._data = data || [];
    const seen = new Set();

    // Clear empty state if present
    const emptyEl = this._body.querySelector(".data-table-empty");
    if (emptyEl) emptyEl.remove();

    // Update/create rows
    for (let i = 0; i < this._data.length; i++) {
      const item = this._data[i];
      const key = this.getKey(item, i);
      seen.add(key);

      // Check if data actually changed (skip update if identical)
      const prevItem = this._dataMap.get(key);
      const changed = !prevItem || !shallowEqual(prevItem, item);

      // Store current item for fresh data in click handlers
      this._dataMap.set(key, item);

      let row = this._elements.get(key);
      if (!row) {
        row = this._createRow(item, key);
        this._elements.set(key, row);
        this._body.appendChild(row);
      } else if (changed) {
        this._updateRow(row, item, key);
      }
    }

    // Remove stale rows and data
    for (const [key, el] of this._elements) {
      if (!seen.has(key)) {
        // Unobserve dynamic cells before removal to prevent memory leak
        const cells = el.querySelectorAll(".data-table-cell");
        cells.forEach((cell) => {
          if (this._dynamicCells.has(cell)) {
            this._resizeObserver?.unobserve(cell);
            this._dynamicCells.delete(cell);
          }
        });
        el.remove();
        this._elements.delete(key);
        this._dataMap.delete(key);
      }
    }

    // Reorder rows to match data order (appendChild moves existing elements)
    for (let i = 0; i < this._data.length; i++) {
      const key = this.getKey(this._data[i], i);
      const row = this._elements.get(key);
      if (row) this._body.appendChild(row);
    }

    // Empty state
    if (this._data.length === 0) {
      this._body.innerHTML = `<div class="data-table-empty">${this.emptyText}</div>`;
    }

    // Auto-scroll to bottom on new entries (if user hasn't scrolled away)
    if (this.autoScroll && this._data.length > this._prevDataLength && !this._userScrolledAway) {
      this.container.scrollTop = this.container.scrollHeight;
    }
    this._prevDataLength = this._data.length;
  }

  _createRow(item, key) {
    const row = document.createElement("div");
    row.className = "data-table-row";
    row.dataset.key = key;

    if (this._selectedKeys.has(key)) {
      row.classList.add("data-table-row--selected");
    }

    // Apply custom row class(es)
    if (this.getRowClass) {
      const rowClass = this.getRowClass(item, key);
      if (rowClass) {
        row.classList.add(...rowClass.split(' ').filter(Boolean));
      }
    }

    // Checkbox column
    if (this.checkboxes) {
      const cell = document.createElement("div");
      cell.className = "data-table-cell data-table-cell--checkbox";
      const checkbox = document.createElement("input");
      checkbox.type = "checkbox";
      checkbox.checked = this.getChecked(item, key);
      checkbox.onchange = (e) => {
        e.stopPropagation();
        if (this.onCheckChange) this.onCheckChange(item, key, checkbox.checked);
      };
      cell.appendChild(checkbox);
      row.appendChild(cell);
    }

    // Data columns
    for (const col of this.columns) {
      const cell = document.createElement("div");
      cell.className = "data-table-cell";
      if (col.truncate) cell.classList.add("data-table-cell--truncate");
      if (col.monospace) cell.classList.add("data-table-cell--mono");
      if (col.center) cell.classList.add("data-table-cell--center");
      if (col.className) cell.classList.add(col.className);

      this._renderCell(cell, col, item);
      row.appendChild(cell);
    }

    // Click handler - use _dataMap for fresh data
    row.onclick = (e) => {
      if (e.target.type === 'checkbox') return;

      if (this.selectable) {
        if (this.multiSelect) {
          this.toggleSelect(key);
        } else {
          this.select(key);
        }
      }
      if (this.onRowClick) {
        const currentItem = this._dataMap.get(key);
        this.onRowClick(currentItem, key);
      }
    };

    // Double-click handler - use _dataMap for fresh data
    row.ondblclick = (e) => {
      if (e.target.type === 'checkbox') return;
      if (this.onRowDoubleClick) {
        const currentItem = this._dataMap.get(key);
        this.onRowDoubleClick(currentItem, key);
      }
    };

    return row;
  }

  _renderCell(cell, col, item) {
    let value = item[col.key];

    if (col.formatter) {
      const content = col.formatter(value, item);
      if (typeof content === "string") {
        cell.textContent = content;
      } else if (content instanceof Node) {
        cell.innerHTML = "";
        cell.appendChild(content);
      } else {
        cell.textContent = content ?? "";
      }
    } else if (col.truncateMiddle === true) {
      // Dynamic middle truncation - observe cell for resize
      cell.textContent = value ?? "";
      cell.title = value ?? "";

      // Unobserve old if exists
      if (this._resizeObserver && this._dynamicCells.has(cell)) {
        this._resizeObserver.unobserve(cell);
      }

      // Track and observe
      this._dynamicCells.set(cell, { col, item });
      if (this._resizeObserver) {
        this._resizeObserver.observe(cell);
      }
    } else if (col.truncateMiddle && typeof value === "string") {
      // Fixed length middle truncation
      const maxLen = typeof col.truncateMiddle === "number" ? col.truncateMiddle : 50;
      cell.textContent = truncateMiddle(value, maxLen);
      cell.title = value ?? "";
    } else {
      cell.textContent = value ?? "";
      if (col.truncate) cell.title = value ?? "";
    }
  }

  _updateRow(row, item, key) {
    // Update checkbox if present
    if (this.checkboxes) {
      const checkbox = row.querySelector('input[type="checkbox"]');
      if (checkbox) checkbox.checked = this.getChecked(item, key);
    }

    // Update data cells
    const cells = row.querySelectorAll(".data-table-cell");
    const startIdx = this.checkboxes ? 1 : 0;

    for (let i = 0; i < this.columns.length; i++) {
      const col = this.columns[i];
      const cell = cells[startIdx + i];
      if (cell) this._renderCell(cell, col, item);
    }

    // Update selection state
    row.classList.toggle("data-table-row--selected", this._selectedKeys.has(key));

    // Update custom row class(es) - only change if different
    if (this.getRowClass) {
      const prevClass = row.dataset.rowClass || "";
      const newClass = this.getRowClass(item, key) || "";
      if (prevClass !== newClass) {
        if (prevClass) row.classList.remove(...prevClass.split(" ").filter(Boolean));
        if (newClass) row.classList.add(...newClass.split(" ").filter(Boolean));
        row.dataset.rowClass = newClass;
      }
    }
  }

  select(key) {
    if (!this.multiSelect) {
      // Deselect all others
      for (const k of this._selectedKeys) {
        const row = this._elements.get(k);
        if (row) row.classList.remove("data-table-row--selected");
      }
      this._selectedKeys.clear();
    }

    this._selectedKeys.add(key);
    const row = this._elements.get(key);
    if (row) row.classList.add("data-table-row--selected");

    if (this.onSelectionChange) {
      this.onSelectionChange(this.getSelection());
    }
  }

  toggleSelect(key) {
    if (this._selectedKeys.has(key)) {
      this._selectedKeys.delete(key);
      const row = this._elements.get(key);
      if (row) row.classList.remove("data-table-row--selected");
    } else {
      this._selectedKeys.add(key);
      const row = this._elements.get(key);
      if (row) row.classList.add("data-table-row--selected");
    }

    if (this.onSelectionChange) {
      this.onSelectionChange(this.getSelection());
    }
  }

  getSelection() {
    return Array.from(this._selectedKeys);
  }

  setSelection(keys) {
    // Clear old
    for (const k of this._selectedKeys) {
      const row = this._elements.get(k);
      if (row) row.classList.remove("data-table-row--selected");
    }

    this._selectedKeys = new Set(keys);

    // Apply new
    for (const k of this._selectedKeys) {
      const row = this._elements.get(k);
      if (row) row.classList.add("data-table-row--selected");
    }
  }

  clearSelection() {
    for (const k of this._selectedKeys) {
      const row = this._elements.get(k);
      if (row) row.classList.remove("data-table-row--selected");
    }
    this._selectedKeys.clear();

    if (this.onSelectionChange) {
      this.onSelectionChange([]);
    }
  }

  getRowByKey(key) {
    return this._elements.get(key);
  }

  scrollToKey(key) {
    const row = this._elements.get(key);
    if (row) row.scrollIntoView({ block: "nearest" });
  }

  destroy() {
    // Clean up requestAnimationFrame
    if (this._rafId) {
      cancelAnimationFrame(this._rafId);
      this._rafId = null;
    }
    // Clean up ResizeObserver
    if (this._resizeObserver) {
      this._resizeObserver.disconnect();
      this._resizeObserver = null;
    }
    this._dynamicCells.clear();
    this._dataMap.clear();
    // Clean up overlay (attached to parent)
    if (this._overlay) {
      this._overlay.remove();
      this._overlay = null;
    }
  }

  setLoading(message = null) {
    this.container.classList.add("loading");
    if (message) {
      this._showOverlay(message);
    }
  }

  clearLoading() {
    this.container.classList.remove("loading");
    this._hideOverlay();
  }

  _showOverlay(message) {
    if (!this._overlay) {
      this._overlay = document.createElement("div");
      this._overlay.className = "datatable-overlay";
      // Append to parent so overlay covers visible area (not scrolled content)
      const parent = this.container.parentElement || this.container;
      parent.style.position = 'relative';
      parent.appendChild(this._overlay);
      this._overlayParent = parent;
    }
    this._overlay.textContent = message;
    this._overlay.classList.add("visible");
  }

  _hideOverlay() {
    if (this._overlay) {
      this._overlay.classList.remove("visible");
    }
  }
}

// ES6 export
export { DataTable };
