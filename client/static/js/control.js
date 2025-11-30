function showMessage(text) {
    const msg = document.getElementById('message');
    msg.textContent = text;
    msg.classList.add('show');
    setTimeout(() => msg.classList.remove('show'), 3000);
}

function moveDirection(dir) {
    fetch('/api/control/move', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({direction: dir})
    })
    .then(r => r.json())
    .then(data => {
        if (data.success) {
            showMessage('Position updated: ' + dir.toUpperCase());
            updateStatus();
        }
    });
}

function updateVoltage(value) {
    document.getElementById('voltageValue').textContent = value + 'V';
    fetch('/api/control/voltage', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({voltage: parseFloat(value)})
    })
    .then(r => r.json())
    .then(data => {
        if (data.success) updateStatus();
    });
}

function updateTemperature(value) {
    document.getElementById('tempValue').textContent = value + '°C';
    fetch('/api/control/temperature', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({temperature: parseInt(value)})
    })
    .then(r => r.json())
    .then(data => {
        if (data.success) updateStatus();
    });
}

function specialOp(operation) {
    fetch('/api/control/operation', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({operation: operation})
    })
    .then(r => r.json())
    .then(data => {
        if (data.success) {
            showMessage('Operation: ' + operation.toUpperCase());
            updateStatus();
        }
    });
}

function togglePower() {
    fetch('/api/control/power', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'}
    })
    .then(r => r.json())
    .then(data => {
        if (data.success) {
            showMessage(data.is_powered_on ? 'BOOTING...' : 'POWERED OFF');
            updateStatus();
        }
    });
}

function setButtonsEnabled(enabled) {
    // Position buttons
    ['upBtn', 'downBtn', 'leftBtn', 'rightBtn'].forEach(id => {
        document.getElementById(id).disabled = !enabled;
    });
    // Operation buttons
    ['standbyBtn', 'movingBtn', 'scanningBtn'].forEach(id => {
        document.getElementById(id).disabled = !enabled;
    });
}

function updateStatus() {
    fetch('/api/control/status')
    .then(r => r.json())
    .then(data => {
        document.getElementById('robotId').textContent = data.robot_id;
        document.getElementById('positionValue').textContent = 
            data.position.x.toFixed(1) + ', ' + data.position.y.toFixed(1);
        document.getElementById('orientationValue').textContent = 
            data.position.orientation.toFixed(1) + '°';
        document.getElementById('batteryValue').textContent = 
            data.battery_voltage.toFixed(2) + 'V';
        document.getElementById('temperatureValue').textContent = 
            data.temperature.toFixed(1) + '°C';
        document.getElementById('statusValue').textContent = data.status;
        document.getElementById('cyclesValue').textContent = data.cycle_count;
        
        // Update sliders
        document.getElementById('voltageSlider').value = data.battery_voltage;
        document.getElementById('tempSlider').value = data.temperature;
        
        // Enable/disable buttons based on power state
        setButtonsEnabled(data.is_powered_on);
    });
}

// Update status every 5 seconds
setInterval(updateStatus, 5000);
updateStatus();
