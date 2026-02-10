/**
 * RaceUI - Race mode: load track, add racers, start race, leaderboard.
 */
class RaceUI {
    constructor(renderer) {
        this.renderer = renderer;
        this.racers = [];
        this.racerPaths = [];
        this.isRunning = false;
        this._pollId = null;
        this._trackData = null;
        this._trackImageLoaded = false;

        this._bindControls();
    }

    _bindControls() {
        document.getElementById('race-load-track-btn').addEventListener('click', () => this.loadTrack());
        document.getElementById('add-racer-btn').addEventListener('click', () => this.addRacer());
        document.getElementById('remove-racer-btn').addEventListener('click', () => this.removeLastRacer());
        document.getElementById('start-race-btn').addEventListener('click', () => this.startRace());
        document.getElementById('stop-race-btn').addEventListener('click', () => this.stopRace());
    }

    async loadTrack() {
        try {
            const result = await pywebview.api.load_track();
            if (result.success) {
                this._trackData = result.data;
                document.getElementById('race-track-name').textContent =
                    result.data.track_name || 'Loaded';

                // Build track image
                if (result.data.road_mask_base64) {
                    const img = new Image();
                    img.src = 'data:image/png;base64,' + result.data.road_mask_base64;
                    await new Promise((resolve) => { img.onload = resolve; });
                    this.renderer.setTrackImage(img);
                    this._trackImageLoaded = true;

                    // Preview the track
                    this.renderer.clear();
                    this.renderer.drawTrack();
                    if (result.data.checkpoints) {
                        this.renderer.drawCheckpoints(result.data.checkpoints);
                    }
                    if (result.data.start) {
                        this.renderer.drawStartPosition(result.data.start);
                    }
                }

                this._updateStartButton();
                showToast('Track loaded for race!');
            }
        } catch (e) {
            showToast('Failed to load track: ' + e.message, 'error');
        }
    }

    async addRacer() {
        try {
            const filepath = await pywebview.api.open_file_dialog(['Racer Files (*.racer)']);
            if (!filepath) return;

            // Load racer info
            const racers = await pywebview.api.list_racers();
            const racer = racers.find(r => r.path === filepath);

            this.racerPaths.push(filepath);
            this.racers.push(racer || { name: filepath.split('/').pop(), path: filepath });

            this._updateRacerList();
            this._updateStartButton();
            showToast('Racer added!');
        } catch (e) {
            showToast('Failed to add racer: ' + e.message, 'error');
        }
    }

    removeLastRacer() {
        if (this.racers.length > 0) {
            this.racers.pop();
            this.racerPaths.pop();
            this._updateRacerList();
            this._updateStartButton();
        }
    }

    _updateRacerList() {
        const list = document.getElementById('racer-list');
        const colors = ['#FF4444', '#4488FF', '#44CC44', '#FFAA00', '#CC44CC',
                        '#44CCCC', '#FF8844', '#8844FF', '#CCCC44', '#FF44AA'];

        list.innerHTML = '';
        this.racers.forEach((racer, i) => {
            const item = document.createElement('div');
            item.className = 'racer-item';

            const config = racer.car_config || {};
            const driftStr = config.drift_enabled ? 'ON' : 'OFF';
            const speedStr = config.max_speed || '?';

            item.innerHTML = `
                <div class="racer-color" style="background:${colors[i % colors.length]}"></div>
                <div class="racer-info">
                    <div class="racer-name">${racer.name || 'Unknown'}</div>
                    <div class="racer-details">Gen ${racer.generation || '?'} | drift: ${driftStr} | spd: ${speedStr}</div>
                </div>
            `;
            list.appendChild(item);
        });

        document.getElementById('remove-racer-btn').disabled = this.racers.length === 0;
    }

    _updateStartButton() {
        const canStart = this._trackData && this.racers.length >= 2;
        document.getElementById('start-race-btn').disabled = !canStart;
    }

    async startRace() {
        if (!this._trackData || this.racers.length < 2) return;

        const numLaps = parseInt(document.getElementById('race-laps').value) || 3;

        try {
            const result = await pywebview.api.start_race(
                JSON.stringify(this._trackData),
                this.racerPaths,
                numLaps
            );

            if (result.success) {
                this.isRunning = true;
                document.getElementById('start-race-btn').style.display = 'none';
                document.getElementById('stop-race-btn').style.display = '';
                this.startPolling();
                showToast('Race started!');
            } else {
                showToast(result.error || 'Failed to start race', 'error');
            }
        } catch (e) {
            showToast('Failed to start race: ' + e.message, 'error');
        }
    }

    async stopRace() {
        await pywebview.api.stop_race();
        this.isRunning = false;
        this.stopPolling();
        document.getElementById('start-race-btn').style.display = '';
        document.getElementById('stop-race-btn').style.display = 'none';
    }

    // === Polling ===

    startPolling() {
        if (this._pollId) return;
        this._poll();
    }

    stopPolling() {
        if (this._pollId) {
            cancelAnimationFrame(this._pollId);
            this._pollId = null;
        }
    }

    async _poll() {
        if (!this.isRunning) {
            this._pollId = null;
            return;
        }

        try {
            const state = await pywebview.api.get_race_state();
            if (state && state.cars) {
                this._renderState(state);
                this._updateLeaderboard(state.rankings);

                if (state.finished) {
                    this.isRunning = false;
                    document.getElementById('start-race-btn').style.display = '';
                    document.getElementById('stop-race-btn').style.display = 'none';
                    showToast('Race finished!');
                }
            }
        } catch (e) {
            // Polling error
        }

        this._pollId = requestAnimationFrame(() => this._poll());
    }

    _renderState(state) {
        this.renderer.clear();
        this.renderer.drawTrack();

        if (this._trackData && this._trackData.checkpoints) {
            this.renderer.drawCheckpoints(this._trackData.checkpoints);
        }

        this.renderer.drawRaceCars(state.cars);
        this.renderer.drawRankings(state.rankings);
    }

    _updateLeaderboard(rankings) {
        if (!rankings) return;
        const container = document.getElementById('race-leaderboard');
        container.innerHTML = '';

        rankings.forEach((r, i) => {
            const item = document.createElement('div');
            item.className = `leaderboard-item${r.dnf ? ' dnf' : ''}`;

            let timeStr;
            if (r.finished) {
                timeStr = `${r.time.toFixed(1)}s`;
            } else if (r.dnf) {
                timeStr = 'DNF';
            } else {
                timeStr = `Lap ${r.lap}`;
            }

            item.innerHTML = `
                <span class="leaderboard-pos">${i + 1}.</span>
                <div class="racer-color" style="background:${r.color}"></div>
                <span class="leaderboard-name">${r.name}</span>
                <span class="leaderboard-time">${timeStr}</span>
            `;
            container.appendChild(item);
        });
    }
}
