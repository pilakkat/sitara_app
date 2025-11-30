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
        // If we get a network error, check if it's an auth issue
        showAuthModal();
    });
}

// Check authentication status every 60 seconds (session timeout check)
setInterval(checkAuthentication, 60000);

function moveDirection(dir) {
    fetch('/api/control/move', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({direction: dir})
    })
    .then(r => {
        if (r.status === 401) {
            showAuthModal();
            throw new Error('Session expired');
        }
        return r.json();
    })
    .then(data => {
        if (data.success) {
            showMessage('Position updated: ' + dir.toUpperCase());
            updateStatus();
        } else if (data.error) {
            showMessage('Error: ' + data.error);
        }
    })
    .catch(error => {
        if (error.message !== 'Session expired') {
            console.error('Move error:', error);
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
    .then(r => {
        if (r.status === 401) {
            showAuthModal();
            throw new Error('Session expired');
        }
        return r.json();
    })
    .then(data => {
        if (data.success) updateStatus();
    })
    .catch(error => {
        if (error.message !== 'Session expired') {
            console.error('Voltage error:', error);
        }
    });
}

function updateTemperature(value) {
    document.getElementById('tempValue').textContent = value + '°C';
    fetch('/api/control/temperature', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({temperature: parseInt(value)})
    })
    .then(r => {
        if (r.status === 401) {
            showAuthModal();
            throw new Error('Session expired');
        }
        return r.json();
    })
    .then(data => {
        if (data.success) updateStatus();
    })
    .catch(error => {
        if (error.message !== 'Session expired') {
            console.error('Temperature error:', error);
        }
    });
}

function specialOp(operation) {
    fetch('/api/control/operation', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({operation: operation})
    })
    .then(r => {
        if (r.status === 401) {
            showAuthModal();
            throw new Error('Session expired');
        }
        return r.json();
    })
    .then(data => {
        if (data.success) {
            showMessage('Operation: ' + operation.toUpperCase());
            updateStatus();
        }
    })
    .catch(error => {
        if (error.message !== 'Session expired') {
            console.error('Operation error:', error);
        }
    });
}

function togglePower() {
    fetch('/api/control/power', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'}
    })
    .then(r => {
        if (r.status === 401) {
            showAuthModal();
            throw new Error('Session expired');
        }
        return r.json();
    })
    .then(data => {
        if (data.success) {
            showMessage(data.is_powered_on ? 'BOOTING...' : 'POWERED OFF');
            updateStatus();
        }
    })
    .catch(error => {
        if (error.message !== 'Session expired') {
            console.error('Power error:', error);
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
    .then(r => {
        // Check for 401 Unauthorized (session timeout)
        if (r.status === 401) {
            showAuthModal();
            throw new Error('Session expired');
        }
        return r.json();
    })
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

// Software Update Functions
function checkForUpdates() {
    const container = document.getElementById('updatesContainer');
    container.innerHTML = '<p class="text-muted">⏳ Checking for updates...</p>';
    
    fetch('/api/versions/check', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'}
    })
    .then(r => {
        if (r.status === 401) {
            showAuthModal();
            throw new Error('Session expired');
        }
        return r.json();
    })
    .then(data => {
        if (data.success) {
            displayUpdates(data.pending_updates);
            if (data.pending_updates.length > 0) {
                showMessage(`Found ${data.pending_updates.length} update(s) available`);
            } else {
                showMessage('✓ All software is up to date');
            }
        } else {
            container.innerHTML = `<p class="text-muted">❌ Error: ${data.error}</p>`;
        }
    })
    .catch(error => {
        if (error.message !== 'Session expired') {
            console.error('Update check error:', error);
            container.innerHTML = '<p class="text-muted">❌ Failed to check for updates</p>';
        }
    });
}

function displayUpdates(updates) {
    const container = document.getElementById('updatesContainer');
    
    if (updates.length === 0) {
        container.innerHTML = '<p class="text-muted">✓ All controllers are running the latest software versions</p>';
        return;
    }
    
    let html = '';
    updates.forEach(update => {
        html += `
            <div class="update-item" id="update-${update.component}">
                <div class="update-header">
                    <div class="update-component">${update.component}</div>
                    <div class="update-versions">
                        ${update.current} <span class="version-arrow">→</span> ${update.available}
                    </div>
                </div>
                <div class="update-notes">${update.notes || 'No release notes available'}</div>
                <div class="update-actions">
                    <button class="btn btn-update" onclick="installUpdate('${update.component}')">
                        📥 INSTALL UPDATE
                    </button>
                </div>
            </div>
        `;
    });
    
    container.innerHTML = html;
}

function installUpdate(component) {
    const updateItem = document.getElementById(`update-${component}`);
    const btn = updateItem.querySelector('.btn-update');
    
    btn.disabled = true;
    btn.textContent = '⏳ INSTALLING...';
    
    fetch('/api/versions/update', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({component: component})
    })
    .then(r => {
        if (r.status === 401) {
            showAuthModal();
            throw new Error('Session expired');
        }
        return r.json();
    })
    .then(data => {
        if (data.success) {
            updateItem.classList.add('update-success');
            updateItem.innerHTML = `
                <div class="update-header">
                    <div class="update-component">✓ ${data.component}</div>
                    <div class="update-versions">
                        ${data.old_version} <span class="version-arrow">→</span> ${data.new_version}
                    </div>
                </div>
                <div class="update-notes" style="color: #00ff00;">
                    ${data.message}
                </div>
            `;
            showMessage(`✓ ${component} updated successfully!`);
            
            // Refresh status to show new version
            setTimeout(updateStatus, 1000);
        } else {
            btn.disabled = false;
            btn.textContent = '📥 INSTALL UPDATE';
            showMessage(`❌ Update failed: ${data.error}`);
        }
    })
    .catch(error => {
        if (error.message !== 'Session expired') {
            console.error('Update error:', error);
            btn.disabled = false;
            btn.textContent = '📥 INSTALL UPDATE';
            showMessage('❌ Update installation failed');
        }
    });
}

// Check authentication on page load
checkAuthentication();

// Update status every 5 seconds
setInterval(updateStatus, 5000);
updateStatus();
