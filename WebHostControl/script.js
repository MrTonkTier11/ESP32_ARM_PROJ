// ==========================================
// ESP32 ROBOTIC ARM CONTROL
// JavaScript Frontend Controller
// ==========================================

const state = {
    1: 90, // Shoulder
    2: 90, // Elbow
    3: 90, // Claw
    4: 90  // Base
};

let sendTimers = {};
let isPolling = false;

// ==========================================
// CONNECTION STATUS HELPER
// ==========================================

function setConnected(connected, connecting = false) {
    const dot = document.getElementById('status-dot');
    const text = document.getElementById('status-text');
    if (!dot || !text) return;

    dot.classList.remove('disconnected', 'connecting');

    if (connecting) {
        dot.classList.add('connecting');
        text.textContent = 'Connecting...';
    } else if (connected) {
        text.textContent = 'Connected (Wi-Fi AP)';
    } else {
        dot.classList.add('disconnected');
        text.textContent = 'Disconnected / Offline';
    }
}

// ==========================================
// UPDATE ROBOTIC ARM VISUALIZER
// ==========================================

function updateVisualizer() {
    // Shoulder rotation (matches Python 2D visualizer)
    const sAngle = (state[1] - 90) * 0.8;

    // Elbow rotation
    const eAngle = (state[2] - 90) * 0.8;

    // Claw opening / closing
    const clawSpread = Math.max(2, Math.min(22, (180 - state[3]) * 0.12));

    // Get SVG elements
    const shoulderGroup = document.getElementById('arm-shoulder-group');
    const elbowGroup = document.getElementById('arm-elbow-group');
    const baseText = document.getElementById('svg-base-text');
    const clawL = document.getElementById('svg-claw-l');
    const clawR = document.getElementById('svg-claw-r');

    // Update shoulder
    if (shoulderGroup) {
        shoulderGroup.setAttribute('transform', `translate(160, 145) rotate(${sAngle})`);
    }

    // Update elbow
    if (elbowGroup) {
        elbowGroup.setAttribute('transform', `translate(0, -55) rotate(${eAngle})`);
    }

    // Update base angle display
    if (baseText) {
        baseText.textContent = `${state[4]}°`;
    }

    // Update left claw pincer
    if (clawL) {
        clawL.setAttribute('x2', -clawSpread);
        clawL.setAttribute('y2', -14);
    }

    // Update right claw pincer
    if (clawR) {
        clawR.setAttribute('x2', clawSpread);
        clawR.setAttribute('y2', -14);
    }
}

// ==========================================
// SET SERVO POSITION
// ==========================================

function setJoint(servoId, value, sendToServer = true) {
    // Restrict servo angle between 0 and 180
    value = Math.max(0, Math.min(180, parseInt(value)));

    // Update local servo state
    state[servoId] = value;

    // Get slider and angle badge
    const slider = document.getElementById('slider' + servoId);
    const valBadge = document.getElementById('val' + servoId);

    // Update slider position
    if (slider) {
        slider.value = value;
    }

    // Update displayed angle
    if (valBadge) {
        valBadge.textContent = value + '°';
    }

    // Update SVG visualizer
    updateVisualizer();

    if (!sendToServer) {
        return;
    }

    // Debounce HTTP requests (30ms)
    clearTimeout(sendTimers[servoId]);
    sendTimers[servoId] = setTimeout(() => {
        fetch(`/api/set?s=${servoId}&v=${value}`)
            .then(res => {
                if (res.ok) setConnected(true);
            })
            .catch(e => {
                console.warn('Fetch error:', e);
                setConnected(false);
            });
    }, 30);
}

// ==========================================
// SLIDER CONTROL
// ==========================================

function onSlider(servoId, value) {
    setJoint(servoId, value, true);
}

// ==========================================
// INCREMENT / DECREMENT CONTROL
// ==========================================

function stepServo(servoId, delta) {
    setJoint(servoId, state[servoId] + delta, true);
}

// ==========================================
// BASE CONTINUOUS JOG & STEP CONTROLS
// ==========================================

let currentJogSpeed = 200;
let jogKeepAliveTimer = null;
let activeJogDir = 0;

function setJogSpeed(spd) {
    currentJogSpeed = spd;
    ['spd-slow', 'spd-norm', 'spd-fast'].forEach(id => {
        const btn = document.getElementById(id);
        if (btn) btn.classList.remove('active');
    });

    if (spd <= 140) {
        document.getElementById('spd-slow')?.classList.add('active');
    } else if (spd >= 300) {
        document.getElementById('spd-fast')?.classList.add('active');
    } else {
        document.getElementById('spd-norm')?.classList.add('active');
    }
}

function updateBaseBadge(text, isMoving = false) {
    const badge = document.getElementById('val4');
    if (!badge) return;
    badge.textContent = text;
    if (isMoving) {
        badge.style.color = '#00d9ff';
        badge.style.borderColor = '#00d9ff';
    } else {
        badge.style.color = '#fff';
        badge.style.borderColor = 'var(--card-border)';
    }
}

