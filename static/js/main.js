/* * SITARA DYNAMICS - Client Side Logic
 * File: static/js/main.js
 */

// Global variables for path visualization
let pathCanvas, pathCtx;
let pathHistory = [];
let lastLogCount = 0;
let isLiveMode = true;
let pollingIntervals = [];

// Ensure functions are available globally for button onclick events
window.sendCommand = function(cmd) {
    console.log("Attempting to send command:", cmd);
    // Visual feedback
    updateLog(`> SENDING COMMAND: ${cmd}...`);

    $.ajax({
        url: '/api/command',
        type: 'POST',
        contentType: 'application/json',
        data: JSON.stringify({ command: cmd }),
        success: function(response) {
            updateLog(`> ACK: ${response.msg}`);
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
    
    // Stop live polling
    stopPolling();
    
    // Update UI
    $('#dataMode').text('MODE: HISTORICAL - ' + selectedDate);
    
    // Load historical data
    fetchHistoricalTelemetry(selectedDate);
    fetchHistoricalPath(selectedDate);
    fetchHistoricalLogs(selectedDate);
};

// Return to live mode
window.loadLiveData = function() {
    console.log("Returning to live mode");
    isLiveMode = true;
    
    // Clear date selector
    $('#dateSelector').val('');
    $('#dataMode').text('MODE: LIVE');
    
    // Restart live polling
    startPolling();
};

$(document).ready(function() {
    console.log("SITARA SYSTEM: Core JS loaded.");

    // --- DASHBOARD SPECIFIC LOGIC ---
    // Only run polling if we are actually on the dashboard page
    if ($('#dashboard-view').length > 0) {
        console.log("Dashboard View Detected. Initializing Telemetry Stream...");
        
        // Initialize canvas for path visualization
        initPathCanvas();
        
        // Set date picker to today
        const today = new Date().toISOString().split('T')[0];
        $('#dateSelector').val(today);
        $('#dateSelector').attr('max', today);  // Prevent future dates
        
        // Calculate min date (7 days ago based on seed data)
        const minDate = new Date();
        minDate.setDate(minDate.getDate() - 7);
        $('#dateSelector').attr('min', minDate.toISOString().split('T')[0]);
        
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
    
    // Then start the polling loops
    pollingIntervals.push(setInterval(fetchTelemetry, 2000));        // Update every 2 seconds
    pollingIntervals.push(setInterval(fetchPathHistory, 3000));      // Update path every 3 seconds
    pollingIntervals.push(setInterval(fetchTelemetryLogs, 5000));    // Update logs every 5 seconds
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
    $.getJSON('/api/telemetry', function(data) {
        updateTelemetryDisplay(data);
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
    $.getJSON('/api/telemetry_at_time?date=' + date, function(data) {
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

    // 5. Move Robot on Map
    $('#robotMarker').css({
        'top': data.pos_y + '%',
        'left': data.pos_x + '%'
    });
    
    // Add rotation if orientation is available
    if (data.orientation !== undefined) {
        $('#robotMarker').css('transform', `translate(-50%, -50%) rotate(${data.orientation}deg)`);
    }
}

/**
 * Fetches and draws the robot's path history
 */
function fetchPathHistory() {
    $.getJSON('/api/path_history', function(data) {
        if (!pathCtx || !data || data.length === 0) return;
        
        pathHistory = data;
        drawPath();
    }).fail(function() {
        console.warn("Path history endpoint unreachable.");
    });
}

/**
 * Fetch historical path for specific date
 */
function fetchHistoricalPath(date) {
    $.getJSON('/api/path_history?date=' + date, function(data) {
        if (!pathCtx || !data || data.length === 0) {
            console.warn("No path data for this date");
            pathHistory = [];
            clearCanvas();
            return;
        }
        
        pathHistory = data;
        drawPath();
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
    $.getJSON('/api/telemetry_history', function(data) {
        displayLogs(data);
    }).fail(function() {
        console.warn("Telemetry history endpoint unreachable.");
    });
}

/**
 * Fetch historical logs for specific date
 */
function fetchHistoricalLogs(date) {
    $.getJSON('/api/telemetry_history?date=' + date, function(data) {
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
    if (!data || data.length === 0) return;
    
    // Only update if we have new logs (skip for historical mode)
    if (isLiveMode && data.length === lastLogCount) return;
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