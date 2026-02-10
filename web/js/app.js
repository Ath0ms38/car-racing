/**
 * App Controller - manages mode switching, initialization, and main polling loop.
 */
class App {
    constructor() {
        this.mode = 'editor';
        this.canvas = document.getElementById('main-canvas');
        this.ctx = this.canvas.getContext('2d');
        this.renderer = null;
        this.editor = null;
        this.trainingUI = null;
        this.raceUI = null;
        this.configPanel = null;
        this.fitnessEditor = null;
        this.chart = null;
        this._pollId = null;
    }

    async init() {
        // Wait for pywebview API
        await this._waitForApi();

        // Initialize sub-modules
        this.renderer = new Renderer(this.canvas, this.ctx);
        this.editor = new Editor(this.canvas, this.ctx, this.renderer);
        this.chart = new FitnessChart(document.getElementById('fitness-chart'));
        this.trainingUI = new TrainingUI(this.renderer, this.chart);
        this.raceUI = new RaceUI(this.renderer);
        this.configPanel = new ConfigPanel();
        this.fitnessEditor = new FitnessEditorUI();

        // Tab switching
        document.querySelectorAll('.tab').forEach(tab => {
            tab.addEventListener('click', () => this.switchMode(tab.dataset.mode));
        });

        // Collapsible sections
        document.querySelectorAll('.collapsible-header').forEach(header => {
            header.addEventListener('click', () => {
                header.closest('.collapsible').classList.toggle('collapsed');
            });
        });

        // Start in collapsed state for config sections
        document.querySelectorAll('.collapsible').forEach(el => {
            el.classList.add('collapsed');
        });

        // Initialize editor
        this.editor.init();

        // Load configs
        await this.configPanel.loadConfigs();
        await this.fitnessEditor.loadCode();

        console.log('App initialized');
    }

    async _waitForApi() {
        // pywebview exposes api at window.pywebview.api
        // Must wait for 'pywebviewready' event AND verify methods are populated
        return new Promise((resolve) => {
            const check = () => {
                if (window.pywebview && window.pywebview.api &&
                    typeof window.pywebview.api.get_car_config === 'function') {
                    resolve();
                } else {
                    setTimeout(check, 100);
                }
            };
            if (window.pywebview && window.pywebview.api &&
                typeof window.pywebview.api.get_car_config === 'function') {
                resolve();
            } else {
                window.addEventListener('pywebviewready', () => {
                    // Even after the event, methods may take a moment to populate
                    check();
                });
                // Also poll in case event already fired
                setTimeout(check, 100);
            }
        });
    }

    switchMode(mode) {
        this.mode = mode;

        // Update tabs
        document.querySelectorAll('.tab').forEach(tab => {
            tab.classList.toggle('active', tab.dataset.mode === mode);
        });

        // Update panels
        document.querySelectorAll('.panel-content').forEach(panel => {
            panel.classList.remove('active');
        });
        document.getElementById(`${mode}-panel`).classList.add('active');

        // Update mode label
        const modeNames = { editor: 'Editor', training: 'Training', race: 'Race' };
        document.getElementById('mode-label').textContent = modeNames[mode] || mode;

        // Toggle bottom bar elements
        const isTraining = mode === 'training';
        document.getElementById('bottom-gen').style.display = isTraining ? '' : 'none';
        document.getElementById('bottom-alive').style.display = isTraining ? '' : 'none';
        document.getElementById('bottom-best').style.display = isTraining ? '' : 'none';
        document.getElementById('bottom-speed').style.display = isTraining ? '' : 'none';

        // Handle mode-specific setup
        if (mode === 'editor') {
            this.editor.activate();
            this.trainingUI.stopPolling();
            this.raceUI.stopPolling();
        } else if (mode === 'training') {
            this.editor.deactivate();
            this.raceUI.stopPolling();
            this.trainingUI.show();
        } else if (mode === 'race') {
            this.editor.deactivate();
            this.trainingUI.stopPolling();
        }
    }
}

// Toast notifications
function showToast(message, type = 'success') {
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    document.body.appendChild(toast);
    setTimeout(() => toast.remove(), 3000);
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.app = new App();
    window.app.init().catch(err => console.error('Init error:', err));
});
