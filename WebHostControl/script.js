// ==========================================
// ESP32 ROBOTIC ARM CONTROL
// JavaScript Frontend Controller
// ==========================================

const JOINT_RANGES = {
    1: { min: 90,  max: 120 },   // Shoulder (matches Python arm_state.py RANGES[1])
    2: { min: 75,  max: 180 },   // Elbow    (matches Python arm_state.py RANGES[2])
    3: { min: 0,   max: 180 },   // Claw
    4: { min: -180, max: 180 },  // Base heading
};

const state = {
    1: 90, // Shoulder (SG90)
    2: 90, // Elbow (SG90)
    3: 90, // Claw (SG90)
    4: 0   // Base virtual heading angle in degrees (0° = center/forward)
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
// ROBOTIC ARM 2D LIVE VISUALIZER
// Matches Python GUI Kinematics, Pose & Smooth Easing
// ==========================================

const visualState = {
    1: 90,
    2: 90,
    3: 90,
    4: 0
};
let animFrameId = null;

function renderVisualizer(s1, s2, s3, s4) {
    const bx = 170;
    const by = 190;
    const L1 = 66;
    const L2 = 56;
    const CLAW_LEN = 18;
    const LEAN_DEG = -10;       // Exactly matches Python ArmVisualizer.LEAN_DEG = -10
    const ELBOW_BEND_DEG = 20;  // Matches Python ArmVisualizer.ELBOW_BEND_DEG = 20

    const shoulder_deg = (s1 - 90) * 0.8;
    const elbow_deg = (s2 - 90) * 0.8;

    // claw_spread: 0 (wide open) to 180 (full grip)
    // Matches Python ArmVisualizer: (180 - claw_val) * 0.144
    const claw_spread = Math.max(2, Math.min(26, (180 - s3) * 0.144));

    // Upper arm kinematics (Shoulder: -shoulder_deg raises arm UP when value increases)
    const rad_s = (-80 + LEAN_DEG - shoulder_deg) * Math.PI / 180;
    const ex = bx + L1 * Math.cos(rad_s);
    const ey = by + L1 * Math.sin(rad_s);

    // Forearm kinematics (Elbow)
    const rad_e = rad_s + (ELBOW_BEND_DEG + elbow_deg) * Math.PI / 180;
    const wx = ex + L2 * Math.cos(rad_e);
    const wy = ey + L2 * Math.sin(rad_e);

    // Claw dual-finger pincers kinematics
    const rad_perp = rad_e + Math.PI / 2;
    const px_l1 = wx + Math.cos(rad_perp) * (claw_spread / 2);
    const py_l1 = wy + Math.sin(rad_perp) * (claw_spread / 2);
    const px_l2 = px_l1 + Math.cos(rad_e) * CLAW_LEN;
    const py_l2 = py_l1 + Math.sin(rad_e) * CLAW_LEN;

    const px_r1 = wx - Math.cos(rad_perp) * (claw_spread / 2);
    const py_r1 = wy - Math.sin(rad_perp) * (claw_spread / 2);
    const px_r2 = px_r1 + Math.cos(rad_e) * CLAW_LEN;
    const py_r2 = py_r1 + Math.sin(rad_e) * CLAW_LEN;

    // Update Upper Arm Link
    const upperArm = document.getElementById('svg-upper-arm');
    if (upperArm) {
        upperArm.setAttribute('x1', bx);
        upperArm.setAttribute('y1', by);
        upperArm.setAttribute('x2', ex.toFixed(1));
        upperArm.setAttribute('y2', ey.toFixed(1));
    }

    // Update Shoulder Joint Circle
    const shoulderJoint = document.getElementById('svg-shoulder-joint');
    if (shoulderJoint) {
        shoulderJoint.setAttribute('cx', bx);
        shoulderJoint.setAttribute('cy', by);
    }

    // Update Forearm Link
    const forearm = document.getElementById('svg-forearm');
    if (forearm) {
        forearm.setAttribute('x1', ex.toFixed(1));
        forearm.setAttribute('y1', ey.toFixed(1));
        forearm.setAttribute('x2', wx.toFixed(1));
        forearm.setAttribute('y2', wy.toFixed(1));
    }

    // Update Elbow Joint Circle
    const elbowJoint = document.getElementById('svg-elbow-joint');
    if (elbowJoint) {
        elbowJoint.setAttribute('cx', ex.toFixed(1));
        elbowJoint.setAttribute('cy', ey.toFixed(1));
    }

    // Update Wrist Joint Circle
    const wristJoint = document.getElementById('svg-wrist-joint');
    if (wristJoint) {
        wristJoint.setAttribute('cx', wx.toFixed(1));
        wristJoint.setAttribute('cy', wy.toFixed(1));
    }

    // Update Left Claw Pincer
    const clawL = document.getElementById('svg-claw-l');
    if (clawL) {
        clawL.setAttribute('points', `${wx.toFixed(1)},${wy.toFixed(1)} ${px_l1.toFixed(1)},${py_l1.toFixed(1)} ${px_l2.toFixed(1)},${py_l2.toFixed(1)}`);
    }

    // Update Right Claw Pincer
    const clawR = document.getElementById('svg-claw-r');
    if (clawR) {
        clawR.setAttribute('points', `${wx.toFixed(1)},${wy.toFixed(1)} ${px_r1.toFixed(1)},${py_r1.toFixed(1)} ${px_r2.toFixed(1)},${py_r2.toFixed(1)}`);
    }

    // Update Base Direction Arrow & Readout Text
    const baseArrow = document.getElementById('svg-base-arrow');
    const baseText = document.getElementById('svg-base-text');
    const normAngle = ((Math.round(s4) + 180) % 360) - 180;

    if (baseArrow) {
        baseArrow.setAttribute('transform', `rotate(${normAngle}, ${bx}, ${by})`);
    }

    if (baseText) {
        if (normAngle === 0) {
            baseText.textContent = 'BASE: 0° [CENTER]';
        } else if (normAngle < 0) {
            baseText.textContent = `BASE: ◀ ${Math.abs(normAngle)}° LEFT`;
        } else {
            baseText.textContent = `BASE: ${normAngle}° RIGHT ▶`;
        }
    }
}

function updateVisualizer(immediate = false) {
    if (immediate) {
        visualState[1] = state[1];
        visualState[2] = state[2];
        visualState[3] = state[3];
        visualState[4] = state[4];
        if (animFrameId) {
            cancelAnimationFrame(animFrameId);
            animFrameId = null;
        }
        renderVisualizer(visualState[1], visualState[2], visualState[3], visualState[4]);
        return;
    }

    if (!animFrameId) {
        animFrameId = requestAnimationFrame(stepVisualizerAnim);
    }
}

function stepVisualizerAnim() {
    let stillMoving = false;
    for (let j = 1; j <= 3; j++) {
        const diff = state[j] - visualState[j];
        if (Math.abs(diff) > 0.15) {
            visualState[j] += diff * 0.22;
            stillMoving = true;
        } else {
            visualState[j] = state[j];
        }
    }

    const bDiff = state[4] - visualState[4];
    if (Math.abs(bDiff) > 0.15) {
        visualState[4] += bDiff * 0.28;
        stillMoving = true;
    } else {
        visualState[4] = state[4];
    }

    renderVisualizer(visualState[1], visualState[2], visualState[3], visualState[4]);

    if (stillMoving) {
        animFrameId = requestAnimationFrame(stepVisualizerAnim);
    } else {
        animFrameId = null;
    }
}

// ==========================================
// SET SERVO POSITION (JOINTS 1-3)
// ==========================================

function setJoint(servoId, value, sendToServer = true) {
    const range = JOINT_RANGES[servoId] || { min: 0, max: 180 };
    value = Math.max(range.min, Math.min(range.max, parseInt(value)));
    state[servoId] = value;

    const slider = document.getElementById('slider' + servoId);
    const valBadge = document.getElementById('val' + servoId);

    if (slider) slider.value = value;
    if (valBadge) valBadge.textContent = value + '°';

    updateVisualizer();

    if (!sendToServer) return;

    clearTimeout(sendTimers[servoId]);
    sendTimers[servoId] = setTimeout(() => {
        fetch(`/api/set?s=${servoId}&v=${value}`)
            .then(res => { if (res.ok) setConnected(true); })
            .catch(e => { console.warn('Fetch error:', e); setConnected(false); });
    }, 30);
}

// ==========================================
// SLIDER CONTROL (CLAW)
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
// TWO-BUTTON HOLD-TO-MOVE (SHOULDER & ELBOW)
// ==========================================

let jointHoldTimer = null;
let jointHoldRepeat = null;

function startJointHold(jointId, dir) {
    // Immediate step
    stepServo(jointId, dir * 5);

    stopJointHold();
    // Start smooth continuous stepping after 280ms hold
    jointHoldTimer = setTimeout(() => {
        jointHoldRepeat = setInterval(() => {
            stepServo(jointId, dir * 2);
        }, 50);
    }, 280);
}

function stopJointHold() {
    if (jointHoldTimer) {
        clearTimeout(jointHoldTimer);
        jointHoldTimer = null;
    }
    if (jointHoldRepeat) {
        clearInterval(jointHoldRepeat);
        jointHoldRepeat = null;
    }
}

// ==========================================
// BASE CONTINUOUS JOG CONTROLS
// ==========================================

let currentJogSpeed = 260;
let jogKeepAliveTimer = null;
let baseJogInterval = null;
let activeJogDir = 0;

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

    // Smoothly rotate the base angle & arrow while button is held
    clearInterval(baseJogInterval);
    baseJogInterval = setInterval(() => {
        state[4] = ((state[4] + (dir > 0 ? 3 : -3) + 180) % 360) - 180;
        updateVisualizer();
    }, 45);

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
    if (activeJogDir === 0 && !jogKeepAliveTimer && !baseJogInterval) return;
    activeJogDir = 0;
    clearInterval(jogKeepAliveTimer);
    jogKeepAliveTimer = null;
    clearInterval(baseJogInterval);
    baseJogInterval = null;

    document.getElementById('btn-jog-cw')?.classList.remove('active');
    document.getElementById('btn-jog-ccw')?.classList.remove('active');
    updateBaseBadge('STOPPED', false);
    updateVisualizer();

    fetch('/api/jog?dir=STOP')
        .then(res => { if (res.ok) setConnected(true); })
        .catch(e => { console.warn(e); setConnected(false); });
}

