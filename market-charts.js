/* Local chart tabs: no third-party script or network request is needed. */
document.querySelectorAll('.market-chart-group').forEach(group => {
  const tabs = [...group.querySelectorAll('[role="tab"]')];
  function select(tab, focus = false) {
    tabs.forEach(button => {
      const selected = button === tab;
      button.setAttribute('aria-selected', String(selected));
      button.tabIndex = selected ? 0 : -1;
      document.getElementById(button.getAttribute('aria-controls')).hidden = !selected;
    });
    if (focus) tab.focus();
  }
  tabs.forEach((tab, index) => {
    tab.addEventListener('click', () => select(tab));
    tab.addEventListener('keydown', event => {
      let target;
      if (event.key === 'ArrowRight') target = (index + 1) % tabs.length;
      else if (event.key === 'ArrowLeft') target = (index - 1 + tabs.length) % tabs.length;
      else if (event.key === 'Home') target = 0;
      else if (event.key === 'End') target = tabs.length - 1;
      if (target !== undefined) { event.preventDefault(); select(tabs[target], true); }
    });
  });
  // Keep every chart visible without JavaScript; activate tabs only after listeners exist.
  select(tabs[0]);
});
