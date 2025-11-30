"""Initialize database with new software version model"""
from app import app, db, SoftwareVersion

with app.app_context():
    # Create all tables
    db.create_all()
    
    # Check if we need to initialize default versions
    existing = SoftwareVersion.query.count()
    
    if existing == 0:
        print("Creating default software versions...")
        controllers = [
            ('RCPCU', '2.3.1', 'Robot Central Processing & Control Unit - Initial version'),
            ('RCSPM', '1.8.5', 'Robot Control System & Power Management - Initial version'),
            ('RCMMC', '3.1.2', 'Robot Control Motion & Motor Controller - Initial version'),
            ('RCPMU', '1.5.9', 'Robot Control Power Management Unit - Initial version')
        ]
        
        for name, version, notes in controllers:
            sv = SoftwareVersion(
                controller_name=name,
                version=version,
                release_notes=notes,
                is_published=False
            )
            db.session.add(sv)
        
        db.session.commit()
        print(f"✓ Created {len(controllers)} default software version entries")
    else:
        print(f"Database already has {existing} software versions")
    
    print("✓ Database initialized successfully!")
