/* * SITARA DYNAMICS - Client Side Logic
 * File: static/js/main.js
 */

// Global variables for path visualization
let pathCanvas, pathCtx;
let pathHistory = [];
let lastLogCount = 0;
let lastLogSignature = '';  // Track content signature for change detection
let isLiveMode = true;
let pollingIntervals = [];

// Current robot selection
let currentRobotId = null;
let availableRobots = [];
let robotDateRange = {
    earliest: null,
    latest: null
};

// Chart.js instances
let batteryChart = null;
let tempChart = null;

// Timeline scrubber state
let timelineData = [];
let currentTimelineIndex = 0;
let isTimelineDragging = false;
let timelineAutoUpdate = true;

/**
 * Get the current timezone offset in minutes
 * Returns negative for west of UTC (e.g., -300 for EST), positive for east
 */
function getTimezoneOffset() {
    return new Date().getTimezoneOffset();
}

/**
 * Obstacle array - will be loaded from database
 * These represent physical objects the robot must avoid
 */
let obstacles = [];

/**
 * Load obstacles for the current robot from database
 */
function fetchObstacles() {
    const params = currentRobotId ? `?robot_id=${currentRobotId}` : '';
    $.getJSON('/api/obstacles' + params, function(data) {
        obstacles = data;
        console.log(`Loaded ${obstacles.length} obstacles for robot`);
        renderObstacles();
    }).fail(function(xhr, status, error) {
        console.warn("Failed to load obstacles:", error);
        obstacles = [];
    });
}

/**
 * Render obstacles on the map
 */
function renderObstacles() {
    const container = $('#obstaclesContainer');
    container.empty(); // Clear existing obstacles
    
    obstacles.forEach(function(obstacle) {
        let element;
        
        if (obstacle.type === 'circle') {
            // Create circular obstacle
            const diameter = obstacle.radius * 2;
            element = $('<div>')
                .addClass('obstacle-circle')
                .css({
                    top: (obstacle.y - obstacle.radius) + '%',
                    left: (obstacle.x - obstacle.radius) + '%',
                    width: diameter + '%',
                    height: diameter + '%',
                    background: obstacle.color || 'rgba(100,100,100,0.4)'
                })
                .attr('title', obstacle.name)
                .attr('data-obstacle-id', obstacle.id);
        } else if (obstacle.type === 'rectangle') {
            // Create rectangular obstacle
            element = $('<div>')
                .addClass('obstacle')
                .css({
                    top: obstacle.y + '%',
                    left: obstacle.x + '%',
                    width: obstacle.width + '%',
                    height: obstacle.height + '%',
                    background: obstacle.color || 'rgba(100,100,100,0.4)'
                })
                .attr('title', obstacle.name)
                .attr('data-obstacle-id', obstacle.id);
        }
        
        if (element) {
            container.append(element);
        }
    });
}

/**
 * Check if a position collides with any obstacle
 * @param {number} x - X position (0-100)
 * @param {number} y - Y position (0-100)
 * @param {number} buffer - Safety buffer around obstacles (default 2%)
 * @returns {boolean} - True if collision detected
 */
function checkCollision(x, y, buffer = 2) {
    for (const obstacle of obstacles) {
        if (obstacle.type === 'rectangle') {
            if (x >= (obstacle.x - buffer) && 
                x <= (obstacle.x + obstacle.width + buffer) &&
                y >= (obstacle.y - buffer) && 
                y <= (obstacle.y + obstacle.height + buffer)) {
                return true;
            }
        } else if (obstacle.type === 'circle') {
            // Check distance from circle center
            const dx = x - obstacle.x;
            const dy = y - obstacle.y;
            const distance = Math.sqrt(dx * dx + dy * dy);
            if (distance <= obstacle.radius + buffer) {
                return true;
            }
        }
    }
    return false;
}

/**
 * Find nearest valid position if collision detected
 * @param {number} x - Target X position
 * @param {number} y - Target Y position
 * @returns {object} - Nearest valid {x, y} position
 */
function findNearestValidPosition(x, y) {
    if (!checkCollision(x, y)) {
        return { x, y };
    }
    
    // Try positions in expanding radius
    for (let radius = 3; radius <= 15; radius += 2) {
        for (let angle = 0; angle < 360; angle += 45) {
            const rad = angle * Math.PI / 180;
            const testX = x + radius * Math.cos(rad);
            const testY = y + radius * Math.sin(rad);
            
            if (testX >= 5 && testX <= 95 && testY >= 5 && testY <= 95) {
                if (!checkCollision(testX, testY)) {
                    return { x: testX, y: testY };
                }
            }
        }
    }
    
    // Fallback to center
    return { x: 50, y: 50 };
}

