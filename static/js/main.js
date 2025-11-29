/* * SITARA DYNAMICS - Client Side Logic
 * File: static/js/main.js
 */

// Global variables for path visualization
let pathCanvas, pathCtx;
let pathHistory = [];
let lastLogCount = 0;
let isLiveMode = true;
let pollingIntervals = [];

// Chart.js instances
let batteryChart = null;
let tempChart = null;

// Timeline scrubber state
let timelineData = [];
let currentTimelineIndex = 0;
let isTimelineDragging = false;
let timelineAutoUpdate = true;

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
    timelineAutoUpdate = false; // Disable auto-update for historical mode
    
    // Stop live polling
    stopPolling();
    
    // Update UI
    $('#dataMode').text('MODE: HISTORICAL - ' + selectedDate);
    
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
        
        // Initialize timeline scrubber
        initTimeline();
        
        // Initialize health charts
        initHealthCharts();
        
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
    fetchHealthHistory();
    
    // Then start the polling loops
    pollingIntervals.push(setInterval(fetchTelemetry, 2000));        // Update every 2 seconds
    pollingIntervals.push(setInterval(fetchPathHistory, 3000));      // Update path every 3 seconds
    pollingIntervals.push(setInterval(fetchTelemetryLogs, 5000));    // Update logs every 5 seconds
    pollingIntervals.push(setInterval(fetchHealthHistory, 10000));   // Update charts every 10 seconds
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
        
        // Update timeline with path data
        updateTimelineData(data);
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
    const url = date ? `/api/health_history?date=${date}` : '/api/health_history';
    
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
    
    // Update robot marker position
    $('#robotMarker').css({
        'top': dataPoint.y + '%',
        'left': dataPoint.x + '%'
    });
    
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
    
    // Auto-update to latest position if enabled
    if (timelineAutoUpdate && isLiveMode) {
        currentTimelineIndex = timelineData.length - 1;
        const percent = (currentTimelineIndex / (timelineData.length - 1)) * 100;
        updateTimelinePosition(percent);
    }
}