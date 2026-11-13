// Exibe a lista de arquivos selecionados antes do envio.
(() => {
  const input = document.getElementById('arquivos');
  const list = document.getElementById('file-list');
  if (!input || !list) return;

  input.addEventListener('change', () => {
    list.textContent = '';
    [...input.files].forEach((file) => {
      const item = document.createElement('li');
      const kb = (file.size / 1024).toFixed(1);
      item.textContent = `${file.name} (${kb} KB)`;
      list.appendChild(item);
    });
  });
})();
