(() => {
  const input = document.getElementById('search');
  const grid = document.getElementById('archive-grid');
  const empty = document.getElementById('no-results');
  if (!input || !grid) return;

  const cards = [...grid.querySelectorAll('.archive-card')];
  const filter = () => {
    const query = input.value.trim().toLocaleLowerCase('tr');
    let visible = 0;
    cards.forEach(card => {
      const match = card.textContent.toLocaleLowerCase('tr').includes(query);
      card.hidden = !match;
      if (match) visible++;
    });
    if (empty) empty.hidden = visible !== 0;
  };

  input.addEventListener('input', filter);
  document.addEventListener('keydown', event => {
    if (event.key === '/' && !['INPUT', 'TEXTAREA'].includes(document.activeElement.tagName)) {
      event.preventDefault();
      input.focus();
    }
    if (event.key === 'Escape' && document.activeElement === input) {
      input.value = '';
      filter();
      input.blur();
    }
  });
})()
  ;
