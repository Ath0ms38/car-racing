/**
 * Editor - Track editor with painting, checkpoints, start position, undo/redo.
 */
class Editor {
    constructor(canvas, ctx, renderer) {
        this.canvas = canvas;
        this.ctx = ctx;
        this.renderer = renderer;

        this.tool = 'road';
        this.brushSize = 20;
        this.isDrawing = false;
        this.isActive = false;

        // Offscreen canvas for road drawing
        this.roadCanvas = null;
        this.roadCtx = null;

        this.checkpoints = [];
        this.startPos = null;
        this._cpDragStart = null;  // For checkpoint placement

        this.undoStack = [];
        this.redoStack = [];

        this.GRASS_COLOR = '#4CAF50';
        this.ROAD_COLOR = '#808080';
    }

    init() {
        this.initCanvas(this.canvas.width, this.canvas.height);
        this._bindEvents();
        this._bindButtons();
        this.activate();
    }

    initCanvas(width, height) {
        this.roadCanvas = document.createElement('canvas');
        this.roadCanvas.width = width;
        this.roadCanvas.height = height;
        this.roadCtx = this.roadCanvas.getContext('2d');

        // Fill with grass
        this.roadCtx.fillStyle = this.GRASS_COLOR;
        this.roadCtx.fillRect(0, 0, width, height);

        this._render();
    }

    activate() {
        this.isActive = true;
        this.canvas.style.cursor = 'crosshair';
        this._render();
    }

    deactivate() {
        this.isActive = false;
        this.isDrawing = false;
    }

    // === Event Binding ===

    _bindEvents() {
        this.canvas.addEventListener('mousedown', (e) => this._onMouseDown(e));
        this.canvas.addEventListener('mousemove', (e) => this._onMouseMove(e));
        this.canvas.addEventListener('mouseup', (e) => this._onMouseUp(e));
        this.canvas.addEventListener('mouseleave', (e) => this._onMouseUp(e));
        this.canvas.addEventListener('wheel', (e) => this._onWheel(e));

        // Keyboard
        document.addEventListener('keydown', (e) => {
            if (!this.isActive) return;
            if (e.ctrlKey && e.key === 'z') { e.preventDefault(); this.undo(); }
            if (e.ctrlKey && e.key === 'y') { e.preventDefault(); this.redo(); }
        });
    }

