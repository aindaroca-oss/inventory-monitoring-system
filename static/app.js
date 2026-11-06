document.addEventListener('DOMContentLoaded', () => {
  const open = id => document.getElementById(id)?.classList.add('visible');
  const close = element => element?.closest('.modal-backdrop')?.classList.remove('visible');

  document.querySelectorAll('[data-modal-open]').forEach(button => {
    button.addEventListener('click', event => {
      event.preventDefault();
      open(button.dataset.modalOpen);
    });
  });
  document.querySelectorAll('[data-modal-close]').forEach(button => button.addEventListener('click', () => close(button)));
  document.querySelectorAll('.modal-close').forEach(button => {
    if (!button.title) button.title = button.getAttribute('aria-label') || 'Close';
  });
  const notificationToggle = document.getElementById('notification-toggle');
  const notificationPanel = document.getElementById('notification-panel');
  const notificationDot = notificationToggle?.querySelector('.notification-dot');
  const notificationSeenKey = notificationToggle?.dataset.notificationKey
    ? `inventory-notifications-seen:${document.body.dataset.userId}:${notificationToggle.dataset.notificationKey}` : '';
  const setNotificationsOpen = (isOpen, markSeen = false) => {
    if (!notificationPanel || !notificationToggle) return;
    notificationPanel.hidden = !isOpen;
    notificationToggle.setAttribute('aria-expanded', String(isOpen));
    if (markSeen && notificationSeenKey) {
      sessionStorage.setItem(notificationSeenKey, 'true');
      notificationDot?.remove();
    }
  };
  if (notificationSeenKey && sessionStorage.getItem(notificationSeenKey)) notificationDot?.remove();
  notificationToggle?.addEventListener('click', () => {
    const willOpen = notificationPanel?.hidden;
    setNotificationsOpen(Boolean(willOpen), true);
  });
  document.addEventListener('click', event => {
    if (notificationPanel && !notificationPanel.hidden && !event.target.closest('.notification-menu')) {
      setNotificationsOpen(false, true);
    }
  });
  document.querySelectorAll('[data-review-action]').forEach(button => button.addEventListener('click', () => {
    const requestId = button.dataset.requestId;
    const decision = button.dataset.reviewAction;
    const detailModal = document.getElementById(`admin-request-details-${requestId}`);
    const reviewContent = document.getElementById('admin-request-review-content');
    const reviewContext = document.getElementById('admin-request-review-context');
    const reviewMeta = document.getElementById('admin-request-review-meta');
    const requestIdField = document.getElementById('admin-review-request-id');
    const decisionField = document.getElementById('admin-review-decision');
    const reviewTitle = document.getElementById('admin-request-review-title');
    const reviewSubmit = document.getElementById('admin-review-submit');
    const remarksWrap = document.getElementById('admin-decline-remarks');
    const remarksField = remarksWrap?.querySelector('textarea');
    if (!detailModal || !reviewContent) return;
    reviewContent.replaceChildren();
    reviewContext?.replaceChildren();
    reviewMeta?.replaceChildren();
    const detailsHeader = detailModal.querySelector('.modal-header');
    const requestHeading = detailsHeader?.querySelector('h2')?.cloneNode(true);
    requestHeading?.removeAttribute('id');
    if (requestHeading) reviewContext?.append(requestHeading);
    const requestStatus = detailsHeader?.querySelector('.status-chip')?.cloneNode(true);
    if (requestStatus) reviewContext?.append(requestStatus);
    detailModal.querySelectorAll('.request-detail-list,.request-remarks-copy,.request-review-meta').forEach(section => {
      const copy = section.cloneNode(true);
      copy.querySelectorAll('button').forEach(closeButton => closeButton.remove());
      if (copy.classList.contains('request-review-meta')) reviewMeta?.append(copy);
      else reviewContent.append(copy);
    });
    if (requestIdField) requestIdField.value = requestId;
    if (decisionField) decisionField.value = decision;
    const needsRemarks = decision === 'decline';
    if (remarksWrap) remarksWrap.hidden = !needsRemarks;
    if (remarksField) {
      remarksField.required = needsRemarks;
      remarksField.value = '';
      remarksField.dispatchEvent(new Event('input', { bubbles: true }));
    }
    const labels = { approve: ['Review Request', 'Approve Request'],
      fulfill: ['Review Request', 'Fulfill Request'],
      decline: ['Decline Request', 'Decline Request'] };
    const [title, submit] = labels[decision] || labels.approve;
    if (reviewTitle) reviewTitle.textContent = title;
    if (reviewSubmit) {
      reviewSubmit.textContent = submit;
      reviewSubmit.classList.toggle('review-fulfill', decision === 'fulfill');
      reviewSubmit.classList.toggle('review-decline', decision === 'decline');
    }
    open('admin-request-review-modal');
  }));
  const confirmBackdrop = document.getElementById('action-confirm-modal');
  const confirmTitle = document.getElementById('action-confirm-title');
  const confirmMessage = document.getElementById('action-confirm-message');
  const confirmCancel = confirmBackdrop?.querySelector('.confirm-keep-button');
  const confirmSubmit = document.getElementById('confirm-action-submit');
  const archiveConfirmVariants = ['archive-item-confirm', 'archive-supplier-confirm', 'archive-shelf-confirm'];
  const clearArchiveConfirmVariant = () => archiveConfirmVariants.forEach(name => confirmBackdrop?.classList.remove(name));
  let pendingConfirmForm = null;
  let pendingConfirmAction = null;
  const showConfirmation = (title, message, cancelLabel, submitLabel, action) => {
    pendingConfirmForm = null;
    pendingConfirmAction = action || null;
    if (confirmTitle) confirmTitle.textContent = title;
    if (confirmMessage) confirmMessage.textContent = message;
    if (confirmCancel) confirmCancel.textContent = cancelLabel;
    if (confirmSubmit) confirmSubmit.textContent = submitLabel;
    confirmBackdrop?.classList.remove('logout-confirm');
    clearArchiveConfirmVariant();
    confirmBackdrop?.classList.add('danger-confirm', 'visible');
  };
  document.querySelectorAll('[data-confirm-modal]').forEach(form => form.addEventListener('submit', event => {
    event.preventDefault();
    pendingConfirmForm = form;
    pendingConfirmAction = null;
    if (confirmTitle) confirmTitle.textContent = form.dataset.confirmTitle || 'Confirm action?';
    if (confirmMessage) confirmMessage.textContent = form.dataset.confirmMessage || 'Are you sure you want to continue?';
    if (confirmCancel) confirmCancel.textContent = form.dataset.confirmCancel || 'Keep';
    if (confirmSubmit) confirmSubmit.textContent = form.dataset.confirmSubmit || 'Confirm';
    confirmBackdrop?.classList.toggle('danger-confirm', form.dataset.confirmTone === 'danger');
    confirmBackdrop?.classList.toggle('logout-confirm', form.dataset.confirmTone === 'logout');
    clearArchiveConfirmVariant();
    const archiveVariant = {
      'Archive Item?': 'archive-item-confirm',
      'Archive Supplier?': 'archive-supplier-confirm',
      'Archive Shelf?': 'archive-shelf-confirm',
    }[form.dataset.confirmTitle];
    if (archiveVariant) confirmBackdrop?.classList.add(archiveVariant);
    confirmBackdrop?.classList.add('visible');
  }));
  document.querySelectorAll('[data-confirm-dismiss]').forEach(button => button.addEventListener('click', () => {
    pendingConfirmForm = null;
    pendingConfirmAction = null;
    confirmBackdrop?.classList.remove('visible', 'danger-confirm', 'logout-confirm');
    clearArchiveConfirmVariant();
  }));
  confirmSubmit?.addEventListener('click', () => {
    const form = pendingConfirmForm;
    const action = pendingConfirmAction;
    pendingConfirmForm = null;
    pendingConfirmAction = null;
    confirmBackdrop?.classList.remove('visible', 'danger-confirm', 'logout-confirm');
    clearArchiveConfirmVariant();
    if (form?.classList.contains('sidebar-logout')) {
      confirmSubmit.disabled = true;
      Promise.resolve(cartSaveQueue).finally(() => {
        confirmSubmit.disabled = false;
        form.submit();
      });
    } else if (form) form.submit();
    else action?.();
  });
  const cartKey = `dunder-inventory-request-cart-${document.body.dataset.userId || 'guest'}`;
  const stockByItem = new Map([...document.querySelectorAll('[data-add-to-cart]')].map(button => [Number(button.dataset.itemId), Number(button.dataset.itemStock || 0)]));
  const cartSaveUrl = document.body.dataset.requestCartUrl;
  const cartCsrf = document.body.dataset.csrfToken;
  let requestCart = [];
  let migrateSessionCart = false;
  const sanitizeCart = values => Array.isArray(values)
    ? values
      .filter(item => item && Number(item.item_id) > 0 && Number(item.quantity) > 0)
      .map(item => ({ ...item, stock_qty: stockByItem.get(Number(item.item_id)) ?? Number(item.stock_qty || 0) }))
      .filter(item => item.stock_qty > 0)
      .map(item => ({ ...item, quantity: Math.min(Number(item.quantity), Number(item.stock_qty)) }))
    : [];
  try {
    requestCart = sanitizeCart(JSON.parse(document.body.dataset.requestCart || '[]'));
    if (!requestCart.length && sessionStorage.getItem(cartKey) !== null) {
      requestCart = sanitizeCart(JSON.parse(sessionStorage.getItem(cartKey)));
      migrateSessionCart = requestCart.length > 0;
    }
  } catch { requestCart = []; }
  const cartList = document.getElementById('request-cart-list');
  const cartEmpty = document.getElementById('request-cart-empty');
  const cartTotal = document.getElementById('request-cart-total');
  const cartCount = document.getElementById('request-cart-count');
  const cartReview = document.getElementById('request-review-items');
  const requestItemsField = document.getElementById('request-items-json');
  const cartStep = document.getElementById('request-cart-step');
  const reviewStep = document.getElementById('request-review-step');
  const addedPopup = document.getElementById('added-to-request-popup');
  let addedPopupTimer;
  let cartSaveQueue = Promise.resolve();

  const persistCart = () => {
    sessionStorage.setItem(cartKey, JSON.stringify(requestCart));
    renderCart();
    if (cartSaveUrl && document.body.dataset.userId) {
      const snapshot = requestCart.map(item => ({ item_id: Number(item.item_id), quantity: Number(item.quantity) }));
      cartSaveQueue = cartSaveQueue.catch(() => {}).then(async () => {
        const response = await fetch(cartSaveUrl, {
          method: 'POST',
          keepalive: true,
          headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': cartCsrf },
          body: JSON.stringify({ items: snapshot }),
        });
        if (!response.ok) throw new Error('Request cart could not be saved.');
        const saved = await response.json();
        requestCart = sanitizeCart(saved.items || []);
        sessionStorage.setItem(cartKey, JSON.stringify(requestCart));
        renderCart();
      }).catch(error => {
        console.error(error);
        let notice = document.getElementById('request-cart-save-error');
        if (!notice) {
          notice = document.createElement('div');
          notice.id = 'request-cart-save-error';
          notice.className = 'notice error';
          notice.setAttribute('role', 'status');
          document.querySelector('.page-content')?.prepend(notice);
        }
        notice.textContent = 'Your cart could not be saved. Check your connection before logging out.';
      });
    }
  };
  const renderCart = () => {
    if (!cartList) return;
    cartList.replaceChildren();
    cartReview?.replaceChildren();
    const count = requestCart.reduce((sum, item) => sum + Number(item.quantity), 0);
    if (cartCount) {
      cartCount.textContent = String(count);
      cartCount.hidden = count === 0;
    }
    if (cartTotal) cartTotal.textContent = `Total Items: ${count}`;
    if (cartEmpty) cartEmpty.hidden = requestCart.length > 0;
    const reviewButton = document.getElementById('review-cart-button');
    if (reviewButton) reviewButton.disabled = requestCart.length === 0;

    requestCart.forEach((item, index) => {
      const row = document.createElement('div');
      row.className = 'request-cart-row';
      const info = document.createElement('div');
      info.className = 'request-cart-item-info';
      const name = document.createElement('b');
      name.textContent = item.item_name;
      const unit = document.createElement('small');
      unit.textContent = item.unit_name;
      info.append(name, unit);

      const controls = document.createElement('div');
      controls.className = 'request-cart-controls';
      const minus = document.createElement('button');
      minus.type = 'button';
      minus.className = 'cart-quantity-button decrease';
      minus.textContent = '−';
      minus.setAttribute('aria-label', `Decrease ${item.item_name} quantity`);
      minus.disabled = Number(item.quantity) <= 1;
      minus.addEventListener('click', () => {
        requestCart[index].quantity = Math.max(1, Number(requestCart[index].quantity) - 1);
        persistCart();
      });
      const quantity = document.createElement('span');
      quantity.className = 'cart-quantity-value';
      quantity.textContent = String(item.quantity);
      const plus = document.createElement('button');
      plus.type = 'button';
      plus.className = 'cart-quantity-button increase';
      plus.textContent = '+';
      plus.setAttribute('aria-label', `Increase ${item.item_name} quantity`);
      plus.disabled = Number(item.quantity) >= Number(item.stock_qty || 9999);
      plus.addEventListener('click', () => {
        requestCart[index].quantity = Math.min(Number(requestCart[index].stock_qty || 9999), 9999, Number(requestCart[index].quantity) + 1);
        persistCart();
      });
      const remove = document.createElement('button');
      remove.type = 'button';
      remove.className = 'cart-remove-button';
      remove.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 7h16M10 11v6M14 11v6M5 7l1 14h12l1-14M9 7V4h6v3"/></svg>';
      remove.setAttribute('aria-label', `Remove ${item.item_name} from request cart`);
      remove.addEventListener('click', () => {
        showConfirmation('Remove Item?', `Are you sure you want to remove ${item.item_name} from your request cart?`, 'Keep Item', 'Yes, Remove Item', () => {
          requestCart = requestCart.filter(cartItem => Number(cartItem.item_id) !== Number(item.item_id));
          persistCart();
        });
      });
      controls.append(minus, quantity, plus, remove);
      row.append(info, controls);
      cartList.append(row);

      if (cartReview) {
        const reviewRow = document.createElement('tr');
        [item.item_name, String(item.quantity), item.unit_name].forEach(value => {
          const cell = document.createElement('td');
          cell.textContent = value;
          reviewRow.append(cell);
        });
        cartReview.append(reviewRow);
      }
    });
    if (requestItemsField) requestItemsField.value = JSON.stringify(requestCart.map(item => ({ item_id: item.item_id, quantity: item.quantity })));
  };
  const showAddedPopup = () => {
    if (!addedPopup) return;
    clearTimeout(addedPopupTimer);
    addedPopup.hidden = false;
    addedPopupTimer = setTimeout(() => { addedPopup.hidden = true; }, 800);
  };
  document.querySelectorAll('[data-add-to-cart]').forEach(button => button.addEventListener('click', () => {
    const itemId = Number(button.dataset.itemId);
    const existing = requestCart.find(item => Number(item.item_id) === itemId);
    const stockQty = Number(button.dataset.itemStock || 0);
    if (existing) existing.quantity = Math.min(stockQty, 9999, Number(existing.quantity) + 1);
    else if (stockQty > 0) requestCart.push({ item_id: itemId, item_name: button.dataset.itemName, unit_name: button.dataset.itemUnit, quantity: 1, stock_qty: stockQty });
    persistCart();
    close(button);
    showAddedPopup();
  }));
  document.getElementById('open-request-cart')?.addEventListener('click', () => {
    renderCart();
    cartStep.hidden = false;
    reviewStep.hidden = true;
    open('request-cart-modal');
  });
  document.getElementById('review-cart-button')?.addEventListener('click', () => {
    renderCart();
    cartStep.hidden = true;
    reviewStep.hidden = false;
  });
  document.getElementById('back-to-cart')?.addEventListener('click', () => {
    cartStep.hidden = false;
    reviewStep.hidden = true;
  });
  const requestReviewForm = document.getElementById('review-request-form');
  let requestSubmitting = false;
  requestReviewForm?.addEventListener('submit', event => {
    if (requestSubmitting) return;
    event.preventDefault();
    requestSubmitting = true;
    const submitButton = document.getElementById('submit-cart-request');
    if (submitButton) submitButton.disabled = true;
    Promise.resolve(cartSaveQueue).then(() => requestReviewForm.submit());
  });
  const purpose = document.querySelector('#review-request-form textarea[name="notes"]');
  const purposeCount = document.getElementById('request-purpose-count');
  purpose?.addEventListener('input', () => { if (purposeCount) purposeCount.textContent = `${purpose.value.length}/255`; });
  document.querySelectorAll('[data-character-count]').forEach(field => {
    const counter = document.getElementById(field.dataset.characterCount);
    const updateCount = () => { if (counter) counter.textContent = `${field.value.length}/${field.maxLength}`; };
    field.addEventListener('input', updateCount);
    updateCount();
  });
  const submittedPopup = document.getElementById('request-submitted-modal');
  if (submittedPopup?.dataset.show === 'true') {
    requestCart = [];
    migrateSessionCart = false;
    sessionStorage.removeItem(cartKey);
    renderCart();
    open('request-submitted-modal');
  }
  renderCart();
  if (migrateSessionCart) persistCart();
  document.querySelectorAll('.modal-backdrop').forEach(backdrop => {
    backdrop.addEventListener('click', event => { if (event.target === backdrop) backdrop.classList.remove('visible'); });
  });
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape') {
      document.querySelectorAll('.modal-backdrop.visible').forEach(m => m.classList.remove('visible'));
      if (notificationPanel && !notificationPanel.hidden) setNotificationsOpen(false, true);
    }
  });

  document.querySelectorAll('[data-toggle-password]').forEach(button => button.addEventListener('click', () => {
    const field = document.getElementById(button.dataset.togglePassword);
    if (field) {
      const visible = field.classList.contains('password-masked');
      field.classList.toggle('password-masked', !visible);
      field.type = visible ? 'text' : 'password';
      button.classList.toggle('is-visible', visible);
      button.setAttribute('aria-pressed', String(visible));
      button.setAttribute('aria-label', visible ? 'Hide password' : 'Show password');
    }
  }));
  const loginForms = [...document.querySelectorAll('[data-login-panel]')];
  const rememberedLoginKey = role => 'inventory-system-remembered-login:' + role;
  const showLoginPanel = role => {
    loginForms.forEach(form => { form.hidden = form.dataset.loginPanel !== role; });
    document.querySelectorAll('[data-login-role]').forEach(button => {
      button.classList.toggle('active', button.dataset.loginRole === role);
    });
    const form = loginForms.find(item => item.dataset.loginPanel === role);
    const email = form?.querySelector('input[name="email"]');
    if (email && !email.defaultValue && !email.value) {
      email.value = localStorage.getItem(rememberedLoginKey(role)) || '';
    }
  };
  try {
    const legacySavedLogin = JSON.parse(localStorage.getItem('inventory-system-remembered-login') || 'null');
    if (legacySavedLogin?.role && legacySavedLogin?.email
      && !localStorage.getItem(rememberedLoginKey(legacySavedLogin.role))) {
      localStorage.setItem(rememberedLoginKey(legacySavedLogin.role), legacySavedLogin.email);
    }
    localStorage.removeItem('inventory-system-remembered-login');
  } catch {
    // Keep sign-in usable if the browser blocks local storage.
  }
  document.querySelectorAll('[data-login-role]').forEach(button => button.addEventListener('click', () => {
    showLoginPanel(button.dataset.loginRole);
  }));
  loginForms.forEach(loginForm => {
    const role = loginForm.dataset.loginPanel;
    const loginEmail = loginForm.querySelector('input[name="email"]');
    const rememberLogin = loginForm.querySelector('input[name="remember"]');
    const savedEmail = localStorage.getItem(rememberedLoginKey(role));
    if (savedEmail && !loginEmail.defaultValue && !loginEmail.value) loginEmail.value = savedEmail;
    rememberLogin?.addEventListener('change', () => {
      if (!rememberLogin.checked) localStorage.removeItem(rememberedLoginKey(role));
    });
    loginForm.addEventListener('submit', () => {
      if (rememberLogin?.checked && loginEmail.value.trim()) {
        localStorage.setItem(rememberedLoginKey(role), loginEmail.value.trim());
      } else {
        localStorage.removeItem(rememberedLoginKey(role));
      }
      Object.keys(sessionStorage).filter(key => key.startsWith('inventory-notifications-seen:')).forEach(key => sessionStorage.removeItem(key));
    });
  });
  document.querySelectorAll('[data-dismiss-notice]').forEach(button => button.addEventListener('click', () => button.closest('[data-notice]')?.remove()));

  const search = document.getElementById('table-search');
  const filter = document.getElementById('stock-filter');
  const categoryFilter = document.getElementById('category-filter');
  const rows = [...(document.querySelectorAll('#inventory-table tbody tr'))];
  const applyRows = () => rows.forEach(row => {
    const matchesText = !search || row.textContent.toLowerCase().includes(search.value.toLowerCase());
    const matchesStock = !filter || filter.value === 'all' || row.dataset.stock === filter.value;
    const matchesCategory = !categoryFilter || categoryFilter.value === 'all' || row.dataset.category === categoryFilter.value;
    row.hidden = !(matchesText && matchesStock && matchesCategory);
  });
  search?.addEventListener('input', applyRows);
  filter?.addEventListener('change', applyRows);
  categoryFilter?.addEventListener('change', applyRows);
  const inventoryStockParam = new URLSearchParams(window.location.search).get('stock');
  if (filter && ['low', 'out'].includes(inventoryStockParam)) filter.value = inventoryStockParam;
  applyRows();

  const requestsSearch = document.getElementById('requests-search');
  const requestsStatusFilter = document.getElementById('requests-status-filter');
  const requestsSort = document.getElementById('requests-sort');
  const requestsTable = document.getElementById('requests-table');
  const requestRows = [...(requestsTable?.querySelectorAll('tbody tr') || [])];
  const applyRequestFilters = () => {
    const query = requestsSearch?.value.trim().toLowerCase() || '';
    const status = requestsStatusFilter?.value || 'all';
    const direction = requestsSort?.dataset.order === 'asc' ? 1 : -1;
    requestRows.sort((a, b) => direction * (a.dataset.sortDate || '').localeCompare(b.dataset.sortDate || ''));
    requestRows.forEach(row => {
      row.hidden = !((!query || row.textContent.toLowerCase().includes(query)) &&
        (status === 'all' || row.dataset.status === status));
      requestsTable.querySelector('tbody').appendChild(row);
    });
  };
  requestsSearch?.addEventListener('input', applyRequestFilters);
  requestsStatusFilter?.addEventListener('change', applyRequestFilters);
  requestsSort?.addEventListener('click', () => {
    const order = requestsSort.dataset.order === 'asc' ? 'desc' : 'asc';
    requestsSort.dataset.order = order;
    requestsSort.setAttribute('aria-label', `Sort by date ${order === 'asc' ? 'ascending' : 'descending'}`);
    requestsSort.title = `Sort by date: ${order === 'asc' ? 'oldest first' : 'newest first'}`;
    const arrow = requestsSort.querySelector('b');
    if (arrow) {
      const direction = order === 'asc' ? 'M12 19V5m-7 7 7-7 7 7' : 'M12 5v14m-7-7 7 7 7-7';
      arrow.innerHTML = `<svg class="ui-icon sort-arrow" viewBox="0 0 24 24" aria-hidden="true"><path d="${direction}"/></svg>`;
    }
    applyRequestFilters();
  });
  const requestsStatusParam = new URLSearchParams(window.location.search).get('status');
  if (requestsStatusFilter && ['pending', 'approved', 'fulfilled', 'declined', 'cancelled'].includes(requestsStatusParam)) {
    requestsStatusFilter.value = requestsStatusParam;
  }
  applyRequestFilters();

  const transactionSearch = document.getElementById('transaction-search');
  const transactionTypeFilter = document.getElementById('transaction-type-filter');
  const transactionStatus = document.getElementById('transaction-status-filter');
  const transactionSort = document.getElementById('transaction-sort');
  const transactionsTable = document.getElementById('transactions-table');
  const transactionRows = [...(transactionsTable?.querySelectorAll('tbody tr[data-type]') || [])];
  const applyTransactionFilters = () => {
    const query = transactionSearch?.value.trim().toLowerCase() || '';
    const type = transactionTypeFilter?.value || 'all';
    const status = transactionStatus?.value || 'all';
    const direction = transactionSort?.dataset.order === 'asc' ? 1 : -1;
    transactionRows.sort((a, b) => direction * (a.dataset.sortDate || '').localeCompare(b.dataset.sortDate || ''));
    transactionRows.forEach(row => {
      row.hidden = !((!query || row.textContent.toLowerCase().includes(query)) &&
        (type === 'all' || row.dataset.type === type) &&
        (status === 'all' || row.dataset.status === status));
      transactionsTable.querySelector('tbody').appendChild(row);
    });
  };
  transactionSearch?.addEventListener('input', applyTransactionFilters);
  transactionTypeFilter?.addEventListener('change', applyTransactionFilters);
  transactionStatus?.addEventListener('change', applyTransactionFilters);
  transactionSort?.addEventListener('click', () => {
    const order = transactionSort.dataset.order === 'asc' ? 'desc' : 'asc';
    transactionSort.dataset.order = order;
    transactionSort.setAttribute('aria-label', `Sort by date ${order === 'asc' ? 'ascending' : 'descending'}`);
    transactionSort.title = `Sort by date: ${order === 'asc' ? 'oldest first' : 'newest first'}`;
    const arrow = transactionSort.querySelector('b');
    if (arrow) {
      const direction = order === 'asc' ? 'M12 19V5m-7 7 7-7 7 7' : 'M12 5v14m-7-7 7 7 7-7';
      arrow.innerHTML = `<svg class="ui-icon sort-arrow" viewBox="0 0 24 24" aria-hidden="true"><path d="${direction}"/></svg>`;
    }
    applyTransactionFilters();
  });
  applyTransactionFilters();

  document.querySelectorAll('[data-confirm]').forEach(form => form.addEventListener('submit', event => {
    if (!window.confirm(form.dataset.confirm)) event.preventDefault();
  }));
  document.querySelectorAll('tr').forEach(row => {
    if (row.querySelector('.status-chip.pending')) {
      const fulfill = row.querySelector('.tiny-button.fulfill');
      if (fulfill) { fulfill.disabled = true; fulfill.title = 'Approve this request first'; }
    }
  });
  const transactionType = document.getElementById('transaction-type');
  const supplierField = document.getElementById('stock-supplier-field');
  const stockItemSelect = document.getElementById('stock-item-select');
  const stockStorageLocation = document.getElementById('stock-storage-location');
  const stockUnitCost = document.getElementById('stock-unit-cost');
  const stockUnitSelect = document.getElementById('stock-unit-select');
  const updateSelectedStockItem = () => {
    const option = stockItemSelect?.selectedOptions[0];
    if (stockStorageLocation) stockStorageLocation.value = option?.dataset.location || '';
    if (stockUnitCost) stockUnitCost.value = option?.dataset.cost || '';
    if (stockUnitSelect) {
      const unit = option?.dataset.unit || '';
      stockUnitSelect.replaceChildren(new Option(unit || 'Select item first', unit));
      stockUnitSelect.disabled = !unit;
    }
  };
  const updateSupplier = () => {
    if (!transactionType || !supplierField) return;
    supplierField.hidden = transactionType.value !== 'Stock In';
    const select = supplierField.querySelector('select');
    if (select) select.required = transactionType.value === 'Stock In';
  };
  transactionType?.addEventListener('change', updateSupplier);
  stockItemSelect?.addEventListener('change', updateSelectedStockItem);
  updateSupplier();
  updateSelectedStockItem();
  document.getElementById('new-role')?.addEventListener('change', event => {
    const field = document.getElementById('department-field');
    if (field) field.hidden = event.target.value === 'admin';
  });
  const menu = document.getElementById('menu-toggle');
  menu?.addEventListener('click', () => document.getElementById('sidebar')?.classList.toggle('open'));
});
