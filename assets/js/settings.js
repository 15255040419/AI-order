// ==== AI 设置面板 ====
        let _aiProviders = [];
        let _aiCurrent  = {};

        async function fetchAiConfig() {
            try {
                const r = await fetch(`${BACKEND_BASE_URL}/ai-config`);
                const d = await r.json();
                _aiProviders = d.providers || [];
                _aiCurrent   = d.current  || {};
            } catch(e) { /* 新部署前志识 */ }
        }

        function openAiSettings() {
            const modalRoot = document.getElementById('modal-root');
            const modal = document.createElement('div');
            modal.className = 'modal-overlay';
            modal.id = 'ai-settings-modal';

            const providerOpts = _aiProviders.map(p =>
                `<option value="${p.id}" ${p.id === _aiCurrent.provider ? 'selected' : ''}>${p.name}</option>`
            ).join('');

            const currentProvider = _aiProviders.find(p => p.id === _aiCurrent.provider);
            const modelOpts = (currentProvider?.models || []).map(m =>
                `<option value="${m}" ${m === _aiCurrent.model ? 'selected' : ''}>${m}</option>`
            ).join('');

            modal.innerHTML = `
                <div class="modal-content" style="max-width:420px;">
                    <div style="display:flex;align-items:center;gap:10px;margin-bottom:18px;">
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="var(--cc-accent)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>
                        <h3 style="font-size:16px;font-weight:700;color:var(--cc-text);">设置</h3>
                    </div>

                    <div style="display:flex;flex-direction:column;gap:14px;">
                        <div>
                            <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:8px;">
                                <label style="font-size:12px;color:var(--cc-muted);font-weight:700;">页面背景</label>
                                <button onclick="clearBackgroundImage()" class="cc-chip" style="height:28px;font-size:12px;padding:0 9px;cursor:pointer;">恢复默认</button>
                            </div>
                            <div class="cc-bg-preview" id="bg-preview"></div>
                            <div style="display:flex;gap:8px;margin-top:10px;">
                                <button type="button" onclick="triggerBackgroundUpload()" class="cc-chip cc-chip-primary" style="height:34px;justify-content:center;cursor:pointer;flex:1;">
                                    上传背景图
                                </button>
                                <input id="bg-file-input" type="file" accept="image/*" style="position:fixed;left:50%;top:50%;width:1px;height:1px;opacity:0;pointer-events:none;" />
                            </div>
                            <p style="font-size:11px;color:var(--cc-muted);margin-top:7px;line-height:1.5;">图片会压缩后保存在当前浏览器本地，刷新后仍然保留。</p>
                        </div>

                        <div style="height:1px;background:var(--cc-border-soft);margin:2px 0;"></div>

                        <div>
                            <label style="font-size:12px;color:var(--cc-muted);font-weight:600;display:block;margin-bottom:6px;">提供商</label>
                            <select id="ai-provider-sel" style="width:100%;height:36px;border-radius:8px;border:1px solid var(--cc-border);background:var(--cc-surface-2);color:var(--cc-text);padding:0 28px 0 10px;font-size:13px;">
                                ${providerOpts}
                            </select>
                        </div>
                        <div>
                            <label style="font-size:12px;color:var(--cc-muted);font-weight:600;display:block;margin-bottom:6px;">模型</label>
                            <select id="ai-model-sel" style="width:100%;height:36px;border-radius:8px;border:1px solid var(--cc-border);background:var(--cc-surface-2);color:var(--cc-text);padding:0 28px 0 10px;font-size:13px;">
                                ${modelOpts}
                            </select>
                        </div>
                        <div>
                            <label style="font-size:12px;color:var(--cc-muted);font-weight:600;display:block;margin-bottom:6px;">API Key</label>
                            <input id="ai-apikey-inp" type="password" value="${_aiCurrent.api_key || ''}" placeholder="输入 API Key" style="width:100%;height:36px;border-radius:8px;border:1px solid var(--cc-border);background:var(--cc-surface-2);color:var(--cc-text);padding:0 10px;font-size:13px;outline:none;" />
                        </div>
                    </div>

                    <div style="display:flex;gap:10px;justify-content:flex-end;margin-top:22px;">
                        <button onclick="document.getElementById('ai-settings-modal').remove()" class="cc-chip" style="height:38px;min-width:80px;justify-content:center;cursor:pointer;">取消</button>
                        <button onclick="saveAiConfig()" class="cc-chip cc-chip-primary" style="height:38px;min-width:80px;justify-content:center;cursor:pointer;">保存生效</button>
                    </div>
                </div>
            `;
            modalRoot.appendChild(modal);
            modal.onclick = e => { if (e.target === modal) modal.remove(); };
            document.getElementById('bg-file-input')?.addEventListener('change', handleBackgroundUpload);

            // 切换提供商时动态刷新模型列表
            document.getElementById('ai-provider-sel').addEventListener('change', function() {
                const prov = _aiProviders.find(p => p.id === this.value);
                const modelSel = document.getElementById('ai-model-sel');
                modelSel.innerHTML = (prov?.models || []).map(m => `<option value="${m}">${m}</option>`).join('');
            });
        }

        function triggerBackgroundUpload() {
            const input = document.getElementById('bg-file-input');
            if (!input) return;
            requestAnimationFrame(() => input.click());
        }

        function handleBackgroundUpload(event) {
            const file = event.target.files?.[0];
            if (!file) return;
            if (!file.type.startsWith('image/')) {
                toast.error('请选择图片文件');
                return;
            }

            const reader = new FileReader();
            reader.onload = () => {
                const img = new Image();
                img.onload = () => {
                    const maxSide = 2200;
                    const scale = Math.min(1, maxSide / Math.max(img.width, img.height));
                    const canvas = document.createElement('canvas');
                    canvas.width = Math.max(1, Math.round(img.width * scale));
                    canvas.height = Math.max(1, Math.round(img.height * scale));
                    const ctx = canvas.getContext('2d');
                    ctx.drawImage(img, 0, 0, canvas.width, canvas.height);

                    try {
                        const dataUrl = canvas.toDataURL('image/jpeg', 0.84);
                        localStorage.setItem('order-helper-bg-image', dataUrl);
                        appState.backgroundImage = dataUrl;
                        applyBackgroundImage();
                        toast.success('背景已更新');
                    } catch (err) {
                        toast.error('背景图太大', '请换一张小一点的图片');
                    }
                };
                img.onerror = () => toast.error('图片读取失败');
                img.src = reader.result;
            };
            reader.onerror = () => toast.error('图片读取失败');
            reader.readAsDataURL(file);
        }

        function clearBackgroundImage() {
            localStorage.removeItem('order-helper-bg-image');
            appState.backgroundImage = '';
            applyBackgroundImage();
            toast.success('已恢复默认背景');
        }

        async function saveAiConfig() {
            const provider = document.getElementById('ai-provider-sel').value;
            const model    = document.getElementById('ai-model-sel').value;
            const api_key  = document.getElementById('ai-apikey-inp').value.trim();
            if (!api_key) { toast.error('API Key 不能为空'); return; }
            try {
                const r = await fetch(`${BACKEND_BASE_URL}/ai-config`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ provider, model, api_key })
                });
                const d = await r.json();
                if (d.ok) {
                    _aiCurrent = d.config;
                    document.getElementById('ai-settings-modal')?.remove();
                    toast.success(`AI 引擎已切换`, `${provider} / ${model}`);
                } else {
                    toast.error('切换失败', JSON.stringify(d));
                }
            } catch(e) {
                toast.error('请求失败', e.message);
            }
        }
        // ==== END AI 设置 ====
