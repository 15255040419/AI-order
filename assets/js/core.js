// 🌟 智能适配后端地址：锁定 5005 端口（避开后台僵尸进程）
        const BACKEND_BASE_URL = (() => {
            // 🌟 核心改进：如果是通过 http/https 协议访问的（不管是 IP 还是 域名），直接使用当前源
            // 这能完美解决多网卡（127.0.0.1 vs 10.20.0.1）导致的连接失败问题
            if (window.location.protocol.startsWith('http')) {
                return `${window.location.origin}/api`;
            }
            // 如果是直接打开本地 .html 文件，则回退到 127.0.0.1
            return 'http://127.0.0.1:5005/api';
        })();

        // 🌟 科技感粒子特效系统
        class ParticleSystem {
            constructor() {
                this.canvas = document.getElementById('particleCanvas');
                if (!this.canvas) return;
                this.ctx = this.canvas.getContext('2d');
                this.particles = [];
                this.mouse = { x: -1000, y: -1000, vx: 0, vy: 0 };
                this.lastMouse = { x: -1000, y: -1000 };

                this.init();
                this.animate();

                window.addEventListener('resize', () => this.resize());
                window.addEventListener('mousemove', (e) => {
                    this.lastMouse.x = this.mouse.x;
                    this.lastMouse.y = this.mouse.y;
                    this.mouse.x = e.clientX;
                    this.mouse.y = e.clientY;
                    this.mouse.vx = this.mouse.x - this.lastMouse.x;
                    this.mouse.vy = this.mouse.y - this.lastMouse.y;
                });
                window.addEventListener('mouseout', () => {
                    this.mouse.x = -1000;
                    this.mouse.y = -1000;
                });
            }

            init() {
                this.resize();
                // 适中的粒子密度
                const numParticles = Math.min(Math.floor((window.innerWidth * window.innerHeight) / 10000), 140);
                for (let i = 0; i < numParticles; i++) {
                    this.particles.push({
                        x: Math.random() * this.canvas.width,
                        y: Math.random() * this.canvas.height,
                        vx: (Math.random() - 0.5) * 1.2,
                        vy: (Math.random() - 0.5) * 1.2,
                        radius: Math.random() * 1.5 + 0.8,
                        baseVx: (Math.random() - 0.5) * 0.8,
                        baseVy: (Math.random() - 0.5) * 0.8
                    });
                }
            }

            resize() {
                this.canvas.width = window.innerWidth;
                this.canvas.height = window.innerHeight;
            }

            animate() {
                this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);

                // 判断当前主题以使用适配的颜色
                const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
                const colorBase = isDark ? '242, 169, 59' : '217, 119, 6'; // 使用 --cc-accent 色系

                this.ctx.fillStyle = `rgba(${colorBase}, 0.8)`;

                for (let i = 0; i < this.particles.length; i++) {
                    let p = this.particles[i];

                    p.x += p.vx;
                    p.y += p.vy;

                    // 边界反弹
                    if (p.x < 0 || p.x > this.canvas.width) p.vx *= -1;
                    if (p.y < 0 || p.y > this.canvas.height) p.vy *= -1;

                    // 鼠标交互：发散与避让效果
                    let dx = this.mouse.x - p.x;
                    let dy = this.mouse.y - p.y;
                    let dist = Math.sqrt(dx * dx + dy * dy);

                    if (dist < 200) {
                        const force = (200 - dist) / 200;
                        p.x -= (dx / dist) * force * 5;
                        p.y -= (dy / dist) * force * 5;

                        // 根据鼠标移动速度给粒子附加惯性（发散感）
                        const mouseSpeed = Math.sqrt(this.mouse.vx * this.mouse.vx + this.mouse.vy * this.mouse.vy);
                        if (mouseSpeed > 2) {
                            p.vx += (this.mouse.vx * force * 0.15);
                            p.vy += (this.mouse.vy * force * 0.15);
                        }
                    }

                    // 速度回归基准（阻尼效果），避免粒子越跑越快
                    p.vx = p.vx * 0.94 + p.baseVx * 0.06;
                    p.vy = p.vy * 0.94 + p.baseVy * 0.06;

                    this.ctx.beginPath();
                    this.ctx.arc(p.x, p.y, p.radius, 0, Math.PI * 2);
                    this.ctx.fill();

                    // 粒子之间连线（星座效果）
                    for (let j = i + 1; j < this.particles.length; j++) {
                        let p2 = this.particles[j];
                        let dx2 = p.x - p2.x;
                        let dy2 = p.y - p2.y;
                        let dist2 = Math.sqrt(dx2 * dx2 + dy2 * dy2);

                        // 适中的连线距离，保持清爽
                        if (dist2 < 120) {
                            this.ctx.beginPath();
                            this.ctx.strokeStyle = `rgba(${colorBase}, ${0.3 * (1 - dist2 / 120)})`;
                            this.ctx.lineWidth = 0.6;
                            this.ctx.moveTo(p.x, p.y);
                            this.ctx.lineTo(p2.x, p2.y);
                            this.ctx.stroke();
                        }
                    }
                }

                requestAnimationFrame(() => this.animate());
            }
        }


        // 🌟 全域幽灵滚动条逻辑
        function initGhostScrollbar() {
            let hideTimeout = null;
            const html = document.documentElement;

            window.addEventListener('scroll', () => {
                html.classList.add('is-scrolling');
                if (hideTimeout) clearTimeout(hideTimeout);
                hideTimeout = setTimeout(() => {
                    html.classList.remove('is-scrolling');
                }, 1000);
            }, { passive: true, capture: true });
        }

        document.addEventListener('DOMContentLoaded', () => {
            new ParticleSystem();
            initGhostScrollbar();
        });

        // Toast 通知
        const toast = {
            success: (message, description = '') => {
                const container = document.getElementById('toast-container');
                const toastEl = document.createElement('div');
                toastEl.className = 'toast success';
                toastEl.innerHTML = `
                    <div style="font-weight: 600; color: #111827;">${message}</div>
                    ${description ? `<div style="font-size: 14px; color: #6b7280; margin-top: 4px;">${description}</div>` : ''}
                `;
                container.appendChild(toastEl);
                setTimeout(() => toastEl.remove(), 3000);
            },
            error: (message, description = '') => {
                const container = document.getElementById('toast-container');
                const toastEl = document.createElement('div');
                toastEl.className = 'toast error';
                toastEl.innerHTML = `
                    <div style="font-weight: 600; color: #111827;">${message}</div>
                    ${description ? `<div style="font-size: 14px; color: #6b7280; margin-top: 4px;">${description}</div>` : ''}
                `;
                container.appendChild(toastEl);
                setTimeout(() => toastEl.remove(), 3000);
            }
        };

        // 确认对话框
        function showConfirmDialog(title, description, onConfirm) {
            const modalRoot = document.getElementById('modal-root');
            const modal = document.createElement('div');
            modal.className = 'modal-overlay';
            modal.innerHTML = `
                <div class="modal-content">
                    <h3 style="font-size: 18px; font-weight: 600; margin-bottom: 8px;">${title}</h3>
                    <p style="color: #6b7280; margin-bottom: 24px;">${description}</p>
                    <div style="display: flex; gap: 12px; justify-content: flex-end;">
                        <button id="cancel-btn" class="cc-chip" style="height: 40px; min-width: 88px; justify-content: center; cursor: pointer;">取消</button>
                        <button id="confirm-btn" class="cc-chip cc-chip-primary" style="height: 40px; min-width: 88px; justify-content: center; cursor: pointer;">确认</button>
                    </div>
                </div>
            `;
            modalRoot.appendChild(modal);

            modal.querySelector('#cancel-btn').onclick = () => modal.remove();
            modal.querySelector('#confirm-btn').onclick = () => {
                onConfirm();
                modal.remove();
            };
            modal.onclick = (e) => {
                if (e.target === modal) modal.remove();
            };
        }

        // 🌟 新增：全局模糊匹配工具 (确保下拉框能对上带括号的名字)
        window.findBestMatch = (options, value) => {
            if (!value) return '';
            const clean = (s) => String(s).replace(/[\(\（].*?[\)\）]/g, '').replace(/[\[\]]/g, '').trim().toUpperCase();
            const target = clean(value);
            // 1. 直接匹配
            if (options.includes(value)) return value;
            // 2. 清洁后的精确匹配
            const match = options.find(opt => clean(opt) === target);
            if (match) return match;
            // 3. 包含匹配
            return options.find(opt => clean(opt).includes(target) || target.includes(clean(opt))) || value;
        };

        // SVG 图标
        const icons = {
            checkCircle: `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><path d="m9 11 3 3L22 4"/></svg>`,
            user: `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>`,
            sparkles: `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364-.707-.707M6.343 6.343l-.707-.707m12.728 0-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 1 1-8 0 4 4 0 0 1 8 0z"/></svg>`,
            send: `<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="22" y1="2" x2="11" y2="13"></line><polygon points="22 2 15 22 11 13 2 9 22 2"></polygon></svg>`,
            download: `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M7 10l5 5 5-5M12 15V3"/></svg>`,
            trash: `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>`,
            trashSmall: `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>`,
            chevronDown: `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m6 9 6 6 6-6"/></svg>`,
            chevronUp: `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m18 15-6-6-6 6"/></svg>`,
            package: `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/><path d="M3.3 7 12 12l8.7-5M12 22V12"/></svg>`,
            loader: `<svg class="loader-icon" width="32" height="32" viewBox="0 0 50 50"><circle cx="25" cy="25" r="20" fill="none" stroke="#3b82f6" stroke-width="3" stroke-dasharray="31.4 31.4" stroke-linecap="round"><animateTransform attributeName="transform" type="rotate" from="0 25 25" to="360 25 25" dur="1s" repeatCount="indefinite"/></circle></svg>`,
            search: `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/></svg>`
        };

        // 主应用状态
        let appState = {
            orders: [],
            globalOptions: {
                salesmen: [],
                customers: [],
                payMethods: [],
                receipts: [],
                expressOptions: [],
                allProducts: [],
            },
            isProcessing: false,
            inputText: '',
            mousePosition: { x: 0, y: 0 },
            theme: localStorage.getItem('order-helper-theme') || 'dark',
            backgroundImage: localStorage.getItem('order-helper-bg-image') || '',
            openDropdown: '',
            dropdownSearch: ''
        };

        function applyBackgroundImage() {
            const image = appState.backgroundImage || localStorage.getItem('order-helper-bg-image') || '';
            document.documentElement.style.setProperty('--cc-bg-image', image ? `url("${image}")` : 'none');
        }

        function escAttr(value) {
            return String(value ?? '')
                .replace(/&/g, '&amp;')
                .replace(/"/g, '&quot;')
                .replace(/</g, '&lt;')
                .replace(/>/g, '&gt;');
        }

        function customSelect(key, field, value, options, placeholder, orderId) {
            const cleanOptions = [...new Set((options || []).filter(v => v !== undefined && v !== null))];
            const current = value || '';
            const isOpen = appState.openDropdown === key;
            
            // 🌟 核心改进：支持输入过滤
            let filteredOptions = cleanOptions;
            if (isOpen && appState.dropdownSearch) {
                const search = appState.dropdownSearch.toUpperCase();
                filteredOptions = cleanOptions.filter(opt => String(opt).toUpperCase().includes(search));
            }
            
            const allOptions = (filteredOptions.includes(current) || !current) ? filteredOptions : [current, ...filteredOptions];
            
            return `
                <div class="cc-select" onclick="event.stopPropagation()">
                    <input 
                        type="text" 
                        class="cc-select-button" 
                        data-key="${key}"
                        data-field="${field}"
                        data-order-id="${orderId}"
                        value="${escAttr(current)}"
                        placeholder="${escAttr(placeholder || '-- 请选择 --')}"
                        onfocus="handleSelectFocus('${key}', this.value)"
                        oninput="handleSelectInput('${key}', this.value)"
                        onkeydown="if(event.key==='Enter') { saveManualEntry(this); this.blur(); }"
                        autocomplete="off"
                        style="cursor: text; padding-right: 24px;"
                    />
                    ${isOpen ? `
                        <div class="cc-select-menu">
                            ${!appState.dropdownSearch ? `<div class="cc-select-option ${!current ? 'active' : ''}" onclick="selectOrderOption(${orderId}, '${field}', '')">${escAttr(placeholder || '-- 请选择 --')}</div>` : ''}
                            ${allOptions.map(opt => `
                                <div class="cc-select-option ${opt === current ? 'active' : ''}" onmousedown="selectOrderOption(${orderId}, '${field}', decodeURIComponent('${encodeURIComponent(opt)}'))">
                                    <span>${escAttr(opt)}</span>
                                </div>
                            `).join('')}
                            ${allOptions.length === 0 ? `<div class="p-3 text-center text-xs text-gray-400">未找到匹配项</div>` : ''}
                        </div>
                    ` : ''}
                </div>
            `;
        }
