// toasts.js – Bootstrap-5 toast helper
(() => {
  const box = document.createElement("div");
  box.className = "toast-container position-fixed bottom-0 end-0 p-3";
  box.id = "toaster";
  document.body.appendChild(box);

  window.toast = (msg, type="info", delay=3500) => {
    const id = "t" + Date.now();
    box.insertAdjacentHTML("beforeend",
      `<div id="${id}" class="toast text-bg-${type}" data-bs-delay="${delay}">
         <div class="toast-body">${msg}</div>
       </div>`);
    new bootstrap.Toast(document.getElementById(id)).show();
  };
})();
