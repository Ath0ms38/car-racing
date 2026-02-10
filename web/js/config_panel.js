/**
 * ConfigPanel - Car & NEAT configuration forms.
 */
class ConfigPanel {
    constructor() {
        this.carConfig = {};
        this.neatConfig = {};
        this.paramMeta = [];
        this._bindEvents();
    }

    _bindEvents() {
        document.getElementById('apply-config-btn').addEventListener('click', () => this.applyConfigs());

        // Ray angle controls
        document.getElementById('ray-angles-apply').addEventListener('click', () => {
            const input = document.getElementById('ray-angles-input');
            this._setRayAngles(input.value);
        });
        document.getElementById('ray-angles-input').addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                this._setRayAngles(e.target.value);
            }
        });

        // Preset buttons
        document.querySelectorAll('.ray-preset').forEach(btn => {
            btn.addEventListener('click', () => {
                const angles = btn.dataset.angles;
                document.getElementById('ray-angles-input').value = angles;
                this._setRayAngles(angles);
            });
        });
    }

    _setRayAngles(anglesStr) {
        const parsed = anglesStr.split(',').map(s => parseFloat(s.trim())).filter(n => !isNaN(n));
        if (parsed.length === 0) {
            showToast('Enter at least one angle', 'error');
            return;
        }
        parsed.sort((a, b) => a - b);
        const formatted = parsed.join(', ');
        document.getElementById('ray-angles-input').value = formatted;
        this.carConfig.ray_angles = formatted;
        this._drawRayPreview(parsed);
    }

    _drawRayPreview(anglesDeg) {
        const canvas = document.getElementById('ray-preview-canvas');
        const ctx = canvas.getContext('2d');
        const w = canvas.width;
        const h = canvas.height;
        const cx = w / 2;
        const cy = h / 2;

        ctx.clearRect(0, 0, w, h);

        // Background
        ctx.fillStyle = '#0a0a1a';
        ctx.fillRect(0, 0, w, h);

        // Draw rays
        const rayLen = 60;
        for (const deg of anglesDeg) {
            const rad = deg * Math.PI / 180;
            // Car faces right (0 deg), rays go from car center
            const ex = cx + Math.cos(rad) * rayLen;
            const ey = cy + Math.sin(rad) * rayLen;

            ctx.beginPath();
            ctx.moveTo(cx, cy);
            ctx.lineTo(ex, ey);
            ctx.strokeStyle = 'rgba(233, 69, 96, 0.6)';
            ctx.lineWidth = 1.5;
            ctx.stroke();

            // Ray endpoint dot
            ctx.beginPath();
            ctx.arc(ex, ey, 3, 0, Math.PI * 2);
            ctx.fillStyle = '#e94560';
            ctx.fill();

            // Angle label
            const labelDist = rayLen + 12;
            const lx = cx + Math.cos(rad) * labelDist;
            const ly = cy + Math.sin(rad) * labelDist;
            ctx.fillStyle = '#8899aa';
            ctx.font = '10px sans-serif';
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.fillText(deg + '\u00B0', lx, ly);
        }

        // Draw car body (rectangle, facing right)
        const carW = 24;
        const carH = 12;
        ctx.save();
        ctx.translate(cx, cy);
        ctx.fillStyle = '#0f3460';
        ctx.strokeStyle = '#e0e0e0';
        ctx.lineWidth = 1.5;
        ctx.beginPath();
        ctx.roundRect(-carW / 2, -carH / 2, carW, carH, 3);
        ctx.fill();
        ctx.stroke();

        // Front indicator (small triangle)
        ctx.fillStyle = '#e94560';
        ctx.beginPath();
        ctx.moveTo(carW / 2, 0);
        ctx.lineTo(carW / 2 - 5, -4);
        ctx.lineTo(carW / 2 - 5, 4);
        ctx.closePath();
        ctx.fill();
        ctx.restore();

        // Ray count label
        ctx.fillStyle = '#e0e0e0';
        ctx.font = '11px sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText(anglesDeg.length + ' rays', cx, h - 8);
    }

    async loadConfigs() {
        try {
            this.carConfig = await pywebview.api.get_car_config();
            this.neatConfig = await pywebview.api.get_neat_config();
            this.paramMeta = await pywebview.api.get_editable_params();
            this.renderCarForm();
            this.renderNeatForm();
            this._initRayAngles();
        } catch (e) {
            console.error('Failed to load configs:', e);
        }
    }

    _initRayAngles() {
        const anglesStr = this.carConfig.ray_angles || '-90, -45, 0, 45, 90';
        document.getElementById('ray-angles-input').value = anglesStr;
        const parsed = anglesStr.split(',').map(s => parseFloat(s.trim())).filter(n => !isNaN(n));
        this._drawRayPreview(parsed);
    }

    renderCarForm() {
        const container = document.getElementById('car-config-form');
        container.innerHTML = '';

        const carParams = this.paramMeta.filter(p => p.section === 'car');
        for (const param of carParams) {
            const field = this._createField(param, this.carConfig[param.key]);
            container.appendChild(field);
        }
    }

    renderNeatForm() {
        const container = document.getElementById('neat-config-form');
        container.innerHTML = '';

        const neatParams = this.paramMeta.filter(p => p.section !== 'car');
        for (const param of neatParams) {
            const configKey = `${param.section}.${param.key}`;
            const value = this.neatConfig[configKey] || param.default;
            const field = this._createField(param, value);
            container.appendChild(field);
        }
    }

    _createField(param, value) {
        const div = document.createElement('div');
        div.className = 'config-field';

        const label = document.createElement('label');
        label.textContent = param.label;
        if (param.tooltip) {
            label.title = param.tooltip;
        }
        div.appendChild(label);

        if (param.type === 'bool') {
            const input = document.createElement('input');
            input.type = 'checkbox';
            input.checked = value === true || value === 'True' || value === 'true';
            input.dataset.key = param.key;
            input.dataset.section = param.section;
            input.addEventListener('change', () => {
                this._onConfigChange(param.section, param.key, input.checked);
            });
            div.appendChild(input);
        } else if (param.type === 'str') {
            const input = document.createElement('input');
            input.type = 'text';
            input.value = value || '';
            input.dataset.key = param.key;
            input.dataset.section = param.section;
            input.addEventListener('change', () => {
                this._onConfigChange(param.section, param.key, input.value);
            });
            div.appendChild(input);
        } else {
            const input = document.createElement('input');
            input.type = 'number';
            input.value = value || param.default;
            input.step = param.type === 'float' ? 'any' : '1';
            if (param.min !== undefined) input.min = param.min;
            if (param.max !== undefined) input.max = param.max;
            input.dataset.key = param.key;
            input.dataset.section = param.section;
            input.addEventListener('change', () => {
                const val = param.type === 'int' ? parseInt(input.value) : parseFloat(input.value);
                this._onConfigChange(param.section, param.key, val);
            });
            div.appendChild(input);
        }

        // Lock icon for non-resume-safe params
        if (!param.resume_safe) {
            const lock = document.createElement('span');
            lock.className = 'lock-icon';
            lock.textContent = '\uD83D\uDD12';
            lock.title = 'Cannot change during resume (changes network topology)';
            div.appendChild(lock);
        }

        // Warning icon
        if (param.warning) {
            const warn = document.createElement('span');
            warn.className = 'warning-icon';
            warn.textContent = '\u26A0';
            warn.title = param.warning;
            div.appendChild(warn);
        }

        return div;
    }

    _onConfigChange(section, key, value) {
        if (section === 'car') {
            this.carConfig[key] = value;
        } else {
            this.neatConfig[`${section}.${key}`] = value;
        }
    }

    async applyConfigs() {
        try {
            const carResult = await pywebview.api.set_car_config(this.carConfig);
            const neatResult = await pywebview.api.set_neat_config(this.neatConfig);

            if (carResult && neatResult) {
                showToast('Config applied!');
            } else {
                showToast('Failed to apply config', 'error');
            }
        } catch (e) {
            showToast('Config error: ' + e.message, 'error');
        }
    }

    async validateForResume() {
        try {
            const result = await pywebview.api.validate_config_for_resume(this.carConfig);
            return result;
        } catch (e) {
            return { valid: false, errors: [e.message] };
        }
    }
}
