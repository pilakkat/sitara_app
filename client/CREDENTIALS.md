# SITARA Authentication Guide

## User Credentials

The SITARA system has two types of users defined in the server's `.env` file:

### 1. Administrator
- **Username:** `admin`
- **Password:** `S1tara_Adm1n_LikeAB0sch`
- **Permissions:** 
  - Can view ALL robots in the system
  - Full access to dashboard
  - Can control any robot

### 2. Operator
- **Username:** `deepak`
- **Password:** `S1tara0perat0r`
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

The `client/config.env` file uses operator credentials by default:

```properties
ROBOT_USERNAME=deepak
ROBOT_PASSWORD=S1tara0perat0r
ROBOT_ID=1
```

**Note:** Variable names use `ROBOT_USERNAME` and `ROBOT_PASSWORD` to avoid conflicts with Windows system environment variables (like `USERNAME`).

### Testing Scenarios

#### Single Robot (Normal Operation)
```bash
cd client
python client_app.py 1
```
Uses: `deepak` / `S1tara0perat0r` (from config.env)

#### Multiple Robots (Same Operator)
```bash
# Terminal 1
python client_app.py 1

# Terminal 2
python client_app.py 2
```
All robots assigned to operator `deepak`

#### Multiple Robots (Admin Override - for testing)
```bash
# Terminal 1 - Robot as operator
python client_app.py 1 deepak S1tara0perat0r

# Terminal 2 - Robot as admin (not recommended)
python client_app.py 2 admin S1tara_Adm1n_LikeAB0sch
```

## Dashboard Login

### As Admin (See All Robots)
1. Go to http://127.0.0.1:5001/login
2. Username: `admin`
3. Password: `S1tara_Adm1n_LikeAB0sch`
4. Result: Robot dropdown shows ALL robots in the system

**Note:** After running `seed_data.py`, the SITARA-X1 robot is assigned to operator `deepak`, so admin will see it but it belongs to deepak.

### As Operator (See Assigned Robots Only)
1. Go to http://127.0.0.1:5001/login
2. Username: `deepak`
3. Password: `S1tara0perat0r`
4. Result: Robot dropdown shows only SITARA-X1 (the robot assigned to deepak)

**Security:** Operators cannot access data from robots not assigned to them, even if they know the robot ID.
1. Go to http://127.0.0.1:5001/login
2. Username: `deepak`
3. Password: `S1tara0perat0r`
4. Result: Robot dropdown shows only robots assigned to `deepak`

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

1. Edit `init_db.py`:
```python
new_operator = User(username='newoperator', password='SecurePassword123!')
db.session.add(new_operator)
```

2. Run initialization:
```bash
python init_db.py
```

3. Update client `config.env`:
```properties
USERNAME=newoperator
PASSWORD=SecurePassword123!
```

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
