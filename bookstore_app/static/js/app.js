document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll(".flash").forEach((message) => {
    window.setTimeout(() => {
      message.classList.add("fade-out");
      window.setTimeout(() => message.remove(), 350);
    }, 3800);
  });
});
