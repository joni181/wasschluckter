/* New-entry modal behavior on the overview page:
 *   - FAB / other triggers open the <dialog>, Cancel/close buttons dismiss it
 *   - client-side validation of numeric precision (≤2 decimal places)
 *   - Save → POST /api/entries, then reload so the new entry appears in History
 *   - Camera → opens the native file picker (photo upload placeholder).
 */

(function () {
  const dialog = document.getElementById("new-entry-dialog");
  const form = document.getElementById("entry-form");
  if (!dialog || !form) return;

  const status = form.querySelector("[data-form-status]");
  const cameraBtn = form.querySelector('[data-action="camera"]');
  const cameraInput = form.querySelector("[data-camera-input]");
  const cancelBtn = form.querySelector('[data-action="cancel"]');
  const saveBtn = form.querySelector('button[type="submit"]');

  function openDialog() {
    resetStatus();
    if (typeof dialog.showModal === "function") dialog.showModal();
    else dialog.setAttribute("open", "");
  }

  function closeDialog() {
    if (typeof dialog.close === "function") dialog.close();
    else dialog.removeAttribute("open");
  }

  function resetStatus() {
    setStatus(null);
    clearFieldErrors();
    saveBtn.disabled = false;
  }

  document.querySelectorAll('[data-action="open-new-entry"]').forEach((el) => {
    el.addEventListener("click", (e) => { e.preventDefault(); openDialog(); });
  });

  document.querySelectorAll('[data-action="close-new-entry"]').forEach((el) => {
    el.addEventListener("click", () => closeDialog());
  });

  // Click outside the panel closes the dialog.
  dialog.addEventListener("click", (event) => {
    if (event.target === dialog) closeDialog();
  });

  function setStatus(text, variant) {
    if (!status) return;
    if (!text) { status.hidden = true; status.textContent = ""; status.removeAttribute("data-variant"); return; }
    status.hidden = false;
    status.textContent = text;
    if (variant) status.setAttribute("data-variant", variant);
    else status.removeAttribute("data-variant");
  }

  function clearFieldErrors() {
    form.querySelectorAll("[data-error-for]").forEach((el) => {
      el.textContent = "";
    });
  }

  function showFieldErrors(errors) {
    Object.entries(errors).forEach(([name, message]) => {
      const target = form.querySelector(`[data-error-for="${name}"]`);
      if (target) target.textContent = message;
    });
  }

  function enforceTwoDecimals(input) {
    if (!input.value) return;
    input.value = input.value.replace(",", ".");
    const num = Number(input.value);
    if (!Number.isFinite(num)) return;
    const rounded = Math.round(num * 100) / 100;
    if (rounded.toString() !== input.value) {
      input.value = rounded.toString();
    }
  }

  ["liters", "amount_eur"].forEach((name) => {
    const input = form.querySelector(`[name="${name}"]`);
    if (input) {
      input.addEventListener("blur", () => enforceTwoDecimals(input));
    }
  });

  cancelBtn?.addEventListener("click", () => closeDialog());

  cameraBtn?.addEventListener("click", () => {
    cameraInput?.click();
  });

  cameraInput?.addEventListener("change", () => {
    if (cameraInput.files?.length) {
      setStatus(`Attached photo: ${cameraInput.files[0].name} (OCR coming soon)`, null);
    }
  });

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    clearFieldErrors();
    setStatus("Saving…", null);
    saveBtn.disabled = true;

    const formData = new FormData(form);

    ["liters", "amount_eur"].forEach((name) => {
      const raw = formData.get(name);
      if (raw) formData.set(name, String(Number(String(raw).replace(",", "."))));
    });

    try {
      const response = await fetch("/api/entries", { method: "POST", body: formData });
      const data = await response.json().catch(() => ({}));

      if (!response.ok) {
        if (data.errors) showFieldErrors(data.errors);
        setStatus("Please fix the highlighted fields.", "error");
        saveBtn.disabled = false;
        return;
      }

      if (data.warnings && data.warnings.length) {
        setStatus("Saved — " + data.warnings.join(" "), null);
      } else {
        setStatus("Saved.", null);
      }

      setTimeout(() => { window.location.reload(); }, 350);
    } catch (err) {
      setStatus("Could not save: " + (err?.message || err), "error");
      saveBtn.disabled = false;
    }
  });
})();
