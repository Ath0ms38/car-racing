/**
 * FitnessChart - line chart showing fitness over generations.
 */
class FitnessChart {
    constructor(canvas) {
        this.canvas = canvas;
        this.ctx = canvas.getContext('2d');
        this.data = [];
        this._lastLength = 0;
    }

    update(history) {
        if (!history || history.length === this._lastLength) return;
        this.data = history;
        this._lastLength = history.length;
        this.draw();
    }

    draw() {
        const ctx = this.ctx;
        const w = this.canvas.width;
        const h = this.canvas.height;
        const pad = { top: 10, right: 10, bottom: 25, left: 50 };

        ctx.clearRect(0, 0, w, h);

        // Background
        ctx.fillStyle = '#0a0a1a';
        ctx.fillRect(0, 0, w, h);

        if (this.data.length < 2) {
            ctx.fillStyle = '#555';
            ctx.font = '12px sans-serif';
            ctx.textAlign = 'center';
            ctx.fillText('Waiting for data...', w / 2, h / 2);
            return;
        }

        const plotW = w - pad.left - pad.right;
        const plotH = h - pad.top - pad.bottom;

        // Compute ranges
        let maxFit = -Infinity, minFit = Infinity;
        for (const d of this.data) {
            if (d.best > maxFit) maxFit = d.best;
            if (d.avg !== undefined && d.avg < minFit) minFit = d.avg;
            if (d.best < minFit) minFit = d.best;
        }
        if (minFit === maxFit) {
            maxFit += 1;
            minFit -= 1;
        }

        const xScale = plotW / (this.data.length - 1);
        const yRange = maxFit - minFit;

        const toX = (i) => pad.left + i * xScale;
        const toY = (v) => pad.top + plotH - ((v - minFit) / yRange) * plotH;

        // Grid lines
        ctx.strokeStyle = '#1a2a3a';
        ctx.lineWidth = 1;
        for (let i = 0; i <= 4; i++) {
            const y = pad.top + (plotH / 4) * i;
            ctx.beginPath();
            ctx.moveTo(pad.left, y);
            ctx.lineTo(w - pad.right, y);
            ctx.stroke();

            const val = maxFit - (yRange / 4) * i;
            ctx.fillStyle = '#556';
            ctx.font = '10px sans-serif';
            ctx.textAlign = 'right';
            ctx.fillText(val >= 1000 ? (val / 1000).toFixed(1) + 'k' : Math.round(val), pad.left - 5, y + 4);
        }

        // X axis labels
        ctx.fillStyle = '#556';
        ctx.textAlign = 'center';
        const step = Math.max(1, Math.floor(this.data.length / 5));
        for (let i = 0; i < this.data.length; i += step) {
            ctx.fillText(this.data[i].gen, toX(i), h - 5);
        }

        // Best fitness line (green)
        this._drawLine(this.data.map((d, i) => [toX(i), toY(d.best)]), '#44cc44', 2);

        // Average fitness line (blue)
        if (this.data[0].avg !== undefined) {
            this._drawLine(this.data.map((d, i) => [toX(i), toY(d.avg)]), '#4488ff', 1.5);
        }

        // Legend
        ctx.font = '10px sans-serif';
        ctx.textAlign = 'left';
        ctx.fillStyle = '#44cc44';
        ctx.fillText('Best', pad.left + 5, pad.top + 12);
        ctx.fillStyle = '#4488ff';
        ctx.fillText('Avg', pad.left + 40, pad.top + 12);
    }

    _drawLine(points, color, width) {
        if (points.length < 2) return;
        const ctx = this.ctx;
        ctx.beginPath();
        ctx.moveTo(points[0][0], points[0][1]);
        for (let i = 1; i < points.length; i++) {
            ctx.lineTo(points[i][0], points[i][1]);
        }
        ctx.strokeStyle = color;
        ctx.lineWidth = width;
        ctx.stroke();
    }

    clear() {
        this.data = [];
        this._lastLength = 0;
        const ctx = this.ctx;
        ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
        ctx.fillStyle = '#0a0a1a';
        ctx.fillRect(0, 0, this.canvas.width, this.canvas.height);
    }
}
