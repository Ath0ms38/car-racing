/**
 * FitnessEditorUI - Read-only preview of config/fitness.py + reload button.
 */
class FitnessEditorUI {
    constructor() {
        this.textarea = document.getElementById('fitness-code');
        this.statusEl = document.getElementById('fitness-status');
        this.filePath = '';

        this._bindEvents();
    }

    _bindEvents() {
        document.getElementById('reload-fitness-btn').addEventListener('click', () => this.reload());
    }

    async loadCode() {
        try {
            this.filePath = await pywebview.api.get_fitness_file_path();
            const code = await pywebview.api.get_fitness_code();
            this.textarea.value = code;
            document.getElementById('fitness-file-path').textContent = this.filePath;
            this.showValid();
        } catch (e) {
            console.error('Failed to load fitness code:', e);
        }
    }

    async reload() {
        try {
            const result = await pywebview.api.reload_fitness();
            const code = await pywebview.api.get_fitness_code();
            this.textarea.value = code;

            if (result.valid) {
                this.showValid();
                showToast('Fitness function reloaded!');
            } else {
                this.showError(result.error);
                showToast('Fitness error: ' + result.error, 'error');
            }
        } catch (e) {
            this.showError(e.message);
        }
    }

    showValid() {
        this.statusEl.textContent = 'Valid';
        this.statusEl.className = 'valid';
    }

    showError(error) {
        this.statusEl.textContent = error;
        this.statusEl.className = 'error';
    }
}
