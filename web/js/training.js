/**
 * TrainingUI - Training controls, push-based rendering, stats display.
 */
class TrainingUI {
    constructor(renderer, chart) {
        this.renderer = renderer;
        this.chart = chart;
        this.isRunning = false;
        this.isPaused = false;
        this._rafId = null;
        this._pendingState = null;
        this._trackImageLoaded = false;
        this._trackData = null;

        // Register global receiver for Python push
        window._onTrainingState = (state) => {
            this._pendingState = state;
        };

        this._bindControls();
        this._refreshCheckpoints();
        this._updateButtons();
    }

    show() {
        this._refreshCheckpoints();
        this._updateButtons();
    }

    _bindControls() {
        document.getElementById('start-training-btn').addEventListener('click', () => this.startTraining());
        document.getElementById('pause-training-btn').addEventListener('click', () => this.togglePause());
        document.getElementById('stop-training-btn').addEventListener('click', () => this.stopTraining());

        // Speed slider
        const speedSlider = document.getElementById('speed-slider');
        speedSlider.addEventListener('input', async () => {
            const val = parseInt(speedSlider.value);
            document.getElementById('speed-label').textContent = `x${val}`;
            document.getElementById('bottom-speed-val').textContent = `x${val}`;
            if (this.isRunning) {
                await pywebview.api.set_speed(val);
            }
        });

        // Show rays toggle
        document.getElementById('show-rays').addEventListener('change', async (e) => {
            this.renderer.showRays = e.target.checked;
            if (this.isRunning) {
                await pywebview.api.toggle_rays(e.target.checked);
            }
        });

        // Checkpoint save/export
        document.getElementById('save-checkpoint-btn').addEventListener('click', async () => {
            try {
                const path = await pywebview.api.save_checkpoint();
                if (path) {
                    showToast('Checkpoint saved!');
                    await this._refreshCheckpoints();
                }
            } catch (e) {
                showToast('Checkpoint save failed', 'error');
            }
        });

        document.getElementById('export-best-btn').addEventListener('click', async () => {
            try {
                const result = await pywebview.api.export_best_racer();
                if (result.success) {
                    showToast(`Exported: ${result.path}`);
                } else {
                    showToast(result.error || 'Export failed', 'error');
                }
            } catch (e) {
                showToast('Export failed: ' + e.message, 'error');
            }
        });

        // Resume from checkpoint
        document.getElementById('resume-checkpoint-btn').addEventListener('click', async () => {
            const select = document.getElementById('checkpoint-select');
            if (!select.value) return;

            // Stop any existing training first
            this.stopPolling();

            // Get track from editor (same as startTraining)
            const editor = window.app.editor;
            const trackData = editor.getTrackData();
            this._trackData = trackData;

            const trackImg = new Image();
            trackImg.src = editor.roadCanvas.toDataURL();
            await new Promise((resolve) => { trackImg.onload = resolve; });
            this.renderer.setTrackImage(trackImg);
            this._trackImageLoaded = true;

            try {
                const result = await pywebview.api.resume_training(select.value, JSON.stringify(trackData));
                if (result.success) {
                    this.isRunning = true;
                    this.isPaused = false;
                    this._updateButtons();
                    this.startPolling();
                    this.chart.clear();
                    this.renderer.clearTireMarks();
                    showToast('Resumed from checkpoint!');
                } else {
                    showToast(result.error || 'Resume failed', 'error');
                }
            } catch (e) {
                showToast('Resume failed: ' + e.message, 'error');
            }
        });
    }

    async startTraining() {
        // Get track data from editor
        const editor = window.app.editor;
        const trackData = editor.getTrackData();

        // Store for rendering
        this._trackData = trackData;

        // Build track image from editor's road canvas
        const trackImg = new Image();
        trackImg.src = editor.roadCanvas.toDataURL();
        await new Promise((resolve) => { trackImg.onload = resolve; });
        this.renderer.setTrackImage(trackImg);
        this._trackImageLoaded = true;

        this.renderer.clearTireMarks();

        try {
            const result = await pywebview.api.start_training(JSON.stringify(trackData));
            if (result.success) {
                this.isRunning = true;
                this.isPaused = false;
                this._updateButtons();
                this.startPolling();
                this.chart.clear();
                showToast('Training started!');
            } else {
                showToast(result.error || 'Failed to start', 'error');
            }
        } catch (e) {
            showToast('Failed to start: ' + e.message, 'error');
        }
    }

