export function createNotebook(canvas) {
  const context = canvas.getContext("2d");
  let drawing = false;
  let used = false;
  let lastPoint = null;

  function clear() {
    used = false;
    context.fillStyle = "#fffdf4";
    context.fillRect(0, 0, canvas.width, canvas.height);
    context.strokeStyle = "#c9d9df";
    context.lineWidth = 2;
    for (let y = 42; y < canvas.height; y += 42) {
      context.beginPath();
      context.moveTo(0, y);
      context.lineTo(canvas.width, y);
      context.stroke();
    }
    context.strokeStyle = "#e87b72";
    context.beginPath();
    context.moveTo(70, 0);
    context.lineTo(70, canvas.height);
    context.stroke();
  }

  function point(event) {
    const rect = canvas.getBoundingClientRect();
    return {
      x: ((event.clientX - rect.left) / rect.width) * canvas.width,
      y: ((event.clientY - rect.top) / rect.height) * canvas.height,
    };
  }

  canvas.addEventListener("pointerdown", (event) => {
    drawing = true;
    used = true;
    lastPoint = point(event);
    canvas.setPointerCapture?.(event.pointerId);
  });
  canvas.addEventListener("pointermove", (event) => {
    if (!drawing || !lastPoint) return;
    const next = point(event);
    context.strokeStyle = "#17202a";
    context.lineWidth = 12;
    context.lineCap = "round";
    context.lineJoin = "round";
    context.beginPath();
    context.moveTo(lastPoint.x, lastPoint.y);
    context.lineTo(next.x, next.y);
    context.stroke();
    lastPoint = next;
  });
  const stop = () => { drawing = false; lastPoint = null; };
  canvas.addEventListener("pointerup", stop);
  canvas.addEventListener("pointercancel", stop);
  clear();

  return {
    clear,
    toDataUrlIfUsed: () => (used ? canvas.toDataURL("image/png") : null),
  };
}

