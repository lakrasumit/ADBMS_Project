/* Optional enhancements: the server-rendered search works without JavaScript. */
document.addEventListener('DOMContentLoaded', () => {
  const enhanceSelect = (select) => {
    const field = select.closest('.journey-field');
    const label = field?.querySelector('label');
    const labelText = label?.querySelector('span') || label;
    if (!label || !labelText) return;

    const labelId = labelText.id || `${select.id}-label`;
    labelText.id = labelId;

    const shell = document.createElement('div');
    shell.className = 'select-shell';

    const trigger = document.createElement('button');
    trigger.className = 'select-trigger';
    trigger.type = 'button';
    trigger.setAttribute('role', 'combobox');
    trigger.setAttribute('aria-haspopup', 'listbox');
    trigger.setAttribute('aria-expanded', 'false');
    trigger.setAttribute('aria-controls', `${select.id}-listbox`);

    const value = document.createElement('span');
    value.id = `${select.id}-value`;
    value.className = 'select-value';

    const chevron = document.createElement('span');
    chevron.className = 'select-chevron';
    chevron.setAttribute('aria-hidden', 'true');

    trigger.append(value, chevron);
    trigger.setAttribute('aria-labelledby', `${labelId} ${value.id}`);

    const listbox = document.createElement('div');
    listbox.id = `${select.id}-listbox`;
    listbox.className = 'select-listbox';
    listbox.setAttribute('role', 'listbox');
    listbox.setAttribute('aria-labelledby', labelId);
    listbox.hidden = true;

    const error = document.createElement('span');
    error.id = `${select.id}-error`;
    error.className = 'select-error';
    error.setAttribute('role', 'alert');
    error.hidden = true;

    const optionNodes = Array.from(select.options, (option, index) => {
      const node = document.createElement('div');
      node.id = `${select.id}-option-${index}`;
      node.className = 'select-option';
      node.setAttribute('role', 'option');
      node.setAttribute('aria-selected', String(index === select.selectedIndex));
      node.textContent = option.textContent.trim();
      if (option.disabled) node.setAttribute('aria-disabled', 'true');
      if (!option.value) node.classList.add('is-placeholder');
      listbox.append(node);
      return node;
    });

    shell.append(trigger, listbox);
    select.after(shell);
    field.append(error);
    trigger.disabled = select.disabled;

    let activeIndex = select.selectedIndex;
    let typeahead = '';
    let typeaheadTimer;

    const enabledIndex = (start, direction) => {
      if (!optionNodes.length) return -1;
      for (let step = 0; step < optionNodes.length; step += 1) {
        const index = (start + step * direction + optionNodes.length) % optionNodes.length;
        if (!select.options[index].disabled) return index;
      }
      return -1;
    };

    const renderState = () => {
      value.textContent = select.options[select.selectedIndex]?.textContent.trim() || '';
      trigger.toggleAttribute('data-placeholder', !select.value);
      optionNodes.forEach((node, index) => {
        node.setAttribute('aria-selected', String(index === select.selectedIndex));
        node.toggleAttribute('data-active', !listbox.hidden && index === activeIndex);
      });
      if (!listbox.hidden && activeIndex >= 0) {
        trigger.setAttribute('aria-activedescendant', optionNodes[activeIndex].id);
      }
    };

    const clearError = () => {
      error.hidden = true;
      trigger.removeAttribute('aria-describedby');
      trigger.removeAttribute('aria-invalid');
    };

    const updatePlacement = () => {
      const rect = trigger.getBoundingClientRect();
      const roomBelow = window.innerHeight - rect.bottom;
      const roomAbove = rect.top;
      const desiredHeight = Math.min(280, window.innerHeight * 0.4, optionNodes.length * 44 + 16);
      shell.classList.toggle('opens-up', roomBelow < desiredHeight && roomAbove > roomBelow);
    };

    const close = () => {
      listbox.hidden = true;
      shell.classList.remove('opens-up');
      trigger.setAttribute('aria-expanded', 'false');
      trigger.removeAttribute('aria-activedescendant');
      renderState();
    };

    const setActive = (index) => {
      if (index < 0) return;
      activeIndex = index;
      renderState();
      optionNodes[index].scrollIntoView?.({ block: 'nearest' });
    };

    const open = (index = select.selectedIndex) => {
      if (listbox.hidden) {
        listbox.hidden = false;
        trigger.setAttribute('aria-expanded', 'true');
        updatePlacement();
      }
      setActive(index >= 0 ? index : enabledIndex(0, 1));
    };

    const commit = (index) => {
      if (index < 0 || select.options[index]?.disabled) return;
      select.selectedIndex = index;
      if (select.value) clearError();
      select.dispatchEvent(new Event('input', { bubbles: true }));
      select.dispatchEvent(new Event('change', { bubbles: true }));
      close();
      trigger.focus();
    };

    const move = (direction) => {
      if (listbox.hidden) {
        const start = select.selectedIndex < 0
          ? (direction > 0 ? 0 : optionNodes.length - 1)
          : select.selectedIndex + direction;
        open(enabledIndex(start, direction));
        return;
      }
      setActive(enabledIndex(activeIndex + direction, direction));
    };

    trigger.addEventListener('click', () => {
      if (listbox.hidden) open();
      else close();
    });

    trigger.addEventListener('keydown', (event) => {
      if (event.key === 'ArrowDown') {
        event.preventDefault();
        move(1);
      } else if (event.key === 'ArrowUp') {
        event.preventDefault();
        move(-1);
      } else if (event.key === 'Home' || event.key === 'End') {
        event.preventDefault();
        open(enabledIndex(event.key === 'Home' ? 0 : optionNodes.length - 1, event.key === 'Home' ? 1 : -1));
      } else if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        if (listbox.hidden) open();
        else commit(activeIndex);
      } else if (event.key === 'Escape' && !listbox.hidden) {
        event.preventDefault();
        close();
      } else if (event.key === 'Tab') {
        close();
      } else if (event.key.length === 1 && !event.ctrlKey && !event.altKey && !event.metaKey) {
        typeahead += event.key.toLocaleLowerCase();
        window.clearTimeout(typeaheadTimer);
        typeaheadTimer = window.setTimeout(() => { typeahead = ''; }, 700);
        const start = select.selectedIndex < 0 ? 0 : select.selectedIndex + 1;
        let match = -1;
        for (let offset = 0; offset < select.options.length; offset += 1) {
          const index = (start + offset) % select.options.length;
          const option = select.options[index];
          if (!option.disabled && option.textContent.trim().toLocaleLowerCase().startsWith(typeahead)) {
            match = index;
            break;
          }
        }
        if (match >= 0) commit(match);
      }
    });

    listbox.addEventListener('click', (event) => {
      const option = event.target.closest('[role="option"]');
      if (option && listbox.contains(option)) commit(optionNodes.indexOf(option));
    });

    select.addEventListener('change', renderState);
    select.addEventListener('invalid', (event) => {
      event.preventDefault();
      error.textContent = 'Choose a station before searching.';
      error.hidden = false;
      trigger.setAttribute('aria-describedby', error.id);
      trigger.setAttribute('aria-invalid', 'true');
      trigger.focus();
      open(select.selectedIndex);
    });

    label.addEventListener('click', (event) => {
      event.preventDefault();
      trigger.focus();
    });

    select.classList.add('is-enhanced');
    select.tabIndex = -1;
    select.setAttribute('aria-hidden', 'true');
    renderState();
  };

  document.querySelectorAll('.journey-form select').forEach(enhanceSelect);

  document.addEventListener('pointerdown', (event) => {
    document.querySelectorAll('.select-shell').forEach((shell) => {
      if (!shell.contains(event.target)) {
        const trigger = shell.querySelector('.select-trigger');
        const listbox = shell.querySelector('.select-listbox');
        if (trigger && listbox && !listbox.hidden) {
          listbox.hidden = true;
          trigger.setAttribute('aria-expanded', 'false');
          trigger.removeAttribute('aria-activedescendant');
          shell.querySelectorAll('[role="option"]').forEach((option) => option.removeAttribute('data-active'));
        }
      }
    });
  });

  const swap = document.querySelector('.swap-stations');
  const origin = document.getElementById('origin');
  const destination = document.getElementById('destination');
  if (swap && origin && destination) {
    swap.hidden = false;
    swap.addEventListener('click', () => {
      [origin.value, destination.value] = [destination.value, origin.value];
      origin.dispatchEvent(new Event('change', { bubbles: true }));
      destination.dispatchEvent(new Event('change', { bubbles: true }));
    });
  }
});