    _bindButtons() {
        // Tool buttons
        document.querySelectorAll('.tool-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                this.setTool(btn.dataset.tool);
                document.querySelectorAll('.tool-btn').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
            });
        });

        // Brush size
        const brushSlider = document.getElementById('brush-size');
        brushSlider.addEventListener('input', () => {
            this.brushSize = parseInt(brushSlider.value);
            document.getElementById('brush-size-label').textContent = this.brushSize;
        });

        // Undo/Redo/Clear
        document.getElementById('undo-btn').addEventListener('click', () => this.undo());
        document.getElementById('redo-btn').addEventListener('click', () => this.redo());
        document.getElementById('clear-btn').addEventListener('click', () => {
            if (confirm('Clear all? This cannot be undone.')) this.clearAll();
        });

        // Delete checkpoint
        document.getElementById('delete-checkpoint-btn').addEventListener('click', () => {
            if (this.checkpoints.length > 0) {
                this.pushUndo();
                this.checkpoints.pop();
                this._updateCheckpointUI();
                this._render();
            }
        });

        // Save/Load
        document.getElementById('save-track-btn').addEventListener('click', () => this._saveTrack());
        document.getElementById('load-track-btn').addEventListener('click', () => this._loadTrack());
    }

    // === Tools ===

    setTool(tool) {
        this.tool = tool;
        if (tool === 'road' || tool === 'erase') {
            this.canvas.style.cursor = 'crosshair';
        } else if (tool === 'checkpoint') {
            this.canvas.style.cursor = 'crosshair';
        } else if (tool === 'start') {
            this.canvas.style.cursor = 'crosshair';
        }
    }

    setBrushSize(size) {
        this.brushSize = size;
    }

    // === Mouse Handlers ===

    _getMousePos(e) {
        const rect = this.canvas.getBoundingClientRect();
        const scaleX = this.canvas.width / rect.width;
        const scaleY = this.canvas.height / rect.height;
        return {
            x: (e.clientX - rect.left) * scaleX,
            y: (e.clientY - rect.top) * scaleY,
        };
    }

    _onMouseDown(e) {
        if (!this.isActive) return;
        const pos = this._getMousePos(e);

        if (this.tool === 'road' || this.tool === 'erase') {
            this.pushUndo();
            this.isDrawing = true;
            this._paint(pos.x, pos.y);
        } else if (this.tool === 'checkpoint') {
            this._cpDragStart = { x: pos.x, y: pos.y };
        } else if (this.tool === 'start') {
            this.pushUndo();
            this.startPos = { x: pos.x, y: pos.y, angle: 0 };
            this._render();
        }
    }

    _onMouseMove(e) {
        if (!this.isActive) return;
        const pos = this._getMousePos(e);

        if (this.isDrawing && (this.tool === 'road' || this.tool === 'erase')) {
            this._paint(pos.x, pos.y);
        }

        // Preview checkpoint line
        if (this.tool === 'checkpoint' && this._cpDragStart) {
            this._render();
            this.ctx.beginPath();
            this.ctx.moveTo(this._cpDragStart.x, this._cpDragStart.y);
            this.ctx.lineTo(pos.x, pos.y);
            this.ctx.strokeStyle = '#FFD700';
            this.ctx.lineWidth = 3;
            this.ctx.setLineDash([5, 5]);
            this.ctx.stroke();
            this.ctx.setLineDash([]);
        }

        // Preview brush
        if ((this.tool === 'road' || this.tool === 'erase') && !this.isDrawing) {
            this._render();
            this.ctx.beginPath();
            this.ctx.arc(pos.x, pos.y, this.brushSize, 0, Math.PI * 2);
            this.ctx.strokeStyle = this.tool === 'road' ? '#aaa' : '#6b6';
            this.ctx.lineWidth = 1;
            this.ctx.setLineDash([4, 4]);
            this.ctx.stroke();
            this.ctx.setLineDash([]);
        }
    }

    _onMouseUp(e) {
        if (!this.isActive) return;
        const pos = this._getMousePos(e);

        if (this.isDrawing) {
            this.isDrawing = false;
        }

        if (this.tool === 'checkpoint' && this._cpDragStart) {
            const dx = pos.x - this._cpDragStart.x;
            const dy = pos.y - this._cpDragStart.y;
            if (Math.sqrt(dx * dx + dy * dy) > 10) {
                this.pushUndo();
                this.checkpoints.push({
                    x1: this._cpDragStart.x,
                    y1: this._cpDragStart.y,
                    x2: pos.x,
                    y2: pos.y,
                });
                this._updateCheckpointUI();
            }
            this._cpDragStart = null;
            this._render();
        }
    }

    _onWheel(e) {
        if (!this.isActive) return;

        // Scroll wheel adjusts start angle when in start mode
        if (this.tool === 'start' && this.startPos) {
            e.preventDefault();
            this.startPos.angle += e.deltaY > 0 ? 0.15 : -0.15;
            this._render();
        }

        // Scroll wheel adjusts brush size in road/erase mode
        if (this.tool === 'road' || this.tool === 'erase') {
            e.preventDefault();
            this.brushSize = Math.max(5, Math.min(80, this.brushSize + (e.deltaY > 0 ? -2 : 2)));
            document.getElementById('brush-size').value = this.brushSize;
            document.getElementById('brush-size-label').textContent = this.brushSize;
        }
    }

    // === Painting ===

    _paint(x, y) {
        const color = this.tool === 'road' ? this.ROAD_COLOR : this.GRASS_COLOR;
        this.roadCtx.beginPath();
        this.roadCtx.arc(x, y, this.brushSize, 0, Math.PI * 2);
        this.roadCtx.fillStyle = color;
        this.roadCtx.fill();
        this._render();
    }

    // === Undo/Redo ===

    pushUndo() {
        // Save current state
        const state = {
            roadImage: this.roadCtx.getImageData(0, 0, this.roadCanvas.width, this.roadCanvas.height),
            checkpoints: JSON.parse(JSON.stringify(this.checkpoints)),
            startPos: this.startPos ? { ...this.startPos } : null,
        };
        this.undoStack.push(state);
        if (this.undoStack.length > 50) this.undoStack.shift();
        this.redoStack = [];
        this._updateUndoButtons();
    }

    undo() {
        if (this.undoStack.length === 0) return;
        // Save current to redo
        this.redoStack.push({
            roadImage: this.roadCtx.getImageData(0, 0, this.roadCanvas.width, this.roadCanvas.height),
            checkpoints: JSON.parse(JSON.stringify(this.checkpoints)),
            startPos: this.startPos ? { ...this.startPos } : null,
        });

        const state = this.undoStack.pop();
        this.roadCtx.putImageData(state.roadImage, 0, 0);
        this.checkpoints = state.checkpoints;
        this.startPos = state.startPos;
        this._updateCheckpointUI();
        this._updateUndoButtons();
        this._render();
    }

    redo() {
        if (this.redoStack.length === 0) return;
        this.undoStack.push({
            roadImage: this.roadCtx.getImageData(0, 0, this.roadCanvas.width, this.roadCanvas.height),
            checkpoints: JSON.parse(JSON.stringify(this.checkpoints)),
            startPos: this.startPos ? { ...this.startPos } : null,
        });

        const state = this.redoStack.pop();
        this.roadCtx.putImageData(state.roadImage, 0, 0);
        this.checkpoints = state.checkpoints;
        this.startPos = state.startPos;
        this._updateCheckpointUI();
        this._updateUndoButtons();
        this._render();
    }

    _updateUndoButtons() {
        document.getElementById('undo-btn').disabled = this.undoStack.length === 0;
        document.getElementById('redo-btn').disabled = this.redoStack.length === 0;
    }

    // === Clear ===

    clearAll() {
        this.roadCtx.fillStyle = this.GRASS_COLOR;
        this.roadCtx.fillRect(0, 0, this.roadCanvas.width, this.roadCanvas.height);
        this.checkpoints = [];
        this.startPos = null;
        this.undoStack = [];
        this.redoStack = [];
        this._updateCheckpointUI();
        this._updateUndoButtons();
        this._render();
    }

    // === Rendering ===

    _render() {
        this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
        // Draw road canvas
        this.ctx.drawImage(this.roadCanvas, 0, 0);
        // Draw checkpoints
        this.renderer.drawCheckpoints(this.checkpoints);
        // Draw start position
        if (this.startPos) {
            this.renderer.drawStartPosition(this.startPos);
        }
    }

    // === Checkpoint UI ===

    _updateCheckpointUI() {
        document.getElementById('checkpoint-count').textContent = this.checkpoints.length;
        document.getElementById('delete-checkpoint-btn').disabled = this.checkpoints.length === 0;

        const list = document.getElementById('checkpoint-list');
        list.innerHTML = '';
        this.checkpoints.forEach((cp, i) => {
            const item = document.createElement('span');
            item.className = 'checkpoint-item';
            item.textContent = `${i + 1}`;
            item.title = `(${Math.round(cp.x1)},${Math.round(cp.y1)}) - (${Math.round(cp.x2)},${Math.round(cp.y2)})`;
            list.appendChild(item);
        });
    }

    // === Save/Load ===

    getTrackData() {
        return {
            version: 1,
            width: this.canvas.width,
            height: this.canvas.height,
            road_mask_base64: this.getRoadMaskBase64(),
            start: this.startPos || { x: 100, y: 400, angle: 0 },
            checkpoints: this.checkpoints.map(cp => ({
                x1: cp.x1, y1: cp.y1, x2: cp.x2, y2: cp.y2,
            })),
        };
    }

    getRoadMaskBase64() {
        // Export the road canvas as base64 PNG (without the "data:image/png;base64," prefix)
        const dataUrl = this.roadCanvas.toDataURL('image/png');
        return dataUrl.split(',')[1];
    }

    loadTrackData(data) {
        // Load track into editor for editing
        if (data.road_mask_base64) {
            const img = new Image();
            img.onload = () => {
                this.roadCtx.drawImage(img, 0, 0);
                this._render();
            };
            img.src = 'data:image/png;base64,' + data.road_mask_base64;
        }

        if (data.start) {
            this.startPos = { x: data.start.x, y: data.start.y, angle: data.start.angle || 0 };
        }

        if (data.checkpoints) {
            this.checkpoints = data.checkpoints.map(cp => ({
                x1: cp.x1, y1: cp.y1, x2: cp.x2, y2: cp.y2,
            }));
            this._updateCheckpointUI();
        }

        this.undoStack = [];
        this.redoStack = [];
        this._updateUndoButtons();

        // Delay render to ensure image loads
        setTimeout(() => this._render(), 100);
    }

    async _saveTrack() {
        const trackData = this.getTrackData();
        try {
            const result = await pywebview.api.save_track(JSON.stringify(trackData));
            if (result.success) {
                showToast('Track saved!');
            } else {
                showToast(result.error || 'Save failed', 'error');
            }
        } catch (e) {
            showToast('Save failed: ' + e.message, 'error');
        }
    }

    async _loadTrack() {
        try {
            const result = await pywebview.api.load_track();
            if (result.success) {
                this.loadTrackData(result.data);
                showToast('Track loaded!');
            } else if (result.error !== 'Cancelled') {
                showToast(result.error || 'Load failed', 'error');
            }
        } catch (e) {
            showToast('Load failed: ' + e.message, 'error');
        }
    }
}