// ==========================================
// STOP BASE SERVO
// ==========================================

function stopBaseCmd() {
    activeJogDir = 0;
    clearInterval(jogKeepAliveTimer);
    jogKeepAliveTimer = null;
    clearInterval(baseJogInterval);
    baseJogInterval = null;

    document.getElementById('btn-jog-cw')?.classList.remove('active');
    document.getElementById('btn-jog-ccw')?.classList.remove('active');
    updateBaseBadge('STOPPED', false);

    fetch('/api/stop')
        .then(res => { if (res.ok) setConnected(true); })
        .catch(e => { console.warn(e); setConnected(false); });
}

// ==========================================
// RESET ALL SERVOS
// ==========================================

function resetAllCmd() {
    // RESET_POSE matches Python robotic_arm_app.py: shoulder=90, elbow=135, claw=90, base=0
    applyPreset(90, 135, 90, 0);

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
    state[4] = s4;
    stopJog();
    updateVisualizer();
}

// ==========================================
// SERVO STATE SYNCHRONIZATION
// ==========================================

function syncStatus() {
    if (isPolling) return;
    isPolling = true;

    fetch('/api/status')
        .then(res => {
            if (!res.ok) throw new Error('Status request failed');
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

// Initial visualizer render (immediate, no delay) and status sync
updateVisualizer(true);
setConnected(false, true);
syncStatus();
setInterval(syncStatus, 3000);