// Helper function to get status icon based on robot status
function getStatusIcon(status) {
    if (!status) return '⚫';
    
    const statusUpper = status.toUpperCase();
    
    if (statusUpper === 'OFFLINE' || statusUpper === 'UNKNOWN') {
        return '⚫'; // Black circle for offline
    } else if (statusUpper === 'FAULT' || statusUpper.includes('ERROR') || statusUpper.includes('WARN')) {
        return '🔴'; // Red circle for fault/error
    } else if (statusUpper === 'CHARGING') {
        return '🟡'; // Yellow circle for charging
    } else if (statusUpper === 'BOOTING') {
        return '🟠'; // Orange circle for booting
    } else if (statusUpper === 'STANDBY' || statusUpper === 'IDLE') {
        return '🟢'; // Green circle for standby/idle
    } else if (statusUpper === 'MOVING' || statusUpper === 'SCANNING') {
        return '🔵'; // Blue circle for active operations
    } else {
        return '🟢'; // Default green for operational states
    }
}

// Update robot dropdown status icons
function updateRobotDropdownStatus(robotId, status) {
    const selector = $('#robotSelector');
    const option = selector.find(`option[value="${robotId}"]`);
    
    if (option.length > 0) {
        const serialNumber = option.text().substring(2).trim(); // Remove old icon
        const statusIcon = getStatusIcon(status);
        option.text(`${statusIcon} ${serialNumber}`);
        option.attr('data-status', status);
    }
}

// Update all robot statuses in dropdown
function updateAllRobotStatuses() {
    // Only update if we're in live mode
    if (!isLiveMode) return;
    
    // Fetch status for all available robots
    availableRobots.forEach(robot => {
        $.getJSON('/api/telemetry?robot_id=' + robot.id, function(data) {
            if (data.status) {
                updateRobotDropdownStatus(robot.id, data.status);
            }
        }).fail(function() {
            // If telemetry fetch fails, mark as offline
            updateRobotDropdownStatus(robot.id, 'OFFLINE');
        });
    });
}

// Helper function to get robot marker CSS class based on status
function getRobotMarkerClass(status) {
    if (!status) return 'status-offline';
    
    const statusUpper = status.toUpperCase();
    
    if (statusUpper === 'OFFLINE' || statusUpper === 'UNKNOWN') {
        return 'status-offline';
    } else if (statusUpper === 'FAULT' || statusUpper.includes('ERROR') || statusUpper.includes('WARN')) {
        return 'status-fault';
    } else if (statusUpper === 'CHARGING') {
        return 'status-charging';
    } else if (statusUpper === 'BOOTING') {
        return 'status-booting';
    } else if (statusUpper === 'STANDBY' || statusUpper === 'IDLE') {
        return 'status-standby';
    } else if (statusUpper === 'MOVING') {
        return 'status-moving';
    } else if (statusUpper === 'SCANNING') {
        return 'status-scanning';
    } else if (statusUpper === 'OPERATIONAL' || statusUpper === 'NOMINAL') {
        return 'status-operational';
    } else {
        return 'status-standby'; // Default
    }
}

// Load available robots
function loadRobots() {
    $.get('/api/robots')
        .done(function(robots) {
            console.log("Available robots:", robots);
            availableRobots = robots;
            
            const selector = $('#robotSelector');
            selector.empty();
            
            if (robots.length === 0) {
                selector.append('<option value="">No robots available</option>');
                return;
            }
            
            robots.forEach(robot => {
                const statusBadge = getStatusIcon(robot.status);
                selector.append(`<option value="${robot.id}" data-status="${robot.status}">${statusBadge} ${robot.serial_number}</option>`);
            });
            
            // Select first robot by default
            currentRobotId = robots[0].id;
            selector.val(currentRobotId);
            
            // Load obstacles for the default robot
            fetchObstacles();
        })
        .fail(function(error) {
            console.error("Failed to load robots:", error);
            $('#robotSelector').html('<option value="">Error loading robots</option>');
        });
}

// Switch to different robot
window.switchRobot = function() {
    const selectedId = $('#robotSelector').val();
    if (selectedId && selectedId !== currentRobotId) {
        console.log("Switching to robot:", selectedId);
        currentRobotId = parseInt(selectedId);
        
        // Clear path history to force full reload for new robot
        pathHistory = [];
        
        // Switch to live mode by default
        isLiveMode = true;
        timelineAutoUpdate = true;
        
        // Clear date selector and update UI
        $('#dateSelector').val('');
        $('#dataMode').text('MODE: LIVE');
        
        // Update button states
        $('#btnLiveMode').addClass('active');
        $('#btnLoadHistorical').removeClass('active');
        
        // Fetch obstacles for this robot
        fetchObstacles();
        
        // Fetch date range for this robot
        fetchRobotDateRange();
        
        // Update navigation button states
        updateDateNavigationButtons();
        
        // Stop any existing polling and start fresh
        stopPolling();
        startPolling();
    }
};

// Fetch and update date range for current robot
function fetchRobotDateRange() {
    const robotId = currentRobotId || '';
    const params = robotId ? `?robot_id=${robotId}` : '';
    
    $.getJSON('/api/robot/date_range' + params, function(data) {
        console.log("Robot date range:", data);
        
        robotDateRange.earliest = data.earliest_date;
        robotDateRange.latest = data.latest_date;
        
        // Update date picker constraints
        const today = new Date().toISOString().split('T')[0];
        // In live mode, maxDate should always be today (to allow navigating to current day)
        // In historical mode, use the database's latest date
        const maxDate = isLiveMode ? today : (data.latest_date || today);
        const minDate = data.earliest_date || today;
        
        $('#dateSelector').attr('max', maxDate);
        $('#dateSelector').attr('min', minDate);
        
        // Update button states
        updateDateNavigationButtons();
        
        console.log(`Date range set: ${minDate} to ${maxDate} (Live mode: ${isLiveMode})`);
    }).fail(function(error) {
        console.error("Failed to fetch date range:", error);
        // Fallback to 30 days
        const today = new Date();
        const minDate = new Date();
        minDate.setDate(minDate.getDate() - 30);
        
        $('#dateSelector').attr('max', today.toISOString().split('T')[0]);
        $('#dateSelector').attr('min', minDate.toISOString().split('T')[0]);
        
        updateDateNavigationButtons();
    });
}

