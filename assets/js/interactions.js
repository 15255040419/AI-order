// --- 全局交互函数 ---

        window.updateCustomerLink = async (orderId, matchedAccountCode) => {
            const order = appState.orders.find(o => o.id === orderId);
            if (!order) return;

            // 如果原本识别出的账号不等于新选的账号，则触发学习
            if (order.account && order.account !== matchedAccountCode) {
                console.log(`🧠 系统正在同步学习客户关联: ${order.account} -> ${matchedAccountCode}`);
                try {
                    await fetch(`${BACKEND_BASE_URL}/learn`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            type: 'customer',
                            rawName: order.account,
                            matchedName: matchedAccountCode
                        })
                    });
                } catch (e) {
                    console.error('学习同步失败:', e);
                }
            }
            updateOrder(orderId, 'account', matchedAccountCode);
        };

        window.toggleTheme = () => {
            appState.theme = appState.theme === 'dark' ? 'light' : 'dark';
            localStorage.setItem('order-helper-theme', appState.theme);
            renderKeepScroll();
        };

        window.saveManualEntry = (el) => {
            if (!el) return;
            const id = el.getAttribute('data-order-id');
            const field = el.getAttribute('data-field');
            const value = el.value;
            
            if (!id || !field) return;

            let finalValue = value;
            let options = [];
            if (field === 'salesman') options = appState.globalOptions.salesmen;
            else if (field === 'express') options = appState.globalOptions.expressOptions;
            else if (field === 'receipt') options = appState.globalOptions.receipts;
            else if (field.startsWith('prod-')) {
                const idx = parseInt(field.split('-')[1]);
                updateProduct(parseInt(id), idx, 'matchedName', value);
                return;
            }
            
            if (options.length > 0 && value) {
                finalValue = window.findBestMatch(options, value);
            }
            updateOrder(parseInt(id), field, finalValue);
        };

        window.handleSelectFocus = (key, value) => {
            if (appState.openDropdown === key) return;
            appState.openDropdown = key;
            appState.dropdownSearch = '';
            refreshDropdownCards(key);
        };

        window.handleSelectInput = (key, value) => {
            appState.dropdownSearch = value;
            refreshDropdownCards(key);
        };

        window.toggleDropdown = (key) => {
            const previousKey = appState.openDropdown;
            if (previousKey) {
                const input = document.querySelector(`input[data-key="${previousKey}"]`);
                if (input) saveManualEntry(input);
            }
            appState.openDropdown = previousKey === key ? '' : key;
            appState.dropdownSearch = '';
            refreshDropdownCards(previousKey, appState.openDropdown);
        };

        window.selectOrderOption = (id, field, value) => {
            appState.openDropdown = '';
            appState.dropdownSearch = '';
            if (field.startsWith('prod-')) {
                const idx = parseInt(field.split('-')[1]);
                updateProduct(id, idx, 'matchedName', value);
            } else {
                updateOrder(id, field, value);
            }
        };

        window.autoResizeNote = (el) => {
            el.style.height = '40px';
            el.style.height = `${Math.max(40, el.scrollHeight)}px`;
        };

        window.updateOrder = (id, field, value) => {
            const oldOrder = appState.orders.find(o => o.id === id);
            const oldPhone = String(oldOrder?.phone || '').trim();
            appState.orders = appState.orders.map(o => {
                if (o.id === id) {
                    let newOrder = { ...o, [field]: value };

                    // 🌟 联动A: 结算方式设为欠款 -> 清空收款人
                    if (field === 'payMethod' && value === '欠款计应收') {
                        newOrder.receipt = '';
                    }
                    // 🌟 联动B: 选了/取消收款人
                    if (field === 'receipt') {
                        if (value !== '') {
                            newOrder.payMethod = '银行收款'; // 选了账户 -> 银行收款
                        } else {
                            newOrder.payMethod = '欠款计应收'; // 清空账户 -> 欠款计应收
                        }
                    }

                    // 🌟 联动C: 快递修改触发学习
                    if (field === 'express' && value) {
                        const key = o.receiver || o.address;
                        if (key && o.express.includes('待定')) {
                            console.log(`🧠 系统正在同步学习快递规则: ${key} -> ${value}`);
                            learnCorrection('express', key, value);
                        }
                    }

                    if (field === 'freight' || field === 'total') {
                        const prodSum = o.products.reduce((sum, p) => sum + (parseFloat(p.price || 0) * parseInt(p.qty || 1)), 0);
                        if (field === 'freight') {
                            newOrder.total = prodSum + parseFloat(value || 0);
                        }
                    }
                    return newOrder;
                }
                return o;
            });
            refreshOrderAfterFieldChange(id, field, oldPhone);
        };

        window.updateProduct = (orderId, productIndex, field, value) => {
            appState.orders = appState.orders.map(o => {
                if (o.id === orderId) {
                    const products = [...o.products];
                    const p = { ...products[productIndex], [field]: value };

                    // 1. 同步库存元数据
                    if (field === 'matchedName') {
                        const oldMatch = products[productIndex].matchedName;
                        const searchName = p.name || p.searchName;
                        if (appState.globalOptions.allProductsData) {
                            const info = appState.globalOptions.allProductsData.find(s =>
                                String(s['货品名称']).trim() === String(value).trim()
                            );
                            if (info) {
                                p.productInfo = info;
                                // 🌟 关键同步：把查到的原始列信息填进我们的标准字段里
                                p.spec_no = info['规格编号'] || info['货品代码'] || info['编码'] || info['货品编号'] || '';
                                p.item_no = info['货品编号'] || info['货品代码'] || info['商品编号'] || '';
                                p.barcode = info['条码'] || info['货品条码'] || info['商品条码'] || '';
                                p.spec = info['规格'] || info['货品规格'] || info['型号规格'] || '';
                                p.needsReview = false;
                                p.matchStatus = 'matched';
                                p.matchType = 'manual';
                            }
                        }
                        if (value && value !== oldMatch && searchName) {
                            learnCorrection('product', searchName, value, o.account);
                        }
                    }

                    products[productIndex] = p;
                    const newOrder = { ...o, products };

                    // 🌟 核心逻辑：如果修改的是价格或数量，则自动更新合计
                    if (field === 'price' || field === 'qty' || field === 'matchedName') {
                        const prodSum = products.reduce((sum, item) => sum + (parseFloat(item.price || 0) * parseInt(item.qty || 1)), 0);
                        newOrder.total = prodSum + parseFloat(o.freight || 0);
                    }

                    return newOrder;
                }
                return o;
            });
            scheduleOrderCardRefresh(orderId);
        };

        window.applyProductInfo = (orderId, productIndex, productDataIndex) => {
            const info = appState.globalOptions.allProductsData?.[productDataIndex];
            if (!info) return;

            appState.orders = appState.orders.map(o => {
                if (o.id !== orderId) return o;
                const products = [...o.products];
                const oldProduct = products[productIndex] || {};
                const productInfo = info.productInfo || info;
                products[productIndex] = {
                    ...oldProduct,
                    matchedName: info['货品名称'] || info.name || '',
                    productInfo,
                    spec_no: info['规格编号'] || info['货品代码'] || info['编码'] || '',
                    item_no: info['货品编号'] || info['货品代码'] || info['商品编号'] || info.item_no || '',
                    barcode: info['条码'] || info['货品条码'] || info['商品条码'] || '',
                    spec: info['规格'] || info['货品规格'] || info['型号规格'] || '',
                    needsReview: false,
                    matchStatus: 'matched',
                    matchType: 'manual'
                };
                const prodSum = products.reduce((sum, item) => sum + (parseFloat(item.price || 0) * parseInt(item.qty || 1)), 0);
                return { ...o, products, total: prodSum + parseFloat(o.freight || 0) };
            });
            scheduleOrderCardRefresh(orderId);
        };

        async function learnCorrection(type, rawName, matchedName, customer) {
            try {
                await fetch(`${BACKEND_BASE_URL}/learn`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ type, rawName, matchedName, customer })
                });
                console.log(`💡 系统进步 [${type}]：记录了 ${rawName} -> ${matchedName} (客户: ${customer || '未知'})`);
                fetchOptions();
            } catch (e) { console.error('Learning Failed', e); }
        }

        window.confirmDeleteOrder = (id) => {
            showConfirmDialog(
                '确认删除此订单？',
                '删除后无法恢复，请确认是否继续。',
                () => {
                    appState.orders = appState.orders.filter(o => o.id !== id);
                    renderKeepScroll();
                    toast.success('订单已删除');
                }
            );
        };

        window.toggleProducts = (orderId) => {
            const productsDiv = document.getElementById(`products-${orderId}`);
            const chevron = document.getElementById(`chevron-${orderId}`);
            if (productsDiv.style.display === 'none') {
                productsDiv.style.display = 'block';
                chevron.innerHTML = icons.chevronUp;
            } else {
                productsDiv.style.display = 'none';
                chevron.innerHTML = icons.chevronDown;
            }
        };

        // 🌟 新增：全库货品精准搜索弹窗 (支持名称与规格编号双向搜索)
        window.openProductSearch = (orderId, productIndex) => {
            const modalRoot = document.getElementById('modal-root');
            const modal = document.createElement('div');
            modal.className = 'modal-overlay';

            let allProdsData = appState.globalOptions.allProductsData || [];

            modal.innerHTML = `
                <div class="modal-content" style="max-width: 600px; max-height: 80vh; display: flex; flex-direction: column; padding: 20px;">
                    <div class="flex justify-between items-center mb-4">
                        <div class="flex items-center gap-3">
                            <h3 class="text-lg font-bold text-gray-900">货品全库精准搜索</h3>
                            <button onclick="fetchOptions().then(() => { modal.remove(); openProductSearch(orderId, productIndex); toast.success('数据同步成功'); })" class="cc-icon-glass text-[10px] px-2 py-0.5 text-blue-700 rounded-md flex items-center gap-1">
                                🔄 强制同步最新库存
                            </button>
                        </div>
                        <button id="close-search-btn" class="cc-icon-glass text-gray-400 p-1 rounded-md">${icons.trashSmall}</button>
                    </div>
                    
                    <div class="relative mb-4">
                        <input type="text" id="prod-search-input" placeholder="搜索货品名称 或 规格编号..." class="w-full h-10 px-10 border-2 border-blue-500 rounded-xl focus:outline-none shadow-sm text-[14px]" autocomplete="off" />
                        <div class="absolute left-3 inset-y-0 flex items-center text-blue-500">${icons.search}</div>
                    </div>

                    <div id="search-results" class="flex-1 overflow-y-auto min-h-[300px] border border-gray-100 rounded-lg bg-gray-50/30">
                        <div class="p-8 text-center text-gray-400 text-sm">
                            请输入名称或编号进行快速匹配...
                        </div>
                    </div>
                    
                    <div class="mt-4 pt-4 border-t border-gray-100 text-[11px] text-gray-400 flex justify-between items-center">
                        <span>总库存数: ${allProdsData.length} 项</span>
                        <span>支持 规格编号 搜索</span>
                    </div>
                </div>
            `;
            modalRoot.appendChild(modal);

            const input = modal.querySelector('#prod-search-input');
            const resultsDiv = modal.querySelector('#search-results');
            input.focus();

            const renderResults = (list) => {
                if (list.length === 0) {
                    resultsDiv.innerHTML = `<div class="p-8 text-center text-gray-400 text-sm">未找到匹配项</div>`;
                    return;
                }
                resultsDiv.innerHTML = list.map(item => `
                    <div class="search-item p-3 border-b border-gray-100 hover:bg-blue-50 cursor-pointer transition-colors flex justify-between items-center group" data-index="${item.dataIndex}" data-name="${item.name}">
                        <div class="flex flex-col">
                            <span class="text-[13px] font-bold text-gray-800 group-hover:text-blue-700">${item.name}</span>
                            <span class="text-[11px] text-blue-500 font-mono">规格编号: ${item['规格编号'] || '--'}　货品编号: ${item['货品编号'] || '--'}　条码: ${item['条码'] || '--'}</span>
                            <span class="text-[11px] text-gray-400">规格: ${item['规格'] || '--'}</span>
                        </div>
                        <span class="text-blue-400 opacity-0 group-hover:opacity-100">${icons.checkCircle}</span>
                    </div>
                `).join('');

                resultsDiv.querySelectorAll('.search-item').forEach(item => {
                    item.onclick = () => {
                        applyProductInfo(orderId, productIndex, parseInt(item.dataset.index));
                        modal.remove();
                        toast.success(`已关联货品: ${item.dataset.name}`);
                    };
                });
            };

            input.oninput = (e) => {
                const kw = e.target.value.trim().toUpperCase();
                if (!kw) {
                    renderResults([]);
                    return;
                }
                const matched = allProdsData.map((p, dataIndex) => ({ ...p, dataIndex })).filter(p => {
                    const searchStr = `${p.name} ${p.item_no} ${p['规格编号'] || ''} ${p['货品编号'] || ''} ${p['条码'] || ''} ${p['规格'] || ''}`.toUpperCase();
                    return searchStr.includes(kw);
                }).slice(0, 100);
                renderResults(matched);
            };

            modal.querySelector('#close-search-btn').onclick = () => modal.remove();
            modal.onclick = (e) => { if (e.target === modal) modal.remove(); };
            document.onkeydown = (e) => { if (e.key === 'Escape') modal.remove(); };
        };
