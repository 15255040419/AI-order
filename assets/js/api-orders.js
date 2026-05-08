// 获取配置
        async function fetchOptions() {
            try {
                const res = await fetch(`${BACKEND_BASE_URL}/options`);
                if (res.ok) {
                    appState.globalOptions = await res.json();
                    console.log('✅ 系统配置与库存加载成功');
                }
            } catch (e) {
                console.error('Options Failed', e);
                toast.error('无法连接到后端服务', `请求失败: ${BACKEND_BASE_URL}/options。请检查后端是否正常启动。`);
            }
        }

        function updatePlaceholderOrder(orderId, patch) {
            appState.orders = appState.orders.map(o =>
                o.id === orderId ? { ...o, ...patch } : o
            );
            scheduleOrderCardRefresh(orderId);
        }

        function applyParsedOrder(orderId, parsed) {
            appState.orders = appState.orders.map(o => {
                if (o.id === orderId) {
                    return {
                        ...o,
                        ...parsed,
                        loading: false,
                        error: false,
                        progressText: '',
                        progressStep: '',
                        receiver: parsed.receiver || '未知名字'
                    };
                }
                return o;
            });
        }

        async function parseOrderPlain(placeholder) {
            const resp = await fetch(`${BACKEND_BASE_URL}/parse`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ text: placeholder.raw }),
            });
            if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
            const parsed = await resp.json();
            applyParsedOrder(placeholder.id, parsed);
        }

        function handleStreamEvent(placeholder, eventName, payload) {
            if (eventName === 'progress') {
                updatePlaceholderOrder(placeholder.id, {
                    progressText: payload.message || '正在识别...',
                    progressStep: payload.step || ''
                });
                return false;
            }

            if (eventName === 'done') {
                applyParsedOrder(placeholder.id, payload);
                return true;
            }

            if (eventName === 'error') {
                throw new Error(payload.message || '流式解析失败');
            }
            return false;
        }

        async function parseOrderWithStream(placeholder) {
            let streamStarted = false;
            try {
                const resp = await fetch(`${BACKEND_BASE_URL}/parse-stream`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ text: placeholder.raw }),
                });
                if (!resp.ok || !resp.body) throw new Error(`HTTP ${resp.status}`);

                streamStarted = true;
                const reader = resp.body.getReader();
                const decoder = new TextDecoder('utf-8');
                let buffer = '';
                let doneReceived = false;

                while (true) {
                    const { value, done } = await reader.read();
                    if (done) break;
                    buffer += decoder.decode(value, { stream: true });

                    const chunks = buffer.split('\n\n');
                    buffer = chunks.pop() || '';
                    for (const chunk of chunks) {
                        const eventLine = chunk.split('\n').find(line => line.startsWith('event:'));
                        const dataLine = chunk.split('\n').find(line => line.startsWith('data:'));
                        if (!dataLine) continue;
                        const eventName = eventLine ? eventLine.replace(/^event:\s*/, '').trim() : 'message';
                        const payload = JSON.parse(dataLine.replace(/^data:\s*/, ''));
                        if (handleStreamEvent(placeholder, eventName, payload)) {
                            doneReceived = true;
                        }
                    }
                }

                if (!doneReceived) throw new Error('流式解析未返回完成结果');
            } catch (e) {
                if (streamStarted) throw e;
                console.warn('流式解析不可用，自动回退普通解析:', e);
                updatePlaceholderOrder(placeholder.id, {
                    progressText: '流式连接失败，切换普通解析...',
                    progressStep: 'fallback'
                });
                await parseOrderPlain(placeholder);
            }
        }

        // 提交订单文本 (非阻塞异步模式)
        async function handleSubmitText(text) {
            const rawText = text.trim();
            if (!rawText) return;

            // 1. 立即清空输入框，准备下一单
            appState.inputText = '';
            syncComposerFromState();


            let chunks = rawText.split(/\n\s*\n/).map(t => t.trim()).filter(t => t.length > 5);
            if (chunks.length === 0) chunks = [rawText];

            const newOrders = chunks.map(chunk => {
                const uniqueId = Date.now() + Math.random();
                return {
                    id: uniqueId,
                    raw: chunk,
                    receiver: '⏳ 正在拼命识别...',
                    products: [],
                    loading: true,
                    error: false,
                    errType: '',
                    phone: '',
                    address: '',
                    total: 0,
                    freight: 0,
                    account: '',
                    salesman: appState.globalOptions.salesmen[0] || '',
                    receipt: appState.globalOptions.receipts[0] || '',
                    express: '',
                    trackingNumber: '',
                    note: '',
                    customerNote: '',
                    progressText: '订单已进入解析队列',
                    progressStep: 'queued',
                };
            });

            // 2. 把占位符按序追加到列表末尾
            const startIndex = appState.orders.length;
            appState.orders = [...appState.orders, ...newOrders];
            appendNewOrderCards(startIndex, newOrders);

            // 3. 并发解析每一单
            newOrders.forEach(async (placeholder, idx) => {
                try {
                    await parseOrderWithStream(placeholder);
                } catch (e) {
                    appState.orders = appState.orders.map(o =>
                        o.id === placeholder.id ? { ...o, error: true, loading: false, errType: e.message, status: 'error', message: '前端处理异常: ' + e.message } : o
                    );
                } finally {
                    scheduleRelatedOrderCardRefresh(placeholder.id);
                }
            });
        }