function startJog(dir) {
    if (activeJogDir === dir) return;
    activeJogDir = dir;

    const dirStr = (dir > 0) ? 'CW' : 'CCW';
    updateBaseBadge(dir > 0 ? 'ROTATING CW ▶' : '◀ ROTATING CCW', true);

    const activeBtn = document.getElementById(dir > 0 ? 'btn-jog-cw' : 'btn-jog-ccw');
    if (activeBtn) activeBtn.classList.add('active');

    // Send initial jog command
    fetch(`/api/jog?dir=${dirStr}&speed=${currentJogSpeed}`)
        .then(res => { if (res.ok) setConnected(true); })
        .catch(e => { console.warn(e); setConnected(false); });

    // Send keepalive pulses every 500ms while button is held
    clearInterval(jogKeepAliveTimer);
    jogKeepAliveTimer = setInterval(() => {
        if (activeJogDir !== 0) {
            fetch(`/api/jog?dir=${dirStr}&speed=${currentJogSpeed}`).catch(() => {});
        }
    }, 500);
}

function stopJog() {
    if (activeJogDir === 0 && !jogKeepAliveTimer) return;
    activeJogDir = 0;
    clearInterval(jogKeepAliveTimer);
    jogKeepAliveTimer = null;

    document.getElementById('btn-jog-cw')?.classList.remove('active');
    document.getElementById('btn-jog-ccw')?.classList.remove('active');
    updateBaseBadge('STOPPED', false);

    fetch('/api/jog?dir=STOP')
        .then(res => { if (res.ok) setConnected(true); })
        .catch(e => { console.warn(e); setConnected(false); });
}

function nudgeBase(dir, ms) {
    const dirStr = (dir > 0) ? 'CW' : 'CCW';
    updateBaseBadge(dir > 0 ? `CW (${ms}ms) ▶` : `◀ CCW (${ms}ms)`, true);

    fetch(`/api/step?dir=${dirStr}&ms=${ms}&speed=${currentJogSpeed}`)
        .then(res => {
            if (res.ok) setConnected(true);
            setTimeout(() => {
                if (activeJogDir === 0) updateBaseBadge('STOPPED', false);
            }, ms + 50);
        })
        .catch(e => {
            console.warn(e);
            setConnected(false);
            updateBaseBadge('STOPPED', false);
        });
}

// ==========================================
// STOP BASE SERVO
// ==========================================

function stopBaseCmd() {
    activeJogDir = 0;
    clearInterval(jogKeepAliveTimer);
    jogKeepAliveTimer = null;
    document.getElementById('btn-jog-cw')?.classList.remove('active');
    document.getElementById('btn-jog-ccw')?.classList.remove('active');
    updateBaseBadge('STOPPED', false);

    fetch('/api/stop')
        .then(res => {
            if (res.ok) setConnected(true);
        })
        .catch(e => {
            console.warn(e);
            setConnected(false);
        });
}

// ==========================================
// RESET ALL SERVOS
// ==========================================

function resetAllCmd() {
    applyPreset(90, 90, 90, 90);

    fetch('/api/reset')
        .then(res => {
            if (res.ok) setConnected(true);
            updateBaseBadge('STOPPED', false);
        })
        .catch(e => {
            console.warn(e);
            setConnected(false);
        });
}

// ==========================================
// PRESET POSITIONS
// ==========================================

function applyPreset(s1, s2, s3, s4) {
    setJoint(1, s1, true);
    setJoint(2, s2, true);
    setJoint(3, s3, true);
    stopJog();
}

// ==========================================
// SERVO STATE SYNCHRONIZATION
// ==========================================

function syncStatus() {
    if (isPolling) return;
    isPolling = true;

    fetch('/api/status')
        .then(res => {
            if (!res.ok) {
                throw new Error('Status request failed');
            }
            return res.json();
        })
        .then(data => {
            setConnected(true);

            // Synchronize positional joints without echoing commands back
            if (data.s1 !== undefined) setJoint(1, data.s1, false);
            if (data.s2 !== undefined) setJoint(2, data.s2, false);
            if (data.s3 !== undefined) setJoint(3, data.s3, false);

            // Synchronize continuous base state if not actively holding button
            if (activeJogDir === 0 && data.baseState !== undefined) {
                if (data.baseState === 1) updateBaseBadge('ROTATING CW ▶', true);
                else if (data.baseState === -1) updateBaseBadge('◀ ROTATING CCW', true);
                else updateBaseBadge('STOPPED', false);
            }
        })
        .catch(() => {
            setConnected(false);
            updateVisualizer();
        })
        .finally(() => {
            isPolling = false;
        });
}

// Initial synchronization and periodic poll (every 3 seconds)
setConnected(false, true);
syncStatus();
setInterval(syncStatus, 3000);