// Ensure functions are available globally for button onclick events
window.sendCommand = function(cmd) {
    console.log("Attempting to send command:", cmd);
    // Visual feedback
    updateLog(`> SENDING COMMAND: ${cmd}...`);

    $.ajax({
        url: '/api/robot/command',
        type: 'POST',
        contentType: 'application/json',
        data: JSON.stringify({ command: cmd, robot_id: currentRobotId || 1 }),
        success: function(response) {
            updateLog(`> ACK: ${response.message}`);
        },
        error: function(err) {
            console.error("Command Error:", err);
            updateLog(`> ERROR: Command Failed. Is Robot Online?`);
        }
    });
};

// Load historical data for selected date
window.loadHistoricalData = function() {
    const selectedDate = $('#dateSelector').val();
    
    if (!selectedDate) {
        alert('Please select a date first');
        return;
    }
    
    console.log("Loading historical data for:", selectedDate);
    isLiveMode = false;
    timelineAutoUpdate = false; // Disable auto-update for historical mode
    
    // Stop live polling
    stopPolling();
    
    // Update UI and button states
    $('#dataMode').text('MODE: HISTORICAL - ' + selectedDate);
    $('#btnLoadHistorical').addClass('active');
    $('#btnLiveMode').removeClass('active');
    
    // Update navigation button states
    updateDateNavigationButtons();
    
    // Load historical data
    fetchHistoricalTelemetry(selectedDate);
    fetchHistoricalPath(selectedDate);
    fetchHistoricalLogs(selectedDate);
    fetchHealthHistory(selectedDate);
};

// Return to live mode
window.loadLiveData = function() {
    console.log("Returning to live mode");
    isLiveMode = true;
    timelineAutoUpdate = true; // Enable auto-update for live mode
    
    // Clear date selector
    $('#dateSelector').val('');
    $('#dataMode').text('MODE: LIVE');
    
    // Update button states
    $('#btnLiveMode').addClass('active');
    $('#btnLoadHistorical').removeClass('active');
    
    // Refresh date range to ensure maxDate is set to today
    fetchRobotDateRange();
    
    // Update navigation button states
    updateDateNavigationButtons();
    
    // Clear existing path history to force full reload
    pathHistory = [];
    
    // Restart live polling
    startPolling();
};

// Navigate date by offset (days)
window.navigateDate = function(offset) {
    const dateInput = $('#dateSelector');
    let currentDate = dateInput.val();
    
    // If no date selected, use today
    if (!currentDate) {
        currentDate = new Date().toISOString().split('T')[0];
    }
    
    // Parse and add offset
    const date = new Date(currentDate);
    date.setDate(date.getDate() + offset);
    
    // Get min and max dates from the input
    const minDate = dateInput.attr('min');
    const maxDate = dateInput.attr('max');
    const newDateStr = date.toISOString().split('T')[0];
    
    // Check bounds - disable button instead of alert
    if (minDate && newDateStr < minDate) {
        return;
    }
    if (maxDate && newDateStr > maxDate) {
        return;
    }
    
    // Update date selector and load data
    dateInput.val(newDateStr);
    loadHistoricalData();
    
    // Update button states
    updateDateNavigationButtons();
};

// Update date navigation button states
function updateDateNavigationButtons() {
    const dateInput = $('#dateSelector');
    const currentDate = dateInput.val();
    
    if (!currentDate) {
        // No date selected, disable both
        $('#btnPrevDay').prop('disabled', false);
        $('#btnNextDay').prop('disabled', false);
        return;
    }
    
    const minDate = dateInput.attr('min');
    const maxDate = dateInput.attr('max');
    
    // Check if previous day would be out of bounds
    const prevDate = new Date(currentDate);
    prevDate.setDate(prevDate.getDate() - 1);
    const prevDateStr = prevDate.toISOString().split('T')[0];
    $('#btnPrevDay').prop('disabled', minDate && prevDateStr < minDate);
    
    // Check if next day would be out of bounds
    const nextDate = new Date(currentDate);
    nextDate.setDate(nextDate.getDate() + 1);
    const nextDateStr = nextDate.toISOString().split('T')[0];
    $('#btnNextDay').prop('disabled', maxDate && nextDateStr > maxDate);
}

