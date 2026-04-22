/* New-entry form behavior:
 *   - client-side validation of numeric precision (≤2 decimal places)
 *   - Save → POST /api/entries, then navigate back to /
 *   - Cancel → confirm, then navigate back to /
 *   - Camera → opens the native file picker (acts as a photo upload).
 *     This is a placeholder until receipt OCR is wired up.
 */

(function () {
  const form = document.getElementById("entry-form");
  if (!form) return;

  const status = form.querySelector("[data-form-status]");
  const cameraBtn = form.querySelector('[data-action="camera"]');
  const cameraInput = form.querySelector("[data-camera-input]");
  const cancelBtn = form.querySelector('[data-action="cancel"]');
  const saveBtn = form.querySelector('button[type="submit"]');

  function setStatus(text, variant) {
    if (!status) return;
    if (!text) { status.hidden = true; status.textContent = ""; return; }
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
    // allow comma as decimal separator for the user
    input.value = input.value.replace(",", ".");
    const num = Number(input.value);
    if (!Number.isFinite(num)) return;
    // Round to 2dp if the user entered more digits.
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

  cancelBtn?.addEventListener("click", () => {
    if (window.confirm("Are you sure? The entry will be discarded.")) {
      window.location.href = "/";
    }
  });

  cameraBtn?.addEventListener("click", () => {
    cameraInput?.click();
  });

  cameraInput?.addEventListener("change", () => {
    // Placeholder: receipt OCR is not implemented yet.
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

    // Normalize numeric inputs once more right before sending.
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

      // Brief confirmation then go back to the overview.
      setTimeout(() => { window.location.href = "/"; }, 450);
    } catch (err) {
      setStatus("Could not save: " + (err?.message || err), "error");
      saveBtn.disabled = false;
    }
  });
})();
