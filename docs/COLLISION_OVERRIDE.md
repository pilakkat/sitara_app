# Collision Detection Override System

## Problem
When a robot is initialized with a position inside an obstacle (e.g., demo database with test positions), it becomes locked and unable to move. This can happen when:
- Restoring position from database after map changes
- Using demo/test data
- Manual position overrides in database

## Solution
Automatic position correction when obstacles are detected at startup.

## How It Works

### 1. Detection
When the robot restores its last position from the server, the system checks if it's inside an obstacle using `is_valid_position()`.

### 2. Position Correction
If an unsafe position is detected, `find_nearest_safe_position()` searches for the closest valid position using a spiral search pattern:
- Checks positions in expanding circles (radius 1-50 units)
- Tests every 15 degrees around the current position
- Returns the first valid position found
- Falls back to map center (50, 50) if no position found

### 3. Automatic Application
The corrected position is automatically applied during startup, before telemetry begins.

## Code Location
`client/client_app.py`:
- Lines 111-147: `find_nearest_safe_position()` function
- Lines 487-500: Position restoration with safety check

## Example Output
```
[ROBOT-1] ✓ Restored last position: (28.9, 50.5), orientation: 275.5°
[COLLISION] Position (28.9, 50.5) is inside obstacle, finding safe position...
[COLLISION] Found safe position at (42.9, 50.5), distance: 14.0
[ROBOT-1] ⚠ Corrected to safe position: (42.9, 50.5)
```

## Configuration
- `COLLISION_BUFFER = 2`: Safety margin around obstacles (units)
- `MAP_SAFE_MIN = 5`: Minimum safe coordinate
- `MAP_SAFE_MAX = 95`: Maximum safe coordinate
- Maximum search radius: 50 units
- Search resolution: 15° increments

## Testing
Run the test suite:
```bash
cd client
python test_obstacle_override.py
```

The test verifies that robots in all obstacle types (walls, furniture) are successfully moved to safe positions.

## Production Notes
In reality, this situation won't occur because:
- Robots track their actual physical positions
- The collision detection prevents movement into obstacles
- Position restoration comes from real telemetry, not test data

This override is primarily for demo systems and development environments where test data may place robots in impossible positions.