$(document).ready(function() {
    console.log("SITARA SYSTEM: Core JS loaded.");

    // --- DASHBOARD SPECIFIC LOGIC ---
    // Only run polling if we are actually on the dashboard page
    if ($('#dashboard-view').length > 0) {
        console.log("Dashboard View Detected. Initializing Telemetry Stream...");
        
        // Load available robots first
        loadRobots();
        
        // Initialize canvas for path visualization
        initPathCanvas();
        
        // Initialize timeline scrubber
        initTimeline();
        
        // Initialize health charts
        initHealthCharts();
        
        // Set date picker to today initially
        const today = new Date().toISOString().split('T')[0];
        $('#dateSelector').val(today);
        $('#dateSelector').attr('max', today);
        
        // Set default min date (30 days ago - will be updated when robot is selected)
        const defaultMinDate = new Date();
        defaultMinDate.setDate(defaultMinDate.getDate() - 30);
        $('#dateSelector').attr('min', defaultMinDate.toISOString().split('T')[0]);
        
        // Fetch actual date range for selected robot
        fetchRobotDateRange();
        
        // Initialize button states
        updateDateNavigationButtons();
        
        // Update button states when date changes
        $('#dateSelector').on('change', updateDateNavigationButtons);
        
        // Start in live mode
        startPolling();
    } else {
        console.log("Not on dashboard view. Telemetry standby.");
    }
});

/**
 * Start live polling intervals
 */
function startPolling() {
    // Clear any existing intervals
    stopPolling();
    
    // Run once immediately
    fetchTelemetry();
    fetchPathHistory();
    fetchTelemetryLogs();
    fetchHealthHistory();
    updateAllRobotStatuses();
    
    // Then start the polling loops
    pollingIntervals.push(setInterval(fetchTelemetry, 2000));        // Update every 2 seconds
    pollingIntervals.push(setInterval(fetchPathHistory, 3000));      // Update path every 3 seconds
    pollingIntervals.push(setInterval(fetchTelemetryLogs, 5000));    // Update logs every 5 seconds
    pollingIntervals.push(setInterval(fetchHealthHistory, 10000));   // Update charts every 10 seconds
    pollingIntervals.push(setInterval(updateAllRobotStatuses, 5000)); // Update all robot statuses every 5 seconds
    
    // Refresh date range every minute to catch day transitions in live mode
    pollingIntervals.push(setInterval(function() {
        if (isLiveMode) {
            fetchRobotDateRange();
        }
    }, 60000)); // Every 60 seconds
}

/**
 * Stop all polling intervals
 */
function stopPolling() {
    pollingIntervals.forEach(interval => clearInterval(interval));
    pollingIntervals = [];
}

/**
 * Initialize the canvas for drawing the robot's path
 */
function initPathCanvas() {
    pathCanvas = document.getElementById('pathCanvas');
    if (!pathCanvas) return;
    
    pathCtx = pathCanvas.getContext('2d');
    
    // Set canvas size to match container
    const container = document.getElementById('mapZone');
    if (container) {
        pathCanvas.width = container.offsetWidth;
        pathCanvas.height = container.offsetHeight;
    }
}

/**
 * Fetches robot telemetry data from the Python backend
 */
function fetchTelemetry() {
    const params = currentRobotId ? `?robot_id=${currentRobotId}` : '';
    $.getJSON('/api/telemetry' + params, function(data) {
        updateTelemetryDisplay(data);
        
        // Update robot dropdown status icon if we have robot_id and status
        if (data.robot_id && data.status) {
            updateRobotDropdownStatus(data.robot_id, data.status);
        }
    }).fail(function(xhr, status, error) {
        console.warn("Telemetry endpoint unreachable:", error);
        $('#statusVal').text("CONNECTION LOST")
            .removeClass('border-info border-warning text-info text-warning')
            .addClass('border-danger text-danger');
    });
}

/**
 * Fetch historical telemetry for specific date
 */
function fetchHistoricalTelemetry(date) {
    const tzOffset = getTimezoneOffset();
    const params = `?date=${date}&tz_offset=${tzOffset}${currentRobotId ? '&robot_id=' + currentRobotId : ''}`;
    $.getJSON('/api/telemetry_at_time' + params, function(data) {
        updateTelemetryDisplay(data);
    }).fail(function(xhr, status, error) {
        console.warn("No telemetry data for this date:", error);
        $('#statusVal').text("NO DATA FOR DATE")
            .removeClass('border-info border-warning text-info text-warning')
            .addClass('border-danger text-danger');
    });
}

/**
 * Update telemetry display with data
 */