    async togglePause() {
        if (this.isPaused) {
            await pywebview.api.unpause_training();
            this.isPaused = false;
        } else {
            await pywebview.api.pause_training();
            this.isPaused = true;
        }
        this._updateButtons();
    }

    async stopTraining() {
        await pywebview.api.stop_training();
        this.isRunning = false;
        this.isPaused = false;
        this.stopPolling();
        this._updateButtons();
        showToast('Training stopped');
        await this._refreshCheckpoints();
    }

    _updateButtons() {
        const startBtn = document.getElementById('start-training-btn');
        const pauseBtn = document.getElementById('pause-training-btn');
        const stopBtn = document.getElementById('stop-training-btn');
        const saveBtn = document.getElementById('save-checkpoint-btn');
        const exportBtn = document.getElementById('export-best-btn');
        const resumeBtn = document.getElementById('resume-checkpoint-btn');
        const dot = document.getElementById('training-dot');
        const status = document.getElementById('training-status');

        startBtn.disabled = this.isRunning;
        pauseBtn.disabled = !this.isRunning;
        stopBtn.disabled = !this.isRunning;
        saveBtn.disabled = !this.isRunning;
        exportBtn.disabled = !this.isRunning;
        resumeBtn.disabled = this.isRunning;

        pauseBtn.textContent = this.isPaused ? 'Resume' : 'Pause';

        dot.className = 'dot';
        if (this.isRunning && !this.isPaused) {
            dot.classList.add('running');
            status.textContent = 'Running';
        } else if (this.isPaused) {
            dot.classList.add('paused');
            status.textContent = 'Paused';
        } else {
            status.textContent = 'Stopped';
        }
    }

    // === Render Loop (push-based) ===

    startPolling() {
        if (this._rafId) return;
        this._pendingState = null;
        this._renderLoop();
    }

    stopPolling() {
        if (this._rafId) {
            cancelAnimationFrame(this._rafId);
            this._rafId = null;
        }
        this._pendingState = null;
    }

    _renderLoop() {
        if (!this.isRunning) {
            this._rafId = null;
            return;
        }

        const state = this._pendingState;
        if (state && state.cars) {
            this._pendingState = null;
            this._renderState(state);
            this._updateStats(state);
        }

        this._rafId = requestAnimationFrame(() => this._renderLoop());
    }

    _renderState(state) {
        const canvas = this.renderer.canvas;
        const ctx = this.renderer.ctx;

        // Clear and draw track
        this.renderer.clear();
        this.renderer.drawTrack();

        // Draw checkpoints
        if (this._trackData && this._trackData.checkpoints) {
            this.renderer.drawCheckpoints(this._trackData.checkpoints);
        }

        // Draw cars
        this.renderer.drawTrainingCars(state);

        // Draw rays
        this.renderer.drawRays(state);
    }

    _updateStats(state) {
        document.getElementById('stat-generation').textContent = state.generation || 0;
        document.getElementById('stat-alive').textContent =
            `${state.alive_count || 0} / ${state.total_count || 0}`;
        document.getElementById('stat-best-fitness').textContent =
            Math.round(state.best_fitness || 0).toLocaleString();
        document.getElementById('stat-species').textContent = state.species_count || 0;

        // Bottom bar
        document.getElementById('bottom-gen-val').textContent = state.generation || 0;
        document.getElementById('bottom-alive-val').textContent =
            `${state.alive_count || 0}/${state.total_count || 0}`;
        document.getElementById('bottom-best-val').textContent =
            Math.round(state.best_fitness || 0).toLocaleString();

        // Update avg fitness
        if (state.history && state.history.length > 0) {
            const latest = state.history[state.history.length - 1];
            document.getElementById('stat-avg-fitness').textContent =
                Math.round(latest.avg || 0).toLocaleString();
        }

        // Update chart
        if (state.history) {
            this.chart.update(state.history);
        }
    }

    async _refreshCheckpoints() {
        try {
            const checkpoints = await pywebview.api.list_checkpoints();
            const select = document.getElementById('checkpoint-select');
            select.innerHTML = '<option value="">-- Select --</option>';
            checkpoints.forEach(cp => {
                const option = document.createElement('option');
                option.value = cp.path;
                option.textContent = cp.name;
                select.appendChild(option);
            });
        } catch (e) {
            // Ignore
        }
    }
}
