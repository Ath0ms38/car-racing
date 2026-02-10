/**
 * Renderer - handles all canvas drawing: track, cars, rays, checkpoints, race.
 */
class Renderer {
    constructor(canvas, ctx) {
        this.canvas = canvas;
        this.ctx = ctx;
        this.trackImage = null;
        this.showRays = true;
        this.camera = { x: 0, y: 0, zoom: 1 };

        // Car dimensions (fixed)
        this.CAR_WIDTH = 30;
        this.CAR_HEIGHT = 15;
    }

    clear() {
        this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
    }

    // === Track ===

    setTrackImage(imageData) {
        this.trackImage = imageData;
    }

    drawTrack() {
        if (this.trackImage) {
            this.ctx.drawImage(this.trackImage, 0, 0);
        }
    }

    drawCheckpoints(checkpoints) {
        if (!checkpoints) return;
        const ctx = this.ctx;

        checkpoints.forEach((cp, i) => {
            ctx.beginPath();
            ctx.moveTo(cp.x1, cp.y1);
            ctx.lineTo(cp.x2, cp.y2);
            ctx.strokeStyle = '#FFD700';
            ctx.lineWidth = 3;
            ctx.stroke();

            // Number label
            const mx = (cp.x1 + cp.x2) / 2;
            const my = (cp.y1 + cp.y2) / 2;
            ctx.fillStyle = '#FFD700';
            ctx.font = 'bold 14px sans-serif';
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.fillText(String(i + 1), mx, my - 12);
        });
    }

    drawStartPosition(start) {
        if (!start) return;
        const ctx = this.ctx;
        const { x, y, angle } = start;

        // Draw flag marker
        ctx.save();
        ctx.translate(x, y);

        // Circle
        ctx.beginPath();
        ctx.arc(0, 0, 8, 0, Math.PI * 2);
        ctx.fillStyle = '#FF4444';
        ctx.fill();
        ctx.strokeStyle = '#FFF';
        ctx.lineWidth = 2;
        ctx.stroke();

        // Direction arrow
        ctx.rotate(angle);
        ctx.beginPath();
        ctx.moveTo(12, 0);
        ctx.lineTo(24, 0);
        ctx.strokeStyle = '#FF4444';
        ctx.lineWidth = 3;
        ctx.stroke();

        // Arrowhead
        ctx.beginPath();
        ctx.moveTo(24, 0);
        ctx.lineTo(18, -5);
        ctx.lineTo(18, 5);
        ctx.closePath();
        ctx.fillStyle = '#FF4444';
        ctx.fill();

        ctx.restore();
    }

    // === Training Mode ===

    drawCars(cars) {
        if (!cars || !cars.length) return;
        const ctx = this.ctx;
        const positions = cars;

        // cars is an array of [x, y] positions, with separate angles/alive arrays
        // Actually we get the full state from training
    }

    drawTrainingCars(state) {
        if (!state || !state.cars) return;
        const ctx = this.ctx;
        const positions = state.cars;  // [[x, y], ...]
        const angles = state.angles;
        const alive = state.alive;
        const velocityAngles = state.velocity_angles;

        for (let i = 0; i < positions.length; i++) {
            const [x, y] = positions[i];
            const angle = angles[i];
            const isAlive = alive[i];

            if (x < -50 || x > this.canvas.width + 50 || y < -50 || y > this.canvas.height + 50) {
                continue;
            }

            ctx.save();
            ctx.translate(x, y);
            ctx.rotate(angle);

            if (isAlive) {
                ctx.fillStyle = 'rgba(68, 136, 255, 0.8)';
                ctx.strokeStyle = 'rgba(68, 136, 255, 1)';
            } else {
                ctx.fillStyle = 'rgba(255, 68, 68, 0.2)';
                ctx.strokeStyle = 'rgba(255, 68, 68, 0.3)';
            }

            // Draw car body
            const hw = this.CAR_WIDTH / 2;
            const hh = this.CAR_HEIGHT / 2;
            ctx.fillRect(-hw, -hh, this.CAR_WIDTH, this.CAR_HEIGHT);
            ctx.strokeRect(-hw, -hh, this.CAR_WIDTH, this.CAR_HEIGHT);

            // Front indicator
            if (isAlive) {
                ctx.fillStyle = '#fff';
                ctx.fillRect(hw - 4, -2, 4, 4);
            }

            ctx.restore();
        }
    }