function updateTelemetryDisplay(data) {
    // 1. Update Numeric Values
    $('#batteryVal').text(data.battery.toFixed(2) + ' V');
    $('#tempVal').text(data.cpu_temp + ' °C');
    $('#cycleVal').text(data.cycles.toLocaleString());
    
    // 2. Update timestamp
    if (data.timestamp) {
        const updateTime = new Date(data.timestamp);
        $('#lastUpdate').text(updateTime.toLocaleTimeString());
    }
    
    // 3. Update Status Badge
    let statusBadge = $('#statusVal');
    statusBadge.text(data.status);
    
    if(data.status === "NOMINAL" || data.status === "OPERATIONAL") {
        statusBadge.removeClass('border-warning border-danger text-warning text-danger')
                  .addClass('border-info text-info');
    } else if(data.status.includes("WARN")) {
        statusBadge.removeClass('border-info border-danger text-info text-danger')
                  .addClass('border-warning text-warning');
    } else {
        statusBadge.removeClass('border-info border-warning text-info text-warning')
                  .addClass('border-danger text-danger');
    }

    // 4. Update Load Bar
    $('#loadVal').text(data.load);
    $('#loadBar').css('width', data.load + '%');
    
    if(data.load > 80) {
        $('#loadBar').removeClass('bg-info').addClass('bg-danger');
    } else {
        $('#loadBar').removeClass('bg-danger').addClass('bg-info');
    }

    // 5. Update Software Versions (if available)
    if (data.versions) {
        $('#versionRCPCU').text(data.versions.RCPCU || '--');
        $('#versionRCSPM').text(data.versions.RCSPM || '--');
        $('#versionRCMMC').text(data.versions.RCMMC || '--');
        $('#versionRCPMU').text(data.versions.RCPMU || '--');
    }

    // 6. Move Robot on Map (with collision detection)
    const robotMarker = $('#robotMarker');
    
    // Check if new position collides with obstacles
    let finalX = data.pos_x;
    let finalY = data.pos_y;
    
    if (checkCollision(finalX, finalY)) {
        console.warn(`Collision detected at (${finalX}, ${finalY}), finding nearest valid position`);
        const validPos = findNearestValidPosition(finalX, finalY);
        finalX = validPos.x;
        finalY = validPos.y;
    }
    
    robotMarker.css({
        'top': finalY + '%',
        'left': finalX + '%'
    });
    
    // Update robot marker color based on status
    const markerClass = getRobotMarkerClass(data.status);
    robotMarker.removeClass('status-offline status-fault status-charging status-booting status-standby status-moving status-scanning status-operational');
    robotMarker.addClass(markerClass);
    
    // Add rotation if orientation is available
    // Note: orientation 0° = pointing right, 90° = pointing down, etc.
    if (data.orientation !== undefined) {
        // Combine translate (for centering) with rotate (for orientation)
        // Subtract 90 to make 0° point upward instead of rightward
        const rotation = data.orientation - 90;
        robotMarker.css('transform', `translate(-50%, -50%)`);// rotate(${rotation}deg)`);
    } else {
        // Keep centering even without orientation
        robotMarker.css('transform', 'translate(-50%, -50%)');
    }
}

/**
 * Fetches and draws the robot's path history
 * In live mode, loads incrementally after initial full load
 */
function fetchPathHistory() {
    let params = currentRobotId ? `?robot_id=${currentRobotId}` : '';
    
    // If we have path history, only fetch new points after the last timestamp
    if (isLiveMode && pathHistory && pathHistory.length > 0) {
        const lastTimestamp = pathHistory[pathHistory.length - 1].timestamp;
        params += (params ? '&' : '?') + 'since=' + encodeURIComponent(lastTimestamp);
        console.log("Fetching incremental path since:", lastTimestamp);
    } else {
        console.log("Fetching full path history");
    }
    
    $.getJSON('/api/path_history' + params, function(data) {
        if (!pathCtx) return;
        
        // Handle data based on mode and existing history
        if (isLiveMode && pathHistory && pathHistory.length > 0 && data && data.length > 0) {
            // Check for large position jump (indicates robot restart or teleport)
            const lastPos = pathHistory[pathHistory.length - 1];
            const newPos = data[0];
            const distanceSquared = Math.pow(newPos.x - lastPos.x, 2) + Math.pow(newPos.y - lastPos.y, 2);
            
            // If position jumped more than 20 units, robot likely restarted - reload full path
            if (distanceSquared > 400) {
                console.log("Large position jump detected, reloading full path");
                pathHistory = [];
                // Fetch full path by removing 'since' parameter
                const fullParams = currentRobotId ? `?robot_id=${currentRobotId}` : '';
                $.getJSON('/api/path_history' + fullParams, function(fullData) {
                    if (fullData && fullData.length > 0) {
                        pathHistory = fullData;
                        drawPath();
                        updateTimelineData(pathHistory);
                    }
                });
                return;
            }
            
            // Append new points to existing path (incremental)
            console.log("Appending", data.length, "new path points");
            pathHistory = pathHistory.concat(data);
        } else if (data && data.length > 0) {
            // Replace entire path (initial load or historical mode)
            console.log("Loading", data.length, "path points");
            pathHistory = data;
        }
        // If data is empty and we have existing history, keep it (no new points yet)
        
        drawPath();
        
        // Update timeline with path data
        updateTimelineData(pathHistory);
    }).fail(function() {
        console.warn("Path history endpoint unreachable.");
    });
}

/**
 * Fetch historical path for specific date
 */
function fetchHistoricalPath(date) {
    const tzOffset = getTimezoneOffset();
    const params = `?date=${date}&tz_offset=${tzOffset}${currentRobotId ? '&robot_id=' + currentRobotId : ''}`;
    $.getJSON('/api/path_history' + params, function(data) {
        if (!pathCtx || !data || data.length === 0) {
            console.warn("No path data for this date");
            pathHistory = [];
            clearCanvas();
            updateTimelineData([]); // Clear timeline
            return;
        }
        
        pathHistory = data;
        drawPath();
        
        // Update timeline with historical data
        updateTimelineData(data);
    }).fail(function() {
        console.warn("Path history endpoint unreachable.");
    });
}

