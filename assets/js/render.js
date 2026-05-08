function getOrdersScrollSnapshot() {
            const scroller = document.getElementById('orders-scroll');
            if (!scroller) return null;
            return {
                top: scroller.scrollTop,
                left: scroller.scrollLeft
            };
        }

        function restoreOrdersScrollSnapshot(snapshot) {
            if (!snapshot) return;
            requestAnimationFrame(() => {
                const scroller = document.getElementById('orders-scroll');
                if (!scroller) return;
                scroller.scrollTop = snapshot.top;
                scroller.scrollLeft = snapshot.left;
            });
        }

        function renderKeepScroll() {
            const snapshot = getOrdersScrollSnapshot();
            render();
            restoreOrdersScrollSnapshot(snapshot);
        }

        function scrollOrdersToBottom() {
            requestAnimationFrame(() => {
                const scroller = document.getElementById('orders-scroll');
                if (!scroller) return;
                scroller.scrollTop = scroller.scrollHeight;
            });
        }

        function renderScrollBottom() {
            render();
            scrollOrdersToBottom();
        }

        function updateHeaderSummary() {
            const label = document.getElementById('order-count-label');
            if (!label) return;
            label.textContent = appState.orders.length > 0 ? `${appState.orders.length} 个订单` : 'rules-engine / exact-match';
        }

        function syncComposerFromState() {
            const textarea = document.getElementById('input-textarea');
            const submitBtn = document.getElementById('submit-btn');
            if (textarea) {
                textarea.value = appState.inputText;
                textarea.style.height = 'auto';
                textarea.style.height = Math.min(textarea.scrollHeight || 44, 200) + 'px';
            }
            if (submitBtn) {
                submitBtn.disabled = !appState.inputText.trim() || appState.isProcessing;
            }
        }

        function getPhoneCounts() {
            const phoneCounts = {};
            appState.orders.forEach(o => {
                const p = String(o.phone || '').trim();
                if (p) phoneCounts[p] = (phoneCounts[p] || 0) + 1;
            });
            return phoneCounts;
        }

        function replaceOrderCard(orderId) {
            const grid = document.getElementById('orders-grid');
            if (!grid) {
                renderKeepScroll();
                return;
            }

            const index = appState.orders.findIndex(o => String(o.id) === String(orderId));
            if (index < 0) return;

            const order = appState.orders[index];
            const phoneCounts = getPhoneCounts();
            const isDuplicate = order.phone && phoneCounts[String(order.phone).trim()] > 1;
            const nextCard = OrderCard(order, index, appState.globalOptions, updateOrder, confirmDeleteOrder, isDuplicate, false);
            const oldCard = grid.querySelector(`[data-order-id="${String(orderId)}"]`);

            if (oldCard) {
                oldCard.replaceWith(nextCard);
            } else {
                grid.appendChild(nextCard);
            }

            // 🌟 核心改进：恢复焦点
            if (appState.openDropdown) {
                const input = nextCard.querySelector(`input[data-key="${appState.openDropdown}"]`);
                if (input) {
                    const len = input.value.length;
                    input.focus();
                    input.setSelectionRange(len, len);
                }
            }

            nextCard.querySelectorAll('.note-textarea').forEach(autoResizeNote);
        }

        let pendingOrderCardIds = new Set();
        let pendingCardFrame = null;
        function scheduleOrderCardRefresh(orderId) {
            pendingOrderCardIds.add(orderId);
            if (pendingCardFrame) return;
            pendingCardFrame = requestAnimationFrame(() => {
                const ids = Array.from(pendingOrderCardIds);
                pendingOrderCardIds.clear();
                pendingCardFrame = null;
                ids.forEach(replaceOrderCard);
            });
        }

        function scheduleRelatedOrderCardRefresh(orderId) {
            const order = appState.orders.find(o => String(o.id) === String(orderId));
            const phone = String(order?.phone || '').trim();
            if (!phone) {
                scheduleOrderCardRefresh(orderId);
                return;
            }
            appState.orders
                .filter(o => String(o.phone || '').trim() === phone)
                .forEach(o => scheduleOrderCardRefresh(o.id));
        }

        function appendNewOrderCards(startIndex, newOrders) {
            const grid = document.getElementById('orders-grid');
            if (!grid) {
                renderScrollBottom();
                return;
            }
            const phoneCounts = getPhoneCounts();
            newOrders.forEach((order, offset) => {
                const isDuplicate = order.phone && phoneCounts[String(order.phone).trim()] > 1;
                grid.appendChild(OrderCard(order, startIndex + offset, appState.globalOptions, updateOrder, confirmDeleteOrder, isDuplicate, true));
            });
            updateHeaderSummary();
            scrollOrdersToBottom();
        }

        function getOrderIdFromDropdownKey(key) {
            const match = String(key || '').match(/^order-(.+?)-/);
            return match ? match[1] : '';
        }

        function refreshDropdownCards(...keys) {
            const ids = new Set(keys.map(getOrderIdFromDropdownKey).filter(Boolean));
            if (!ids.size) {
                renderKeepScroll();
                return;
            }
            ids.forEach(id => scheduleOrderCardRefresh(id));
        }

        function refreshOrderAfterFieldChange(orderId, field, oldPhone = '') {
            if (field === 'phone') {
                const ids = new Set([String(orderId)]);
                const nextOrder = appState.orders.find(o => String(o.id) === String(orderId));
                const newPhone = String(nextOrder?.phone || '').trim();
                appState.orders.forEach(o => {
                    const phone = String(o.phone || '').trim();
                    if ((oldPhone && phone === oldPhone) || (newPhone && phone === newPhone)) {
                        ids.add(String(o.id));
                    }
                });
                ids.forEach(id => scheduleOrderCardRefresh(id));
                return;
            }
            scheduleOrderCardRefresh(orderId);
        }

        // 渲染应用
        function render() {
            document.documentElement.setAttribute('data-theme', appState.theme || 'dark');
            applyBackgroundImage();
            const root = document.getElementById('root');
            root.innerHTML = '';
            root.className = 'cc-shell';

            // 查重逻辑
            const phoneCounts = getPhoneCounts();

            // Header
            const header = document.createElement('header');
            header.className = 'cc-header sticky top-0 z-50';
            header.innerHTML = `
                <div class="px-4 h-14 flex items-center justify-between">
                    <div class="flex items-center gap-3">
                        <div class="cc-logo">✦</div>
                        <div>
                            <h1 class="cc-title text-sm font-semibold">订单助手</h1>
                            <p id="order-count-label" class="cc-subtitle text-xs">${appState.orders.length > 0 ? `${appState.orders.length} 个订单` : 'rules-engine / exact-match'}</p>
                        </div>
                    </div>
                    <div class="flex items-center gap-2">
                        <button onclick="openAiSettings()" class="cc-chip" title="设置" style="width:34px;height:34px;padding:0;justify-content:center;">
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>
                        </button>
                        <button onclick="toggleTheme()" class="cc-chip" title="${appState.theme === 'dark' ? '切换为白天模式' : '切换为夜间模式'}" style="width:34px;height:34px;padding:0;justify-content:center;">
                            ${appState.theme === 'dark'
                                ? `<svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor" stroke="none"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>`
                                : `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/></svg>`
                            }
                        </button>
                        ${appState.orders.length > 0 ? `
                            <button onclick="clearAllOrders()" class="cc-chip cc-chip-danger text-sm">
                                清空列表
                            </button>
                            <button onclick="exportToExcel()" class="cc-chip cc-chip-primary text-sm">
                                下载表格
                            </button>
                        ` : ''}
                    </div>
                </div>
            `;

            // Content
            const content = document.createElement('div');
            content.id = 'orders-scroll';
            content.className = 'flex-1 overflow-y-auto';
            content.style.height = 'calc(100vh - 56px - 84px)';

            const contentInner = document.createElement('div');
            contentInner.className = 'max-w-[1800px] mx-auto px-4 py-6';

            if (appState.orders.length === 0) {
                contentInner.appendChild(WelcomeScreen());
            } else {
                const grid = document.createElement('div');
                grid.id = 'orders-grid';
                grid.className = 'grid grid-cols-1 lg:grid-cols-2 gap-4';
                appState.orders.forEach((order, index) => {
                    const isDuplicate = order.phone && phoneCounts[String(order.phone).trim()] > 1;
                    grid.appendChild(OrderCard(order, index, appState.globalOptions, updateOrder, confirmDeleteOrder, isDuplicate));
                });
                contentInner.appendChild(grid);
            }

            content.appendChild(contentInner);

            // Input
            const inputSection = document.createElement('div');
            inputSection.className = 'cc-input-area sticky bottom-0';
            inputSection.innerHTML = `
                <div class="max-w-7xl mx-auto px-4 py-2">
                    <div class="cc-composer flex items-center gap-2 p-1.5">
                        <div class="flex-1 relative">
                            <textarea
                                id="input-textarea"
                                placeholder="粘贴订单文本，自动识别..."
                                class="w-full min-h-[34px] max-h-[120px] resize-none border-0 px-3 py-[7px] text-[13px] focus:outline-none"
                                ${appState.isProcessing ? 'disabled' : ''}
                                rows="1"
                            >${appState.inputText}</textarea>
                        </div>
                        <button
                            id="submit-btn"
                            ${!appState.inputText.trim() || appState.isProcessing ? 'disabled' : ''}
                            class="cc-send h-[34px] px-3 min-w-[58px] flex items-center justify-center disabled:opacity-50 disabled:cursor-not-allowed"
                        >
                            ${appState.isProcessing ? '<div class="loader" style="width: 18px; height: 18px;"></div>' : '发送 ↵'}
                        </button>
                    </div>
                    <p class="hidden md:block text-[11px] text-gray-400 mt-1 text-center leading-none">
                        粘贴自动识别 · Enter 发送 · Shift + Enter 换行
                    </p>
                </div>
            `;

            root.appendChild(header);
            root.appendChild(content);
            root.appendChild(inputSection);

            // 事件监听
            const textarea = document.getElementById('input-textarea');
            const submitBtn = document.getElementById('submit-btn');

            textarea.addEventListener('input', (e) => {
                appState.inputText = e.target.value;
                e.target.style.height = 'auto';
                e.target.style.height = Math.min(e.target.scrollHeight, 200) + 'px';
                submitBtn.disabled = !appState.inputText.trim() || appState.isProcessing;
            });

            textarea.addEventListener('paste', (e) => {
                const pastedText = e.clipboardData.getData('text');
                if (pastedText.trim()) {
                    e.preventDefault();
                    handleSubmitText(pastedText);
                }
            });

            textarea.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    if (appState.inputText.trim() && !appState.isProcessing) {
                        handleSubmitText(appState.inputText);
                    }
                }
            });

            submitBtn.addEventListener('click', () => {
                if (appState.inputText.trim() && !appState.isProcessing) {
                    handleSubmitText(appState.inputText);
                }
            });

            document.querySelectorAll('.note-textarea').forEach(autoResizeNote);
        }

        // 初始化
        document.addEventListener('click', (e) => {
            // 🌟 核心修复：如果点击的是下拉框内部（输入框或菜单），则不触发全局关闭逻辑
            if (e.target.closest('.cc-select')) return;

            if (appState.openDropdown) {
                const previousKey = appState.openDropdown;
                const input = document.querySelector(`input[data-key="${previousKey}"]`);
                if (input) saveManualEntry(input);
                
                appState.openDropdown = '';
                appState.dropdownSearch = '';
                refreshDropdownCards(previousKey);
            }
        });
