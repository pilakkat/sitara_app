# SITARA Authentication Guide

## User Credentials

The SITARA system has two types of users defined in the server's `.env` file:

### 1. Administrator
- **Username:** Set in server `.env` file
- **Password:** Set in server `.env` file (keep secure!)
- **Permissions:** 
  - Can view ALL robots in the system
  - Full access to dashboard
  - Can control any robot

### 2. Operator
- **Username:** Set in server `.env` file
- **Password:** Set in server `.env` file (keep secure!)
- **Permissions:**
  - Can view only assigned robots
  - Dashboard access
  - Can control assigned robots

## Robot Client Authentication

**Robot clients should authenticate as operators, NOT as admin.**

### Why?
- In a production system, each robot would have its own operator account
- This allows proper isolation and tracking
- Admin account is for human administrators only

### Default Client Configuration

The `client/config.env` file should contain operator credentials:

```properties
ROBOT_USERNAME=your_operator_username
ROBOT_PASSWORD=your_operator_password
ROBOT_ID=1
```

**Note:** Variable names use `ROBOT_USERNAME` and `ROBOT_PASSWORD` to avoid conflicts with Windows system environment variables (like `USERNAME`).

### Testing Scenarios

#### Single Robot (Normal Operation)
```bash
cd client
python client_app.py 1
```
Uses credentials from config.env or .env file

#### Multiple Robots (Same Operator)
```bash
# Terminal 1
python client_app.py 1

# Terminal 2
python client_app.py 2
```

#### Multiple Robots (Different Users)
```bash
# Terminal 1 - Robot as operator
python client_app.py 1 operator1 password1

# Terminal 2 - Robot as different operator
python client_app.py 2 operator2 password2
```

## Dashboard Login

### As Admin (See All Robots)
1. Go to http://127.0.0.1:5001/login
2. Enter admin username and password
3. Result: Robot dropdown shows ALL robots in the system

### As Operator (See Assigned Robots Only)
1. Go to http://127.0.0.1:5001/login
2. Enter operator username and password
3. Result: Robot dropdown shows only robots assigned to that operator

**Security:** Operators cannot access data from robots not assigned to them, even if they know the robot ID.

## Security Notes

⚠️ **Important Security Considerations:**

1. **Production Deployment:**
   - Change ALL default passwords
   - Use strong, unique passwords
   - Consider using API keys instead of passwords for robots
   - Use HTTPS for all connections
   - Store credentials in secure vaults (e.g., Azure Key Vault, AWS Secrets Manager)

2. **Robot Authentication:**
   - Each robot should have its own credentials
   - Use service accounts, not human user accounts
   - Implement certificate-based authentication for robots
   - Rotate credentials regularly

3. **Environment Files:**
   - Never commit `.env` files to version control
   - Add `.env` to `.gitignore`
   - Use different credentials for dev/staging/production

4. **Password Requirements:**
   - Minimum 12 characters
   - Mix of uppercase, lowercase, numbers, special characters
   - No dictionary words
   - Not based on system/company names

## Adding New Users

To add a new operator user:

1. Edit `init_db.py` and add the user
2. Run initialization: `python init_db.py`
3. Update client `.env` file with the new credentials

## Troubleshooting

### Client Authentication Failed
- Verify username/password in `config.env`
- Check server is running
- Verify user exists: Log into dashboard with same credentials
- Check server logs for authentication errors

### Robot Not Showing in Dropdown
- Verify robot is assigned to a user
- Run `python seed_data.py` to ensure robot entry exists
- Check if logged in as correct user (admin sees all, operators see assigned only)
- Check browser console for API errors

### "No robots available" Message
- No robots are assigned to the logged-in user
- Run seed_data.py to create initial robot
- Check database: `SELECT * FROM robots;`
