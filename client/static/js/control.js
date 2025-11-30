function showMessage(text) {
    const msg = document.getElementById('message');
    msg.textContent = text;
    msg.classList.add('show');
    setTimeout(() => msg.classList.remove('show'), 3000);
}

function showAuthModal() {
    document.getElementById('authModal').classList.add('show');
    document.getElementById('mainContent').classList.add('disabled');
    document.getElementById('passwordInput').focus();
}

function hideAuthModal() {
    document.getElementById('authModal').classList.remove('show');
    document.getElementById('mainContent').classList.remove('disabled');
    document.getElementById('passwordInput').value = '';
    document.getElementById('authError').textContent = '';
}

function retryAuth(event) {
    event.preventDefault();
    
    const password = document.getElementById('passwordInput').value;
    const submitBtn = document.getElementById('authSubmitBtn');
    const errorDiv = document.getElementById('authError');
    
    submitBtn.disabled = true;
    submitBtn.textContent = 'Authenticating...';
    errorDiv.textContent = '';
    
    fetch('/api/auth/retry', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({password: password})
    })
    .then(r => r.json().then(data => ({status: r.status, data: data})))
    .then(result => {
        if (result.status === 200 && result.data.success) {
            showMessage('✓ Authentication successful!');
            hideAuthModal();
            updateStatus();
        } else {
            errorDiv.textContent = result.data.error || 'Authentication failed';
            document.getElementById('passwordInput').value = '';
            document.getElementById('passwordInput').focus();
        }
    })
    .catch(error => {
        errorDiv.textContent = 'Connection error. Please try again.';
        console.error('Auth error:', error);
    })
    .finally(() => {
        submitBtn.disabled = false;
        submitBtn.textContent = 'Authenticate';
    });
}

function checkAuthentication() {
    fetch('/api/auth/status')
    .then(r => r.json())
    .then(data => {
        // Update username display
        if (data.username) {
            document.getElementById('usernameDisplay').textContent = data.username;
        }
        
        if (!data.authenticated) {
            showAuthModal();
        } else {
            hideAuthModal();
        }
    })
    .catch(error => {
        console.error('Auth check error:', error);
    });
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
        // Check authentication status
        if (data.authenticated === false) {
            showAuthModal();
            return;
        }
        
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
    })
    .catch(error => {
        console.error('Status update error:', error);
    });
}

// Check authentication on page load
checkAuthentication();

// Update status every 5 seconds
setInterval(updateStatus, 5000);
updateStatus();
