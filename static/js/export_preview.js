(() => {
  "use strict";

  const app = document.getElementById("export-app");
  if (!app) return;

  const caseId = Number(app.dataset.caseId);
  let previewVersion = Number(app.dataset.previewVersion || 1);
  let preview = JSON.parse(document.getElementById("preview-state-json").textContent);
  const defaultPreview = JSON.parse(document.getElementById("default-preview-json").textContent);
  const allImages = JSON.parse(document.getElementById("images-json").textContent);
  const imagesById = new Map(allImages.map((image) => [Number(image.id), image]));

  const widthSpans = { one_third: 4, half: 6, two_thirds: 8, full: 12 };
  const spanChoices = [
    { span: 4, value: "one_third" },
    { span: 6, value: "half" },
    { span: 8, value: "two_thirds" },
    { span: 12, value: "full" },
  ];

  let selectedKey = "cover";
  let saveTimer = null;
  let saveInFlight = false;
  let saveAgain = false;
  let dirty = false;
  let selectedExportFormat = null;
  let draggedBlock = null;
  let draggedImage = null;

  const canvas = document.getElementById("preview-canvas");
  const sectionGrid = document.getElementById("preview-section-grid");
  const inspectorTitle = document.getElementById("inspector-title");
  const coverControls = document.getElementById("cover-controls");
  const sectionControls = document.getElementById("section-controls");

  const controls = {
    width: document.getElementById("section-width"),
    layout: document.getElementById("section-layout"),
    style: document.getElementById("section-style"),
    height: document.getElementById("section-height"),
    titleSize: document.getElementById("title-size"),
    bodySize: document.getElementById("body-size"),
    imageHeight: document.getElementById("image-height"),
    imageFit: document.getElementById("image-fit"),
    imageColumns: document.getElementById("image-columns"),
    showCaption: document.getElementById("show-caption"),
    showEvidenceType: document.getElementById("show-evidence-type"),
  };

  function sectionElement(key) {
    return document.querySelector(`[data-section-key="${CSS.escape(key)}"]`);
  }

  function scheduleAutosave() {
    clearTimeout(saveTimer);
    saveTimer = setTimeout(flushAutosave, 850);
  }

  function markDirty() {
    dirty = true;
    scheduleAutosave();
  }

  async function flushAutosave() {
    clearTimeout(saveTimer);
    saveTimer = null;
    if (!dirty) return;

    if (saveInFlight) {
      saveAgain = true;
      return;
    }

    saveInFlight = true;
    dirty = false;

    try {
      const response = await fetch(`/cases/${caseId}/export-preview`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ preview, version: previewVersion }),
        keepalive: true,
      });

      if (response.status === 409) {
        const data = await response.json();
        previewVersion = Number(data?.detail?.current_version || previewVersion);
        dirty = true;
        saveAgain = true;
        return;
      }

      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        throw new Error(typeof data.detail === "string" ? data.detail : "Preview autosave failed.");
      }

      const data = await response.json();
      previewVersion = Number(data.version);
      preview = data.preview;
    } catch (error) {
      dirty = true;
      if (window.showToast) {
        showToast({
          type: "error",
          title: "Preview was not saved",
          description: error.message || "Check your connection and try again.",
        });
      }
    } finally {
      saveInFlight = false;
      if (saveAgain || dirty) {
        saveAgain = false;
        scheduleAutosave();
      }
    }
  }

  async function ensureSaved() {
    clearTimeout(saveTimer);
    saveTimer = null;

    while (dirty || saveInFlight) {
      if (dirty && !saveInFlight) {
        await flushAutosave();
      } else {
        await new Promise((resolve) => setTimeout(resolve, 70));
      }
    }
  }

  function setSelected(key) {
    selectedKey = key;

    document.querySelectorAll("[data-editor-target]").forEach((element) => {
      const elementKey = element.dataset.editorTarget === "cover"
        ? "cover"
        : element.dataset.sectionKey;
      element.classList.toggle("is-selected", elementKey === key);
    });

    document.querySelectorAll(".export-section-link").forEach((button) => {
      const targetKey = button.dataset.target === "preview-cover"
        ? "cover"
        : button.dataset.target;
      button.classList.toggle("is-active", targetKey === key);
    });

    if (key === "cover") {
      inspectorTitle.textContent = "Cover";
      coverControls.classList.remove("hidden");
      sectionControls.classList.add("hidden");
      return;
    }

    const element = sectionElement(key);
    inspectorTitle.textContent = element?.querySelector("h2")?.textContent || "Section";
    coverControls.classList.add("hidden");
    sectionControls.classList.remove("hidden");
    syncSectionControls();
  }

  function updateControlOutputs() {
    if (selectedKey === "cover") return;
    const settings = preview.sections[selectedKey];
    document.getElementById("section-height-value").textContent = `${settings.min_height}px`;
    document.getElementById("title-size-value").textContent = `${settings.title_size}px`;
    document.getElementById("body-size-value").textContent = `${settings.body_size}px`;
    document.getElementById("image-height-value").textContent = `${settings.image_height}px`;
  }

  function syncSectionControls() {
    if (selectedKey === "cover") return;
    const settings = preview.sections[selectedKey];
    controls.width.value = settings.width;
    controls.layout.value = settings.layout;
    controls.style.value = settings.style;
    controls.height.value = settings.min_height;
    controls.titleSize.value = settings.title_size;
    controls.bodySize.value = settings.body_size;
    controls.imageHeight.value = settings.image_height;
    controls.imageFit.value = settings.image_fit;
    controls.imageColumns.value = String(settings.image_columns);
    controls.showCaption.checked = settings.show_caption;
    controls.showEvidenceType.checked = settings.show_evidence_type;
    updateControlOutputs();
  }

  function applySection(key) {
    const element = sectionElement(key);
    if (!element) return;
    const settings = preview.sections[key];

    element.dataset.width = settings.width;
    element.dataset.layout = settings.layout;
    element.style.setProperty("--section-span", widthSpans[settings.width] || 12);
    element.style.setProperty("--section-min-height", `${settings.min_height}px`);
    element.style.setProperty("--section-padding", `${settings.padding}px`);
    element.style.setProperty("--section-title-size", `${settings.title_size}px`);
    element.style.setProperty("--section-body-size", `${settings.body_size}px`);
    element.style.setProperty("--section-line-height", settings.line_height);
    element.style.setProperty("--section-text-align", settings.text_align);
    element.style.setProperty("--section-image-height", `${settings.image_height}px`);
    element.style.setProperty("--section-image-fit", settings.image_fit);
    element.style.setProperty("--section-image-columns", settings.image_columns);

    element.classList.remove(
      "preview-section--plain",
      "preview-section--soft",
      "preview-section--outline"
    );
    element.classList.add(`preview-section--${settings.style}`);
    element.querySelector(".preview-section__body").dataset.layout = settings.layout;

    element.querySelectorAll(".preview-image-card__label").forEach((label) => {
      label.hidden = !settings.show_evidence_type;
    });
    element.querySelectorAll("figcaption").forEach((caption) => {
      caption.hidden = !settings.show_caption;
    });
  }

  function applyCover() {
    const media = document.getElementById("cover-media");
    media.style.setProperty("--cover-image-height", `${preview.cover.image_height}px`);
    media.style.setProperty("--cover-image-fit", preview.cover.image_fit);
    const selectedImage = imagesById.get(Number(preview.cover.cover_image_id));
    media.innerHTML = "";

    if (selectedImage) {
      media.classList.remove("is-empty");
      const image = document.createElement("img");
      image.src = selectedImage.location;
      image.alt = selectedImage.caption || selectedImage.name;
      media.appendChild(image);
    } else {
      media.classList.add("is-empty");
      media.innerHTML = `<div class="empty-media-placeholder"><span>Cover image</span><small>Choose one from Layout settings</small></div>`;
    }
  }

  function reorderImagesInDom(key) {
    const grid = sectionElement(key)?.querySelector(".preview-image-grid");
    if (!grid) return;
    preview.sections[key].image_order.forEach((imageId) => {
      const card = grid.querySelector(`[data-image-id="${imageId}"]`);
      if (card) grid.appendChild(card);
    });
  }

  document.querySelectorAll("[data-editor-target]").forEach((element) => {
    element.addEventListener("click", (event) => {
      if (event.target.closest("input, textarea, select, .section-resize-handle")) return;
      setSelected(
        element.dataset.editorTarget === "cover"
          ? "cover"
          : element.dataset.sectionKey
      );
    });
  });

  document.querySelectorAll(".export-section-link").forEach((button) => {
    button.addEventListener("click", () => {
      const target = document.getElementById(button.dataset.target);
      target?.scrollIntoView({ behavior: "smooth", block: "start" });
      setSelected(button.dataset.target === "preview-cover" ? "cover" : button.dataset.target);
    });
  });

  function bindSectionControl(control, property, transform = (value) => value) {
    control.addEventListener("input", () => {
      if (selectedKey === "cover") return;
      const raw = control.type === "checkbox" ? control.checked : control.value;
      preview.sections[selectedKey][property] = transform(raw);
      applySection(selectedKey);
      updateControlOutputs();
      markDirty();
    });
  }

  bindSectionControl(controls.width, "width");
  bindSectionControl(controls.layout, "layout");
  bindSectionControl(controls.style, "style");
  bindSectionControl(controls.height, "min_height", Number);
  bindSectionControl(controls.titleSize, "title_size", Number);
  bindSectionControl(controls.bodySize, "body_size", Number);
  bindSectionControl(controls.imageHeight, "image_height", Number);
  bindSectionControl(controls.imageFit, "image_fit");
  bindSectionControl(controls.imageColumns, "image_columns", Number);
  bindSectionControl(controls.showCaption, "show_caption", Boolean);
  bindSectionControl(controls.showEvidenceType, "show_evidence_type", Boolean);

  const coverFields = {
    "cover-eyebrow": "eyebrow",
    "cover-subtitle": "subtitle",
    "cover-role": "role",
    "cover-platform": "platform",
    "cover-focus": "focus",
    "cover-timeline": "timeline",
  };

  Object.entries(coverFields).forEach(([id, property]) => {
    document.getElementById(id)?.addEventListener("input", (event) => {
      preview.cover[property] = event.target.value;
      markDirty();
    });
  });

  document.getElementById("cover-image-select").addEventListener("change", (event) => {
    preview.cover.cover_image_id = event.target.value ? Number(event.target.value) : null;
    applyCover();
    markDirty();
  });

  document.getElementById("cover-image-height").addEventListener("input", (event) => {
    preview.cover.image_height = Number(event.target.value);
    document.getElementById("cover-image-height-value").textContent = `${preview.cover.image_height}px`;
    applyCover();
    markDirty();
  });

  document.getElementById("cover-image-fit").addEventListener("change", (event) => {
    preview.cover.image_fit = event.target.value;
    applyCover();
    markDirty();
  });

  document.getElementById("document-font-family").addEventListener("change", (event) => {
    preview.document.font_family = event.target.value;
    canvas.style.setProperty("--document-font", `'${event.target.value}'`);
    markDirty();
  });

  document.getElementById("show-status-badges").addEventListener("change", (event) => {
    preview.document.show_status_badges = event.target.checked;
    markDirty();
  });

  document.getElementById("include-missing-sections").addEventListener("change", (event) => {
    preview.document.include_missing_sections = event.target.checked;
    markDirty();
  });
  document.getElementById("reset-layout").addEventListener("click", () => {
    const message = selectedKey === "cover"
      ? "Reset the cover layout and metadata to its defaults?"
      : "Reset this section layout to its defaults?";
    if (!window.confirm(message)) return;

    if (selectedKey === "cover") {
      preview.cover = structuredClone(defaultPreview.cover);
      Object.entries(coverFields).forEach(([id, property]) => {
        document.getElementById(id).value = preview.cover[property];
      });
      document.getElementById("cover-image-select").value = preview.cover.cover_image_id || "";
      document.getElementById("cover-image-height").value = preview.cover.image_height;
      document.getElementById("cover-image-fit").value = preview.cover.image_fit;
      document.getElementById("cover-image-height-value").textContent = `${preview.cover.image_height}px`;
      applyCover();
    } else {
      preview.sections[selectedKey] = structuredClone(defaultPreview.sections[selectedKey]);
      applySection(selectedKey);
      reorderImagesInDom(selectedKey);
      syncSectionControls();
    }
    markDirty();
  });

  document.querySelectorAll(".section-resize-handle").forEach((handle) => {
    handle.addEventListener("pointerdown", (event) => {
      event.preventDefault();
      const section = handle.closest(".preview-section");
      const key = section.dataset.sectionKey;
      setSelected(key);

      const startX = event.clientX;
      const startY = event.clientY;
      const startWidth = section.getBoundingClientRect().width;
      const startHeight = section.getBoundingClientRect().height;
      const gridWidth = sectionGrid.getBoundingClientRect().width;
      handle.setPointerCapture(event.pointerId);

      function onMove(moveEvent) {
        const targetWidth = Math.max(120, startWidth + moveEvent.clientX - startX);
        const targetSpan = Math.max(1, Math.min(12, Math.round(targetWidth / gridWidth * 12)));
        const nearest = spanChoices.reduce((best, item) => (
          Math.abs(item.span - targetSpan) < Math.abs(best.span - targetSpan)
            ? item
            : best
        ));

        preview.sections[key].width = nearest.value;
        preview.sections[key].min_height = Math.max(
          110,
          Math.min(760, Math.round((startHeight + moveEvent.clientY - startY) / 10) * 10)
        );
        applySection(key);
        syncSectionControls();
        dirty = true;
      }

      function onEnd(endEvent) {
        if (handle.hasPointerCapture(endEvent.pointerId)) {
          handle.releasePointerCapture(endEvent.pointerId);
        }
        handle.removeEventListener("pointermove", onMove);
        handle.removeEventListener("pointerup", onEnd);
        handle.removeEventListener("pointercancel", onEnd);
        markDirty();
      }

      handle.addEventListener("pointermove", onMove);
      handle.addEventListener("pointerup", onEnd);
      handle.addEventListener("pointercancel", onEnd);
    });
  });

  document.querySelectorAll(".preview-block[draggable='true']").forEach((block) => {
    block.addEventListener("dragstart", (event) => {
      if (event.target.closest(".preview-image-card")) return;
      const section = block.closest(".preview-section");
      draggedBlock = {
        key: section.dataset.sectionKey,
        type: block.dataset.blockType,
      };
      block.classList.add("is-dragging");
      event.dataTransfer.effectAllowed = "move";
    });

    block.addEventListener("dragend", () => {
      block.classList.remove("is-dragging");
      draggedBlock = null;
    });

    block.addEventListener("dragover", (event) => {
      if (!draggedBlock || event.target.closest(".preview-image-card")) return;
      const section = block.closest(".preview-section");
      if (section.dataset.sectionKey !== draggedBlock.key) return;
      event.preventDefault();
    });

    block.addEventListener("drop", (event) => {
      if (!draggedBlock || event.target.closest(".preview-image-card")) return;
      const section = block.closest(".preview-section");
      const key = section.dataset.sectionKey;
      if (key !== draggedBlock.key || block.dataset.blockType === draggedBlock.type) return;
      event.preventDefault();

      preview.sections[key].layout = draggedBlock.type === "media"
        ? "media_top"
        : "media_bottom";
      applySection(key);
      syncSectionControls();
      markDirty();
    });
  });

  document.querySelectorAll(".preview-image-card").forEach((card) => {
    card.addEventListener("dragstart", (event) => {
      event.stopPropagation();
      draggedImage = {
        id: Number(card.dataset.imageId),
        key: card.dataset.sectionKey,
      };
      card.classList.add("is-dragging");
      event.dataTransfer.effectAllowed = "move";
    });

    card.addEventListener("dragend", () => {
      card.classList.remove("is-dragging");
      draggedImage = null;
    });

    card.addEventListener("dragover", (event) => {
      if (!draggedImage || draggedImage.key !== card.dataset.sectionKey) return;
      event.preventDefault();
      event.stopPropagation();
    });

    card.addEventListener("drop", (event) => {
      if (!draggedImage || draggedImage.key !== card.dataset.sectionKey) return;
      event.preventDefault();
      event.stopPropagation();

      const targetId = Number(card.dataset.imageId);
      if (targetId === draggedImage.id) return;
      const order = [...preview.sections[draggedImage.key].image_order];
      const fromIndex = order.indexOf(draggedImage.id);
      const targetIndex = order.indexOf(targetId);
      if (fromIndex < 0 || targetIndex < 0) return;

      order.splice(fromIndex, 1);
      order.splice(targetIndex, 0, draggedImage.id);
      preview.sections[draggedImage.key].image_order = order;
      reorderImagesInDom(draggedImage.key);
      markDirty();
    });
  });

  const confirmModal = document.getElementById("confirm-export-modal");
  const formatModal = document.getElementById("format-export-modal");
  const exportButton = document.getElementById("download-export-file");
  const exportProgress = document.getElementById("export-progress");

  function openModal(modal) {
    modal.classList.remove("hidden");
    document.body.style.overflow = "hidden";
  }

  function closeModals() {
    document.querySelectorAll(".export-modal").forEach((modal) => {
      modal.classList.add("hidden");
    });
    document.body.style.overflow = "";
    selectedExportFormat = null;
    exportButton.disabled = true;
    document.querySelectorAll(".format-card").forEach((card) => {
      card.classList.remove("is-selected");
    });
    exportProgress.classList.add("hidden");
  }

  const sidebarTabs = [...document.querySelectorAll("[data-sidebar-tab]")];
  const sidebarPanels = [...document.querySelectorAll("[data-sidebar-panel]")];

  function setSidebarTab(tabName) {
    sidebarTabs.forEach((tab) => {
      const isActive = tab.dataset.sidebarTab === tabName;
      tab.classList.toggle("is-active", isActive);
      tab.setAttribute("aria-selected", String(isActive));
    });

    sidebarPanels.forEach((panel) => {
      const isActive = panel.dataset.sidebarPanel === tabName;
      panel.classList.toggle("is-active", isActive);
      panel.hidden = !isActive;
    });
  }

  sidebarTabs.forEach((tab) => {
    tab.addEventListener("click", () => setSidebarTab(tab.dataset.sidebarTab));
  });

  document.getElementById("open-export-modal").addEventListener("click", () => {
    openModal(confirmModal);
  });
  document.getElementById("continue-to-format").addEventListener("click", () => {
    confirmModal.classList.add("hidden");
    openModal(formatModal);
  });
  document.querySelectorAll("[data-close-modal]").forEach((element) => {
    element.addEventListener("click", closeModals);
  });

  document.querySelectorAll(".format-card[data-export-format]").forEach((card) => {
    card.addEventListener("click", () => {
      selectedExportFormat = card.dataset.exportFormat;
      document.querySelectorAll(".format-card").forEach((item) => {
        item.classList.toggle("is-selected", item === card);
      });
      exportButton.disabled = false;
    });
  });

  function filenameFromDisposition(disposition, fallback) {
    const utfMatch = disposition?.match(/filename\*=UTF-8''([^;]+)/i);
    if (utfMatch) return decodeURIComponent(utfMatch[1]);
    const basicMatch = disposition?.match(/filename="?([^";]+)"?/i);
    return basicMatch ? basicMatch[1] : fallback;
  }

  exportButton.addEventListener("click", async () => {
    if (!selectedExportFormat) return;
    exportButton.disabled = true;
    exportProgress.classList.remove("hidden");

    try {
      await ensureSaved();
      const response = await fetch(`/cases/${caseId}/export/${selectedExportFormat}`, {
        method: "POST",
      });

      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        throw new Error(typeof data.detail === "string" ? data.detail : "Export failed.");
      }

      const blob = await response.blob();
      const extension = "docx";
      const filename = filenameFromDisposition(
        response.headers.get("Content-Disposition"),
        `case-study.${extension}`
      );
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
      closeModals();
    } catch (error) {
      exportProgress.classList.add("hidden");
      exportButton.disabled = false;
      if (window.showToast) {
        showToast({
          type: "error",
          title: "Export failed",
          description: error.message || "Please try again.",
        });
      }
    }
  });

  window.addEventListener("beforeunload", () => {
    if (!dirty) return;
    fetch(`/cases/${caseId}/export-preview`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ preview, version: previewVersion }),
      keepalive: true,
    }).catch(() => {});
  });

  setSelected("cover");
})();