/**
 * Clear the canvas
 */
function clearCanvas() {
    if (pathCtx) {
        pathCtx.clearRect(0, 0, pathCanvas.width, pathCanvas.height);
    }
}

/**
 * Draws the path trail on the canvas
 */
function drawPath() {
    if (!pathCtx || pathHistory.length === 0) return;
    
    // Clear canvas
    pathCtx.clearRect(0, 0, pathCanvas.width, pathCanvas.height);
    
    // Draw path as connected line
    pathCtx.beginPath();
    pathCtx.strokeStyle = 'rgba(0, 255, 255, 0.5)';  // Cyan trail
    pathCtx.lineWidth = 2;
    
    pathHistory.forEach((point, index) => {
        const x = (point.x / 100) * pathCanvas.width;
        const y = (point.y / 100) * pathCanvas.height;
        
        if (index === 0) {
            pathCtx.moveTo(x, y);
        } else {
            pathCtx.lineTo(x, y);
        }
        
        // Draw a small dot at each point
        pathCtx.fillStyle = 'rgba(0, 255, 255, 0.3)';
        pathCtx.fillRect(x - 1, y - 1, 2, 2);
    });
    
    pathCtx.stroke();
}

/**
 * Fetches telemetry logs and displays them in the log terminal
 */
function fetchTelemetryLogs() {
    const params = currentRobotId ? `?robot_id=${currentRobotId}` : '';
    $.getJSON('/api/telemetry_history' + params, function(data) {
        displayLogs(data);
    }).fail(function() {
        console.warn("Telemetry history endpoint unreachable.");
    });
}

/**
 * Fetch historical logs for specific date
 */
function fetchHistoricalLogs(date) {
    const tzOffset = getTimezoneOffset();
    const params = `date=${date}&tz_offset=${tzOffset}${currentRobotId ? '&robot_id=' + currentRobotId : ''}`;
    $.getJSON('/api/telemetry_history?' + params, function(data) {
        displayLogs(data);
    }).fail(function() {
        console.warn("No logs for this date.");
        $('#sysLogs').html('<div class="log-entry text-warning">No telemetry logs found for this date.</div>');
    });
}

/**
 * Display logs in terminal
 */
function displayLogs(data) {
    if (!data || data.length === 0) {
        // If no data, show initial message only if terminal is empty
        if ($('#sysLogs').children().length === 0) {
            $('#sysLogs').html('<div class="log-entry text-warning">[S4-CLOUD] No telemetry data available.</div>');
        }
        return;
    }
    
    // Create a signature of the log content (excluding timestamps)
    // This signature includes: status, battery, temp, load for each log
    const currentSignature = data.map(log => 
        `${log.status}|${log.battery.toFixed(2)}|${log.temp}|${log.load}`
    ).join(';;');
    
    // Only update if content has actually changed
    if (currentSignature === lastLogSignature) {
        return; // No change in actual data
    }
    
    // Update the signature
    lastLogSignature = currentSignature;
    lastLogCount = data.length;
    
    let logs = $('#sysLogs');
    logs.empty();  // Clear existing logs
    
    // Display logs in reverse order (newest first)
    data.slice().reverse().forEach(log => {
        const timestamp = new Date(log.timestamp).toLocaleTimeString();
        const statusColor = getStatusColor(log.status);
        
        const logEntry = `<div class="log-entry">
            <span class="text-muted">[${timestamp}]</span>
            <span class="${statusColor}">${log.status}</span> | 
            BAT: ${log.battery.toFixed(2)}V | 
            TEMP: ${log.temp}°C | 
            LOAD: ${log.load}%
        </div>`;
        
        logs.append(logEntry);
    });
    
    // Limit to 30 visible entries
    if (logs.children().length > 30) {
        logs.children().slice(30).remove();
    }
}

/**
 * Returns appropriate CSS class for status color
 */
function getStatusColor(status) {
    if (status === "NOMINAL" || status === "OPERATIONAL") {
        return "text-info";
    } else if (status.includes("WARN")) {
        return "text-warning";
    } else if (status.includes("ERR") || status.includes("ERROR")) {
        return "text-danger";
    } else if (status.includes("CHARGING") || status.includes("MAINTENANCE")) {
        return "text-secondary";
    }
    return "text-light";
}

/**
 * Helper to append text to the log terminal
 */
function updateLog(message) {
    let logs = $('#sysLogs');
    // Safety check: does the log container exist on this page?
    if (logs.length === 0) return;

    let time = new Date().toLocaleTimeString();
    logs.prepend(`<div class="log-entry"><span class="text-muted">[${time}]</span> ${message}</div>`);
    
    if (logs.children().length > 30) {
        logs.children().last().remove();
    }
}

/**
 * Initialize health monitoring charts
 */
