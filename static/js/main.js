/* * SITARA DYNAMICS - Client Side Logic
 * File: static/js/main.js
 */

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


$(document).ready(function() {
    console.log("SITARA SYSTEM: Core JS loaded.");

    // --- DASHBOARD SPECIFIC LOGIC ---
    // Only run polling if we are actually on the dashboard page
    if ($('#dashboard-view').length > 0) {
        console.log("Dashboard View Detected. Initializing Telemetry Stream...");
        
        // Run once immediately
        fetchTelemetry();
        // Then start the polling loop (every 2 seconds)
        setInterval(fetchTelemetry, 2000);
    } else {
        console.log("Not on dashboard view. Telemetry standby.");
    }
});


/**
 * Fetches robot data from the Python backend
 */
function fetchTelemetry() {
    $.getJSON('/api/telemetry', function(data) {
        // 1. Update Numeric Values
        const batteryDisplay = (data.battery == null) ? 'N/A' : data.battery + ' V';
        $('#batteryVal').text(batteryDisplay);
        // Feed battery chart if available
        if (data.battery != null) {
            if (typeof updateBatteryChart === 'function') {
                updateBatteryChart(data.battery);
            } else {
                // Chart function not ready yet; queue the value for later flush
                window._pendingBattery = window._pendingBattery || [];
                window._pendingBattery.push(data.battery);
                console.debug('Battery value queued until chart initializes:', data.battery);
            }
        } else {
            console.debug('Battery value is null (no telemetry ingested yet).');
        }
        $('#tempVal').text(data.cpu_temp + ' °C');
        
        // 2. Update Status Badge
        let statusBadge = $('#statusVal');
        statusBadge.text(data.status);
        
        if(data.status === "OPERATIONAL") {
            statusBadge.removeClass('text-warning text-danger').addClass('text-info');
        } else {
            statusBadge.removeClass('text-info').addClass('text-warning');
        }

        // 3. Update Load Bar
        $('#loadVal').text(data.load);
        $('#loadBar').css('width', data.load + '%');
        
        if(data.load > 80) {
            $('#loadBar').removeClass('bg-info').addClass('bg-danger');
        } else {
            $('#loadBar').removeClass('bg-danger').addClass('bg-info');
        }

        // 4. Move Robot on Map
        $('#robotMarker').css({
            'top': data.pos_y + '%',
            'left': data.pos_x + '%'
        });

    }).fail(function() {
        console.warn("Telemetry endpoint unreachable.");
        $('#statusVal').text("CONNECTION LOST").removeClass('text-info').addClass('text-danger');
    });
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
    
    if (logs.children().length > 20) {
        logs.children().last().remove();
    }
}