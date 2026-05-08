// 动画角色组件
        function AnimatedCharacters() {
            const container = document.createElement('div');
            container.style.cssText = 'position: relative; width: 480px; height: 360px; margin: 0 auto; perspective: 1000px;';

            // 紫色矩形角色
            const purple = document.createElement('div');
            purple.className = 'character-purple';
            purple.style.cssText = 'position: absolute; bottom: 0; left: 60px; width: 170px; height: 370px; background: #6c3ff5; border-radius: 10px 10px 0 0; z-index: 1; transform-origin: bottom center; transition: transform 0.7s ease-in-out;';
            purple.innerHTML = `
                <div style="position: absolute; left: 45px; top: 40px; display: flex; gap: 28px; transition: all 0.7s ease-in-out;">
                    <div class="eye" style="width: 18px; height: 18px; border-radius: 50%; background: white; display: flex; align-items: center; justify-content: center; overflow: hidden;">
                        <div class="pupil" style="width: 7px; height: 7px; border-radius: 50%; background: #2d2d2d; transition: transform 0.1s;"></div>
                    </div>
                    <div class="eye" style="width: 18px; height: 18px; border-radius: 50%; background: white; display: flex; align-items: center; justify-content: center; overflow: hidden;">
                        <div class="pupil" style="width: 7px; height: 7px; border-radius: 50%; background: #2d2d2d; transition: transform 0.1s;"></div>
                    </div>
                </div>
            `;

            // 黑色矩形角色
            const black = document.createElement('div');
            black.className = 'character-black';
            black.style.cssText = 'position: absolute; bottom: 0; left: 220px; width: 115px; height: 290px; background: #2d2d2d; border-radius: 8px 8px 0 0; z-index: 2; transform-origin: bottom center; transition: transform 0.7s ease-in-out;';
            black.innerHTML = `
                <div style="position: absolute; left: 26px; top: 32px; display: flex; gap: 20px; transition: all 0.7s ease-in-out;">
                    <div class="eye" style="width: 16px; height: 16px; border-radius: 50%; background: white; display: flex; align-items: center; justify-content: center; overflow: hidden;">
                        <div class="pupil" style="width: 6px; height: 6px; border-radius: 50%; background: #2d2d2d; transition: transform 0.1s;"></div>
                    </div>
                    <div class="eye" style="width: 16px; height: 16px; border-radius: 50%; background: white; display: flex; align-items: center; justify-content: center; overflow: hidden;">
                        <div class="pupil" style="width: 6px; height: 6px; border-radius: 50%; background: #2d2d2d; transition: transform 0.1s;"></div>
                    </div>
                </div>
            `;

            // 橙色半圆角色
            const orange = document.createElement('div');
            orange.className = 'character-orange';
            orange.style.cssText = 'position: absolute; bottom: 0; left: 0; width: 230px; height: 190px; background: #ff9b6b; border-radius: 115px 115px 0 0; z-index: 3; transform-origin: bottom center; transition: transform 0.7s ease-in-out;';
            orange.innerHTML = `
                <div style="position: absolute; left: 82px; top: 90px; display: flex; gap: 28px; transition: all 0.7s ease-in-out;">
                    <div class="pupil" style="width: 12px; height: 12px; border-radius: 50%; background: #2d2d2d; transition: transform 0.1s;"></div>
                    <div class="pupil" style="width: 12px; height: 12px; border-radius: 50%; background: #2d2d2d; transition: transform 0.1s;"></div>
                </div>
            `;

            // 黄色圆角色
            const yellow = document.createElement('div');
            yellow.className = 'character-yellow';
            yellow.style.cssText = 'position: absolute; bottom: 0; left: 290px; width: 135px; height: 215px; background: #e8d754; border-radius: 68px 68px 0 0; z-index: 4; transform-origin: bottom center; transition: transform 0.7s ease-in-out;';
            yellow.innerHTML = `
                <div style="position: absolute; left: 52px; top: 40px; display: flex; gap: 20px; transition: all 0.7s ease-in-out;">
                    <div class="pupil" style="width: 12px; height: 12px; border-radius: 50%; background: #2d2d2d; transition: transform 0.1s;"></div>
                    <div class="pupil" style="width: 12px; height: 12px; border-radius: 50%; background: #2d2d2d; transition: transform 0.1s;"></div>
                </div>
                <div class="mouth-line" style="position: absolute; left: 54px; top: 88px; width: 40px; height: 4px; background: #2d2d2d; border-radius: 2px; transition: all 0.7s ease-in-out;"></div>
            `;

            container.appendChild(purple);
            container.appendChild(black);
            container.appendChild(orange);
            container.appendChild(yellow);

            // 鼠标跟随动画
            window.addEventListener('mousemove', (e) => {
                const characters = [purple, black, orange, yellow];
                characters.forEach((char) => {
                    const rect = char.getBoundingClientRect();
                    const cx = rect.left + rect.width / 2;
                    const cy = rect.top + rect.height / 3;
                    const dx = e.clientX - cx;
                    const dy = e.clientY - cy;
                    const faceX = Math.max(-15, Math.min(15, dx / 20));
                    const faceY = Math.max(-10, Math.min(10, dy / 30));
                    const bodySkew = Math.max(-6, Math.min(6, -dx / 120));

                    char.style.transform = `skewX(${bodySkew}deg)`;

                    const faceContainer = char.querySelector('div[style*="transition"]');
                    const mouthLine = char.querySelector('.mouth-line');
                    if (faceContainer) {
                        const baseLeft = char === purple ? 45 : char === black ? 26 : char === orange ? 82 : 52;
                        const baseTop = char === purple ? 40 : char === black ? 32 : char === orange ? 90 : 40;
                        faceContainer.style.left = `${baseLeft + faceX}px`;
                        faceContainer.style.top = `${baseTop + faceY}px`;

                        // 🌟 如果是黄色小人，让它的横线嘴巴也跟着动 (修正基准点为 54px)
                        if (mouthLine) {
                            mouthLine.style.left = `${54 + faceX * 1.2}px`;
                            mouthLine.style.top = `${88 + faceY * 0.8}px`;
                        }
                    }

                    // 眼珠跟随
                    const pupils = char.querySelectorAll('.pupil');
                    pupils.forEach((pupil) => {
                        const pupilRect = pupil.getBoundingClientRect();
                        const pcx = pupilRect.left + pupilRect.width / 2;
                        const pcy = pupilRect.top + pupilRect.height / 2;
                        const pdx = e.clientX - pcx;
                        const pdy = e.clientY - pcy;
                        const maxDist = char === purple ? 4 : char === black ? 3.5 : 8;
                        const dist = Math.min(Math.sqrt(pdx * pdx + pdy * pdy), maxDist);
                        const angle = Math.atan2(pdy, pdx);
                        pupil.style.transform = `translate(${Math.cos(angle) * dist}px, ${Math.sin(angle) * dist}px)`;
                    });
                });
            });

            return container;
        }

        // 欢迎屏幕
        function WelcomeScreen() {
            const container = document.createElement('div');
            container.className = 'cc-welcome';
            container.style.minHeight = 'calc(100vh - 200px)';
            container.innerHTML = `
                <div class="cc-terminal">
                    <div class="cc-terminal-bar">
                        <span>order-helper / rules-engine</span>
                        <span>${new Date().toLocaleDateString()}</span>
                    </div>
                    <div class="cc-terminal-body">
                        <div><span style="color: var(--cc-accent);">></span> 粘贴订单原文，系统开始拆单</div>
                        <div><span style="color: var(--cc-accent);">></span> AI 只切割文本，货品和快递由本地规则查表</div>
                        <div><span style="color: var(--cc-accent);">></span> 普通货品查规格编号，收银机/一体称查组合装货品名称</div>
                        <div><span style="color: var(--cc-accent);">></span> 查不到会标记待确认，不自动猜 <span class="cc-cursor"></span></div>
                    </div>
                </div>
                <div class="grid grid-cols-1 md:grid-cols-3 gap-3 mt-4">
                    <div class="cc-card p-4">
                        <div class="text-xs cc-muted font-bold mb-1">PRODUCT</div>
                        <div class="text-sm font-bold">精确查表，不走模糊匹配</div>
                    </div>
                    <div class="cc-card p-4">
                        <div class="text-xs cc-muted font-bold mb-1">EXPRESS</div>
                        <div class="text-sm font-bold">按省份、重量、品类判定</div>
                    </div>
                    <div class="cc-card p-4">
                        <div class="text-xs cc-muted font-bold mb-1">EXPORT</div>
                        <div class="text-sm font-bold">订单表和货品表一键导出</div>
                    </div>
                </div>
            `;

            return container;
        }

        // 订单卡片
        function OrderCard(order, index, globalOptions, onUpdate, onDelete, isDuplicate = false, animate = true) {
            const card = document.createElement('div');
            card.className = `cc-card ${animate ? 'cc-card-enter' : ''} p-3 mb-3 transition-all ${isDuplicate ? 'duplicate-highlight' : ''}`;
            card.style.height = 'fit-content';
            card.dataset.orderId = String(order.id);

            if (order.loading) {
                card.innerHTML = `
                    <div class="cc-loading-card">
                        <div class="flex items-center gap-3 mb-5">
                            <div class="loader"></div>
                            <div>
                                <div class="cc-type-line text-sm">${escAttr(order.progressText || '订单已进入解析队列')}</div>
                                <div class="text-xs cc-muted mt-1">${escAttr(order.progressStep || 'streaming / rules-engine')}</div>
                            </div>
                        </div>
                        <div class="space-y-3">
                            <div class="cc-scan-row w-full"></div>
                            <div class="cc-scan-row"></div>
                            <div class="cc-scan-row"></div>
                        </div>
                    </div>
                `;
                return card;
            }

            if (order.status === 'error') {
                card.className = 'bg-red-50 rounded-xl p-4 border border-red-100 shadow-sm relative group mb-4';
                card.innerHTML = `
                    <div class="flex justify-between items-start mb-2">
                        <div class="flex items-center gap-2">
                            <span class="bg-red-200 text-red-800 text-[10px] font-bold px-2 py-0.5 rounded">ERROR</span>
                            <h3 class="font-bold text-red-800 text-sm">解析失败</h3>
                        </div>
                        <button onclick="confirmDeleteOrder(${order.id})" class="cc-icon-glass h-8 w-8 flex items-center justify-center text-red-400 rounded-full transition-all">
                            ${icons.trash}
                        </button>
                    </div>
                    <p class="text-xs text-red-600 font-mono break-all leading-relaxed bg-white/50 p-2 rounded border border-red-50">${order.message || '未知解析错误'}</p>
                `;
                return card;
            }

            // Content
            card.innerHTML = `
                    <div class="cc-card-head flex justify-between items-center -mx-3 -mt-3 mb-3 px-4 py-2 border-l-[5px]" style="border-left-color: var(--cc-accent);">
                        <div class="flex items-center gap-4">
                            <span class="text-[10px] font-black px-2 py-0.5 rounded-md" style="background: var(--cc-text); color: var(--cc-bg);">#${index + 1}</span>
                            <h3 class="font-bold text-lg tracking-tight">${order.receiver || '新订单'}</h3>
                        </div>
                        <div class="flex items-center gap-3">
                            ${isDuplicate ? `<span class="px-2 py-0.5 rounded-full border border-red-500/55 text-red-500 text-[11px] font-extrabold leading-[1.4]">重复订单</span>` : ''}
                            <button onclick="confirmDeleteOrder(${order.id})" class="cc-chip cc-chip-danger h-8 w-8 !px-0 justify-center">
                                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M3 6h18m-2 0v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6m3 0V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"/></svg>
                            </button>
                        </div>
                    </div>

                    <div class="space-y-2.5">
                        <!-- 第一排：收货核心与财务汇总 (4列等宽) -->
                        <div class="grid grid-cols-2 md:grid-cols-4 gap-2">
                            <div class="space-y-0.5">
                                <label class="text-[11px] font-bold text-gray-400 uppercase tracking-wider">收货人</label>
                                <input type="text" value="${order.receiver || ''}" onchange="updateOrder(${order.id}, 'receiver', this.value)" class="w-full h-8 text-[13px] px-2 border border-gray-200 rounded-lg focus:outline-none focus:border-blue-500 bg-white text-gray-800 font-bold" />
                            </div>
                            <div class="space-y-0.5">
                                <label class="text-[11px] font-bold text-gray-400 uppercase tracking-wider">手机号</label>
                                <input type="text" value="${order.phone || ''}" onchange="updateOrder(${order.id}, 'phone', this.value)" class="w-full h-8 text-[13px] px-2 border border-gray-200 rounded-lg focus:outline-none focus:border-blue-500 bg-white text-gray-800 font-bold" />
                            </div>
                            <div class="space-y-0.5">
                                <label class="text-[11px] font-bold text-gray-400 uppercase tracking-wider">应收合计</label>
                                <input type="number" value="${order.total || 0}" onchange="updateOrder(${order.id}, 'total', this.value)" class="w-full h-8 text-[13px] px-2 border border-gray-200 rounded-lg focus:outline-none focus:border-blue-500 bg-white font-black text-blue-600 text-center" />
                            </div>
                            <div class="space-y-0.5">
                                <label class="text-[11px] font-bold text-gray-400 uppercase tracking-wider">应收邮费</label>
                                <input type="number" value="${order.freight || 0}" onchange="updateOrder(${order.id}, 'freight', this.value)" class="w-full h-8 text-[13px] px-2 border border-gray-200 rounded-lg focus:outline-none focus:border-blue-500 bg-white text-gray-800 text-center" />
                            </div>
                        </div>

                        <!-- 第二排：地址 (独占一行) -->
                        <div class="space-y-0.5">
                            <label class="text-[11px] font-bold text-gray-400 uppercase tracking-wider">收货地址</label>
                            <input type="text" value="${order.address || ''}" onchange="updateOrder(${order.id}, 'address', this.value)" class="w-full h-8 text-[13px] px-2 border border-gray-200 rounded-lg focus:outline-none focus:border-blue-500 bg-white text-gray-800 font-medium" />
                        </div>

                        <!-- 第三排：客户账号 (1/2) + 结算方式 (1/4) + 收款账户 (1/4) -->
                        <div class="grid grid-cols-4 gap-2 py-2 border-y border-dashed border-gray-100">
                             <div class="col-span-2 space-y-0.5">
                                <label class="text-[11px] font-bold text-gray-400 uppercase tracking-wider">客户账号</label>
                                <input type="text" value="${order.account || ''}" onchange="updateOrder(${order.id}, 'account', this.value)" class="w-full h-8 text-[13px] px-2 border border-gray-200 rounded-lg bg-white focus:outline-none focus:ring-1 focus:ring-blue-500 font-bold text-gray-800" />
                            </div>
                            <div class="col-span-1 space-y-0.5">
                                <label class="text-[11px] font-bold text-gray-400 uppercase tracking-wider">结算方式</label>
                                ${customSelect(`order-${order.id}-payMethod`, 'payMethod', order.payMethod || '银行收款', ['银行收款', '欠款计应收'], '-- 选择方式 --', order.id)}
                            </div>
                            <div class="col-span-1 space-y-0.5">
                                <label class="text-[11px] font-bold text-gray-400 uppercase tracking-wider">收款账户</label>
                                ${(() => {
                                    const receipts = [...globalOptions.receipts];
                                    if (order.receipt && !receipts.includes(order.receipt)) receipts.push(order.receipt);
                                    return customSelect(`order-${order.id}-receipt`, 'receipt', order.receipt || '', receipts, '-- 选择账户 --', order.id);
                                })()}
                            </div>
                        </div>

                        <!-- 第四排：物流相关与业务员；有单号时才显示物流单号 -->
                        <div class="grid ${order.trackingNumber ? 'grid-cols-3' : 'grid-cols-2'} gap-2 py-1">
                            <div class="space-y-0.5">
                                <label class="text-[11px] font-bold text-gray-400 uppercase tracking-wider">业务员</label>
                                ${customSelect(`order-${order.id}-salesman`, 'salesman', order.salesman || '', globalOptions.salesmen, '-- 请选择 --', order.id)}
                            </div>
                            <div class="space-y-0.5 relative">
                                <label class="text-[11px] font-bold text-gray-400 uppercase tracking-wider">物流公司</label>
                                ${(() => {
                                    const options = [...globalOptions.expressOptions];
                                    if (order.express && !options.includes(order.express)) options.push(order.express);
                                    return customSelect(`order-${order.id}-express`, 'express', order.express || '', options, '-- 自动计算 --', order.id);
                                })()}
                                <p class="absolute left-0 -bottom-3.5 text-[9px] text-gray-400 px-1 font-medium whitespace-nowrap pointer-events-none" title="${order.expressReason || '依据判定'}">
                                    💡 ${order.expressReason || 'AI依据规则库判定'}
                                </p>
                            </div>
                            ${order.trackingNumber ? `
                            <div class="space-y-0.5">
                                <label class="text-[11px] font-bold text-gray-400 uppercase tracking-wider">物流单号</label>
                                <input type="text" value="${order.trackingNumber || ''}" onchange="updateOrder(${order.id}, 'trackingNumber', this.value)" class="w-full h-8 text-[12px] px-2 border border-gray-200 rounded-lg focus:outline-none focus:border-blue-500 bg-white text-gray-800 font-bold" placeholder="物流单号" />
                            </div>
                            ` : ''}
                        </div>

                        <!-- 第五排：客服备注 / 客户备注 -->
                        <div class="grid grid-cols-1 md:grid-cols-2 gap-2">
                            <div class="space-y-0.5">
                                <label class="text-[11px] font-bold text-gray-400 uppercase tracking-wider">客服备注</label>
                                <textarea onchange="updateOrder(${order.id}, 'note', this.value)" class="note-textarea w-full text-[13px] px-3 border border-gray-200 rounded-lg bg-blue-50/50 text-blue-800 font-bold focus:outline-none resize-none overflow-hidden" oninput="autoResizeNote(this)">${order.note || ''}</textarea>
                            </div>
                            <div class="space-y-0.5">
                                <label class="text-[11px] font-bold text-gray-400 uppercase tracking-wider">客户备注</label>
                                <textarea onchange="updateOrder(${order.id}, 'customerNote', this.value)" class="note-textarea w-full text-[13px] px-3 border border-gray-200 rounded-lg bg-blue-50/50 text-blue-800 font-bold focus:outline-none resize-none overflow-hidden" oninput="autoResizeNote(this)">${order.customerNote || ''}</textarea>
                            </div>
                        </div>

                        ${order.products && order.products.length > 0 ? `
                            <div class="pt-1">
                                <button onclick="toggleProducts(${order.id})" class="cc-icon-glass w-full flex items-center justify-between h-8 px-3 rounded-lg group">
                                    <div class="flex items-center gap-3 overflow-hidden">
                                        <span class="text-blue-600">${icons.package}</span>
                                        <span class="text-xs font-bold text-gray-700">货品清单 (${order.products.length} 件):</span>
                                        <span class="text-xs text-blue-800 font-black truncate max-w-[450px]">
                                            ${order.products.map(p => `${p.needsReview ? '[待确认] ' : ''}${p.matchedName || p.searchName} * ${p.qty}`).join(', ')}
                                        </span>
                                    </div>
                                    <span id="chevron-${order.id}" class="text-blue-400 group-hover:text-blue-600">${icons.chevronDown}</span>
                                </button>
                                <div id="products-${order.id}" style="display: none;" class="cc-product-panel mt-2 overflow-x-auto custom-scrollbar">
                                    <table class="min-w-[700px] w-full text-sm">
                                        <thead class="bg-gray-50 border-b border-gray-200">
                                            <tr>
                                                <th class="px-3 py-2 text-left text-[10px] font-bold text-gray-400 uppercase w-1/3">货品名称</th>
                                                <th class="px-2 py-2 text-left text-[10px] font-bold text-gray-400 uppercase">规格编号</th>
                                                <th class="px-2 py-2 text-left text-[10px] font-bold text-gray-400 uppercase">条码</th>
                                                <th class="px-2 py-2 text-left text-[10px] font-bold text-gray-400 uppercase w-20 text-center">数量</th>
                                                <th class="px-2 py-2 text-left text-[10px] font-bold text-gray-400 uppercase w-24 text-center">单价</th>
                                            </tr>
                                        </thead>
                                        <tbody class="bg-white">
                                            ${order.products.map((p, idx) => `
                                                <tr class="border-t ${p.needsReview ? 'cc-review' : 'border-gray-100'} hover:bg-gray-50/50 transition-colors">
                                                    <td class="px-3 py-2">
                                                        <div class="flex gap-1.5 items-center flex-1">
                                                            ${customSelect(`order-${order.id}-prod-${idx}`, `prod-${idx}`, p.matchedName || '', [...(p.candidates || []), ...(globalOptions.allProducts || []).slice(0, 10)], '-- 请输入或选择 --', order.id)}
                                                            <button onclick="openProductSearch(${order.id}, ${idx})" class="cc-icon-glass p-1.5 text-blue-600 rounded-md" title="全库精准搜索">
                                                                ${icons.search}
                                                            </button>
                                                        </div>
                                                        ${p.needsReview ? `<div class="mt-1 text-[11px] font-bold text-amber-700">原文：${p.searchName || '--'}，未在两个货品表中精确命中，请人工选择。</div>` : `<div class="mt-1 text-[10px] text-gray-400">原文：${p.searchName || '--'} · ${p.matchType || '精确匹配'}</div>`}
                                                    </td>
                                                    <td class="px-2 py-2 text-[11px] text-gray-500 font-mono">${p.spec_no || p.item_no || '--'}</td>
                                                    <td class="px-2 py-2 text-[11px] text-gray-400 font-mono">${p.barcode || '--'}</td>
                                                    <td class="px-2 py-2">
                                                        <input type="number" value="${p.qty}" onchange="updateProduct(${order.id}, ${idx}, 'qty', parseInt(this.value))" class="w-full h-8 text-xs border border-gray-200 rounded-md text-center focus:border-blue-500" />
                                                    </td>
                                                    <td class="px-2 py-2">
                                                        <input type="number" value="${p.price || 0}" onchange="updateProduct(${order.id}, ${idx}, 'price', parseFloat(this.value))" class="w-full h-8 text-xs border border-gray-200 rounded-md text-center font-bold text-blue-600 focus:border-blue-500" />
                                                    </td>
                                                </tr>
                                            `).join('')}
                                        </tbody>
                                    </table>
                                </div>
                            </div>
                        ` : ''}
                        
                        <!-- 底部原文回显 -->
                        <div class="mt-1 pt-2 border-t border-dashed border-gray-200">
                            <div class="flex items-center gap-2 mb-1 text-[9px] font-bold text-gray-400 uppercase tracking-widest">
                                📝 订单原文
                            </div>
                            <div class="bg-gray-50/50 rounded-lg p-2 text-[10px] text-gray-500 font-medium leading-normal italic border border-gray-100 shadow-inner">
                                ${(order.raw || '无数据').replace(/\r?\n/g, ' ')}
                            </div>
                        </div>
                    </div>
            `;

            return card;
        }
