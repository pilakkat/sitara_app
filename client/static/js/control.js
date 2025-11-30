// Toast notification with auto-hide
let toastTimeout;

function hideToast() {
    const msg = document.getElementById('message');
    if (toastTimeout) {
        clearTimeout(toastTimeout);
    }
    msg.classList.add('hiding');
    setTimeout(() => {
        msg.classList.remove('show', 'hiding', 'error', 'warning', 'success');
        msg.innerHTML = '';
    }, 1000);
}

function showMessage(text, type = 'success') {
    const msg = document.getElementById('message');
    
    // Clear any existing timeout
    if (toastTimeout) {
        clearTimeout(toastTimeout);
    }
    
    // Remove hiding class if present
    msg.classList.remove('hiding');
    
    // Set content with close button
    msg.innerHTML = `
        <span>${text}</span>
        <button class="message-close" onclick="hideToast()" aria-label="Close">×</button>
    `;
    
    // Remove any existing type classes
    msg.classList.remove('error', 'warning', 'success');
    // Add the new type class
    msg.classList.add('show', type);
    
    // Auto-hide after 4 seconds
    toastTimeout = setTimeout(() => {
        hideToast();
    }, 4000);
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

function showRebootEffect() {
    // Add visual reboot effect to status display
    const statusElements = document.querySelectorAll('.value');
    statusElements.forEach(el => {
        el.style.transition = 'opacity 0.3s';
        el.style.opacity = '0.3';
    });
    
    setTimeout(() => {
        statusElements.forEach(el => {
            el.style.opacity = '1';
        });
    }, 1500);
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
        if (r.status === 400) {
            // Collision or invalid position
            return r.json().then(data => {
                showMessage(data.message || 'Cannot move - obstacle in the way', 'error');
                throw new Error('Movement blocked');
            });
        }
        return r.json();
    })
    .then(data => {
        if (data.success) {
            showMessage('Position updated: ' + dir.toUpperCase());
            updateStatus();
        } else if (data.error) {
            showMessage('Error: ' + data.error, 'error');
        }
    })
    .catch(error => {
        if (error.message !== 'Session expired' && error.message !== 'Movement blocked') {
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
    btn.innerHTML = '⏳ CHECKING STATE...';
    
    // First, check robot state
    fetch('/api/control/status')
    .then(r => r.json())
    .then(statusData => {
        const status = statusData.status.replace(' | BAT LOW', ''); // Remove battery warning suffix
        const isPoweredOn = statusData.is_powered_on;
        
        // Check if robot is powered on
        if (!isPoweredOn) {
            btn.disabled = false;
            btn.innerHTML = '📥 INSTALL UPDATE';
            showMessage('❌ Cannot update: Robot is powered OFF. Please power on first.', 'error');
            return;
        }
        
        // Check if robot is in safe state for update
        if (status === 'MOVING' || status === 'SCANNING') {
            btn.innerHTML = '⏸️ STOPPING OPERATIONS...';
            
            // Stop the robot first
            fetch('/api/control/operation', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({operation: 'standby'})
            })
            .then(() => {
                // Wait a moment for robot to stop
                setTimeout(() => {
                    startUpdateProcess(component, updateItem, btn);
                }, 1000);
            })
            .catch(error => {
                btn.disabled = false;
                btn.innerHTML = '📥 INSTALL UPDATE';
                showMessage('❌ Failed to stop robot operations', 'error');
            });
        } else if (status === 'STANDBY' || status === 'CHARGING') {
            // Safe to proceed
            startUpdateProcess(component, updateItem, btn);
        } else {
            btn.disabled = false;
            btn.innerHTML = '📥 INSTALL UPDATE';
            showMessage(`❌ Cannot update: Robot is in ${status} state. Must be STANDBY or CHARGING.`, 'error');
        }
    })
    .catch(error => {
        btn.disabled = false;
        btn.innerHTML = '📥 INSTALL UPDATE';
        showMessage('❌ Failed to check robot state', 'error');
    });
}

function startUpdateProcess(component, updateItem, btn) {
    // Stage 1: Downloading
    let downloadProgress = 0;
    btn.innerHTML = '📥 DOWNLOADING... 0%';
    
    const downloadInterval = setInterval(() => {
        downloadProgress += Math.random() * 15 + 10;
        if (downloadProgress >= 100) {
            downloadProgress = 100;
        }
        btn.innerHTML = `📥 DOWNLOADING... ${Math.floor(downloadProgress)}%`;
        
        if (downloadProgress >= 100) {
            clearInterval(downloadInterval);
            btn.innerHTML = '📥 DOWNLOAD COMPLETE';
            
            // Stage 2: Flashing
            setTimeout(() => {
                let flashProgress = 0;
                const flashInterval = setInterval(() => {
                    flashProgress += Math.random() * 12 + 8;
                    if (flashProgress >= 100) {
                        flashProgress = 100;
                    }
                    btn.innerHTML = `⚡ FLASHING FIRMWARE... ${Math.floor(flashProgress)}%`;
                    
                    if (flashProgress >= 100) {
                        clearInterval(flashInterval);
                        btn.innerHTML = '⚡ FLASH COMPLETE';
                        
                        // Stage 3: Rebooting
                        setTimeout(() => {
                            btn.innerHTML = '🔄 REBOOTING CONTROLLER...';
                            
                            // Call actual update API
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
                                    setTimeout(() => {
                                        updateItem.classList.add('update-success');
                                        updateItem.innerHTML = `
                                            <div class="update-header">
                                                <div class="update-component">✓ ${data.component} UPDATED</div>
                                                <div class="update-versions">
                                                    ${data.old_version} <span class="version-arrow">→</span> ${data.new_version}
                                                </div>
                                            </div>
                                            <div class="update-notes" style="color: #00ff00;">
                                                ✓ ${data.message}<br>
                                                <small style="color: #4caf50;">Controller rebooted successfully</small>
                                            </div>
                                        `;
                                        showMessage(`✓ ${component} updated to ${data.new_version}!`, 'success');
                                        setTimeout(updateStatus, 1000);
                                        showRebootEffect();
                                    }, 2000);
                                } else {
                                    btn.disabled = false;
                                    btn.innerHTML = '📥 INSTALL UPDATE';
                                    showMessage(`❌ Update failed: ${data.error}`, 'error');
                                }
                            })
                            .catch(error => {
                                if (error.message !== 'Session expired') {
                                    console.error('Update error:', error);
                                    btn.disabled = false;
                                    btn.innerHTML = '📥 INSTALL UPDATE';
                                    showMessage('❌ Update installation failed', 'error');
                                }
                            });
                        }, 500);
                    }
                }, 100);
            }, 500);
        }
    }, 150);
}

// Check authentication on page load
checkAuthentication();

// Update status every 5 seconds
setInterval(updateStatus, 5000);
updateStatus();