function initHealthCharts() {
    console.log("Initializing health charts...");
    
    // Check if Chart.js is loaded
    if (typeof Chart === 'undefined') {
        console.error("Chart.js is not loaded!");
        return;
    }
    
    // Check if canvas elements exist
    const batteryCanvas = document.getElementById('batteryChart');
    const tempCanvas = document.getElementById('tempChart');
    
    if (!batteryCanvas || !tempCanvas) {
        console.error("Chart canvas elements not found!");
        return;
    }
    
    console.log("Canvas elements found, creating charts...");
    
    // Common chart configuration
    const commonOptions = {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
            legend: {
                display: false
            },
            tooltip: {
                mode: 'index',
                intersect: false,
                backgroundColor: 'rgba(0, 0, 0, 0.8)',
                titleColor: 'rgba(0, 243, 255, 1)',
                bodyColor: 'rgba(200, 200, 200, 1)',
                borderColor: 'rgba(0, 243, 255, 0.5)',
                borderWidth: 1
            }
        },
        scales: {
            x: {
                type: 'time',
                time: {
                    unit: 'minute',
                    displayFormats: {
                        minute: 'HH:mm'
                    }
                },
                grid: {
                    color: 'rgba(0, 243, 255, 0.1)'
                },
                ticks: {
                    color: 'rgba(0, 243, 255, 0.6)',
                    maxTicksLimit: 6,
                    font: {
                        size: 9
                    }
                }
            },
            y: {
                grid: {
                    color: 'rgba(0, 243, 255, 0.1)'
                },
                ticks: {
                    color: 'rgba(0, 243, 255, 0.6)',
                    font: {
                        size: 9
                    }
                }
            }
        },
        elements: {
            point: {
                radius: 2,
                hoverRadius: 4
            },
            line: {
                tension: 0.4
            }
        }
    };

    // Battery Chart
    const batteryCtx = batteryCanvas.getContext('2d');
    batteryChart = new Chart(batteryCtx, {
        type: 'line',
        data: {
            datasets: [{
                label: 'Battery Voltage',
                data: [],
                borderColor: 'rgba(0, 243, 255, 0.8)',
                backgroundColor: 'rgba(0, 243, 255, 0.1)',
                fill: true,
                borderWidth: 2
            }]
        },
        options: {
            ...commonOptions,
            scales: {
                ...commonOptions.scales,
                y: {
                    ...commonOptions.scales.y,
                    suggestedMin: 20,
                    suggestedMax: 26,
                    ticks: {
                        ...commonOptions.scales.y.ticks,
                        callback: function(value) {
                            return value + 'V';
                        }
                    }
                }
            }
        }
    });
    
    console.log("Battery chart created:", batteryChart);

    // Temperature Chart
    const tempCtx = tempCanvas.getContext('2d');
    tempChart = new Chart(tempCtx, {
        type: 'line',
        data: {
            datasets: [{
                label: 'CPU Temperature',
                data: [],
                borderColor: 'rgba(255, 100, 100, 0.8)',
                backgroundColor: 'rgba(255, 100, 100, 0.1)',
                fill: true,
                borderWidth: 2
            }]
        },
        options: {
            ...commonOptions,
            scales: {
                ...commonOptions.scales,
                y: {
                    ...commonOptions.scales.y,
                    suggestedMin: 30,
                    suggestedMax: 70,
                    ticks: {
                        ...commonOptions.scales.y.ticks,
                        callback: function(value) {
                            return value + '°C';
                        }
                    }
                }
            }
        }
    });
    
    console.log("Temperature chart created:", tempChart);

    // Initial data fetch
    fetchHealthHistory();
}

/**
 * Fetch health history data and update charts
 */
function fetchHealthHistory(date = null) {
    const tzOffset = getTimezoneOffset();
    const url = date 
        ? `/api/health_history?date=${date}&tz_offset=${tzOffset}` 
        : '/api/health_history';
    
    console.log("Fetching health history from:", url);
    
    $.getJSON(url, function(data) {
        console.log("Health history data received:", data);
        updateHealthCharts(data);
    }).fail(function(xhr, status, error) {
        console.error("Health history endpoint unreachable:", error);
    });
}

/**
 * Update health charts with new data
 */
function updateHealthCharts(data) {
    console.log("Updating charts with data:", data);
    
    if (!batteryChart || !tempChart) {
        console.error("Charts not initialized!");
        return;
    }
    
    console.log("Battery data points:", data.battery.length);
    console.log("Temperature data points:", data.temperature.length);
    
    // Update battery chart
    batteryChart.data.datasets[0].data = data.battery.map(point => ({
        x: new Date(point.time),
        y: point.value
    }));
    batteryChart.update('none'); // 'none' for no animation
    
    console.log("Battery chart updated");
    
    // Update temperature chart
    tempChart.data.datasets[0].data = data.temperature.map(point => ({
        x: new Date(point.time),
        y: point.value
    }));
    tempChart.update('none');
    
    console.log("Temperature chart updated");
}

/**
 * Initialize timeline scrubber
 */