    drawRays(state) {
        if (!state || !state.rays || !this.showRays) return;
        const ctx = this.ctx;

        for (let i = 0; i < state.rays.length; i++) {
            const carRays = state.rays[i];
            if (!carRays) continue;

            for (const ray of carRays) {
                const [x1, y1, x2, y2, normalizedDist] = ray;

                // Color: green (far) -> red (close)
                const r = Math.floor(255 * (1 - normalizedDist));
                const g = Math.floor(255 * normalizedDist);
                ctx.beginPath();
                ctx.moveTo(x1, y1);
                ctx.lineTo(x2, y2);
                ctx.strokeStyle = `rgba(${r}, ${g}, 0, 0.4)`;
                ctx.lineWidth = 1;
                ctx.stroke();

                // Hit point
                ctx.beginPath();
                ctx.arc(x2, y2, 2, 0, Math.PI * 2);
                ctx.fillStyle = `rgb(${r}, ${g}, 0)`;
                ctx.fill();
            }
        }
    }

    // === Race Mode ===

    drawRaceCars(cars) {
        if (!cars) return;
        const ctx = this.ctx;

        for (const car of cars) {
            const { x, y, angle, velocity_angle, drift_enabled, color, alive, name } = car;

            ctx.save();
            ctx.translate(x, y);
            ctx.rotate(angle);

            // Car body
            if (alive) {
                ctx.fillStyle = color;
                ctx.globalAlpha = 0.9;
            } else {
                ctx.fillStyle = '#666';
                ctx.globalAlpha = 0.4;
            }

            const hw = this.CAR_WIDTH / 2;
            const hh = this.CAR_HEIGHT / 2;
            ctx.fillRect(-hw, -hh, this.CAR_WIDTH, this.CAR_HEIGHT);
            ctx.strokeStyle = alive ? '#fff' : '#444';
            ctx.lineWidth = 1;
            ctx.strokeRect(-hw, -hh, this.CAR_WIDTH, this.CAR_HEIGHT);

            // Front indicator
            ctx.fillStyle = '#fff';
            ctx.globalAlpha = alive ? 0.9 : 0.3;
            ctx.fillRect(hw - 4, -2, 4, 4);

            ctx.restore();

            // Drift arrow (if drifting)
            if (alive && drift_enabled && Math.abs(angle - velocity_angle) > 0.1) {
                ctx.save();
                ctx.translate(x, y);
                ctx.rotate(velocity_angle);
                ctx.beginPath();
                ctx.moveTo(0, 0);
                ctx.lineTo(20, 0);
                ctx.strokeStyle = 'rgba(255, 255, 0, 0.5)';
                ctx.lineWidth = 2;
                ctx.setLineDash([3, 3]);
                ctx.stroke();
                ctx.setLineDash([]);
                ctx.restore();
            }

            // Name label
            ctx.globalAlpha = alive ? 1 : 0.4;
            ctx.fillStyle = color;
            ctx.font = 'bold 11px sans-serif';
            ctx.textAlign = 'center';
            ctx.fillText(name, x, y - 14);
            ctx.globalAlpha = 1;
        }
    }

    drawRankings(rankings) {
        if (!rankings) return;
        const ctx = this.ctx;

        // Draw in top-right corner
        const x = this.canvas.width - 200;
        const y = 10;

        ctx.fillStyle = 'rgba(0, 0, 0, 0.7)';
        ctx.fillRect(x - 10, y, 200, 20 + rankings.length * 22);
        ctx.strokeStyle = '#0f3460';
        ctx.strokeRect(x - 10, y, 200, 20 + rankings.length * 22);

        ctx.font = 'bold 12px sans-serif';
        ctx.fillStyle = '#FFD700';
        ctx.textAlign = 'left';
        ctx.fillText('Leaderboard', x, y + 14);

        rankings.forEach((r, i) => {
            const ry = y + 30 + i * 22;
            ctx.fillStyle = r.color || '#ccc';
            ctx.font = '12px sans-serif';
            ctx.fillText(`${i + 1}. ${r.name}`, x, ry);

            ctx.textAlign = 'right';
            if (r.finished) {
                ctx.fillText(`${r.time.toFixed(1)}s`, x + 180, ry);
            } else if (r.dnf) {
                ctx.fillStyle = '#666';
                ctx.fillText('DNF', x + 180, ry);
            } else {
                ctx.fillText(`Lap ${r.lap}`, x + 180, ry);
            }
            ctx.textAlign = 'left';
        });
    }

    // === Utilities ===

    worldToScreen(x, y) {
        return {
            x: (x - this.camera.x) * this.camera.zoom,
            y: (y - this.camera.y) * this.camera.zoom,
        };
    }

    screenToWorld(x, y) {
        return {
            x: x / this.camera.zoom + this.camera.x,
            y: y / this.camera.zoom + this.camera.y,
        };
    }
}