function initTimeline() {
    const track = document.getElementById('timelineTrack');
    const handle = document.getElementById('timelineHandle');
    
    if (!track || !handle) {
        console.error("Timeline elements not found");
        return;
    }
    
    console.log("Initializing timeline scrubber...");
    
    // Mouse/Touch event handlers
    let startX, startLeft;
    
    const onDragStart = (e) => {
        isTimelineDragging = true;
        timelineAutoUpdate = false;
        
        const clientX = e.type.includes('mouse') ? e.clientX : e.touches[0].clientX;
        startX = clientX;
        startLeft = handle.offsetLeft;
        
        handle.style.cursor = 'grabbing';
        e.preventDefault();
    };
    
    const onDrag = (e) => {
        if (!isTimelineDragging) return;
        
        const clientX = e.type.includes('mouse') ? e.clientX : e.touches[0].clientX;
        const trackRect = track.getBoundingClientRect();
        const relativeX = clientX - trackRect.left;
        const percent = Math.max(0, Math.min(100, (relativeX / trackRect.width) * 100));
        
        updateTimelinePosition(percent);
        e.preventDefault();
    };
    
    const onDragEnd = () => {
        if (!isTimelineDragging) return;
        
        isTimelineDragging = false;
        handle.style.cursor = 'grab';
    };
    
    // Click on track to jump
    track.addEventListener('click', (e) => {
        if (e.target === handle) return;
        
        const trackRect = track.getBoundingClientRect();
        const relativeX = e.clientX - trackRect.left;
        const percent = (relativeX / trackRect.width) * 100;
        
        timelineAutoUpdate = false;
        updateTimelinePosition(percent);
    });
    
    // Mouse events
    handle.addEventListener('mousedown', onDragStart);
    document.addEventListener('mousemove', onDrag);
    document.addEventListener('mouseup', onDragEnd);
    
    // Touch events
    handle.addEventListener('touchstart', onDragStart);
    document.addEventListener('touchmove', onDrag);
    document.addEventListener('touchend', onDragEnd);
    
    console.log("Timeline scrubber initialized");
}

/**
 * Update timeline position and corresponding robot position
 */
function updateTimelinePosition(percent) {
    const handle = document.getElementById('timelineHandle');
    const progress = document.getElementById('timelineProgress');
    
    if (!handle || !progress) return;
    
    // Clamp percentage
    percent = Math.max(0, Math.min(100, percent));
    
    // Update visual position
    handle.style.left = percent + '%';
    progress.style.width = percent + '%';
    
    // Update data index
    if (timelineData.length > 0) {
        currentTimelineIndex = Math.floor((percent / 100) * (timelineData.length - 1));
        updateRobotPositionFromTimeline(currentTimelineIndex);
    }
}

/**
 * Update robot position based on timeline index
 */
function updateRobotPositionFromTimeline(index) {
    if (!timelineData || timelineData.length === 0) return;
    
    index = Math.max(0, Math.min(timelineData.length - 1, index));
    const dataPoint = timelineData[index];
    
    // Check for collision before updating position
    let finalX = dataPoint.x;
    let finalY = dataPoint.y;
    
    if (checkCollision(finalX, finalY)) {
        console.warn(`Timeline position collision at (${finalX}, ${finalY}), adjusting`);
        const validPos = findNearestValidPosition(finalX, finalY);
        finalX = validPos.x;
        finalY = validPos.y;
    }
    
    // Update robot marker position
    $('#robotMarker').css({
        'top': finalY + '%',
        'left': finalX + '%'
    });
    
    // Update robot marker rotation if orientation is available
    if (dataPoint.orientation !== undefined) {
        const rotation = dataPoint.orientation - 90;
        $('#robotMarker').css('transform', `translate(-50%, -50%)`);// rotate(${rotation}deg)`);
    } else {
        $('#robotMarker').css('transform', 'translate(-50%, -50%)');
    }
    
    // Update current time display
    const timestamp = new Date(dataPoint.timestamp);
    $('#timelineCurrent').text(timestamp.toLocaleTimeString());
    
    // Update info text
    const pointNum = index + 1;
    $('#timelineInfo').text(`Point ${pointNum} of ${timelineData.length}`);
}

/**
 * Update timeline data when path history changes
 */
function updateTimelineData(pathData) {
    if (!pathData || pathData.length === 0) return;
    
    console.log("Updating timeline with", pathData.length, "data points");
    
    timelineData = pathData;
    
    // Update start/end time labels
    if (timelineData.length > 0) {
        const startTime = new Date(timelineData[0].timestamp);
        const endTime = new Date(timelineData[timelineData.length - 1].timestamp);
        
        $('#timelineStart').text(startTime.toLocaleTimeString());
        $('#timelineEnd').text(endTime.toLocaleTimeString());
        $('#timelineDataPoints').text(timelineData.length + ' data points');
    }
    
    // Auto-update timeline position to latest point if enabled
    // But DON'T update robot marker - that should come from fetchTelemetry() in live mode
    if (timelineAutoUpdate && isLiveMode) {
        currentTimelineIndex = timelineData.length - 1;
        const percent = (currentTimelineIndex / (timelineData.length - 1)) * 100;
        
        // Update timeline UI position only, not robot marker
        const handle = document.getElementById('timelineHandle');
        const progress = document.getElementById('timelineProgress');
        
        if (handle && progress) {
            handle.style.left = percent + '%';
            progress.style.width = percent + '%';
        }
        
        // Update current time display
        if (timelineData.length > 0) {
            const timestamp = new Date(timelineData[timelineData.length - 1].timestamp);
            $('#timelineCurrent').text(timestamp.toLocaleTimeString());
        }
    }
}