import models
from database import engine, SessionLocal
from auth import hash_password

def seed_database():
    # Make sure tables exist
    models.Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    
    try:
        # 1. Create Default Admin User
        admin_user = db.query(models.User).filter(models.User.username == "admin").first()
        if not admin_user:
            admin_user = models.User(
                username="admin",
                email="admin@calvarygospel.org",
                password_hash=hash_password("adminpassword123"),
                role="admin"
            )
            db.add(admin_user)
            db.commit()
            print("Default admin created successfully: admin / adminpassword123")
        else:
            print("Admin user already exists.")
            
        # 2. Seed Default Settings
        settings = db.query(models.Settings).first()
        if not settings:
            settings = models.Settings(
                youtube_link="",  # Empty initially -> Show Coming Soon
                hero_title="Calvary Gospel Prayer Fellowship",
                hero_subtitle="Experience the blessings and grace of our Lord Jesus Christ",
                contact_phone="+91 97010 20668",
                contact_email="info@calvarygospel.org"
            )
            db.add(settings)
            db.commit()
            print("Default settings seeded.")

        # 3. Seed Founder Profile
        founder = db.query(models.FounderProfile).first()
        if not founder:
            founder = models.FounderProfile(
                name="కొనగంటి ప్రకాష్బాబు గారు",
                about="",  # Empty bio initially -> Show Coming Soon
                birth_date="",
                death_date="",
                highlights="",
                photo=""
            )
            db.add(founder)
            db.commit()
            print("Default founder profile created (Coming Soon state).")

        # 4. Seed Pastor Profile
        pastor = db.query(models.PastorProfile).first()
        if not pastor:
            pastor = models.PastorProfile(
                name="",  # Empty name initially -> Show Coming Soon
                role="Pastor",
                about="",  # Empty bio initially -> Show Coming Soon
                message="",
                photo=""
            )
            db.add(pastor)
            db.commit()
            print("Default pastor profile created (Coming Soon state).")

        # 5. Seed the 4 Initial Churches
        initial_churches = [
            {
                "name": "Dubacherla",
                "address": "Dubacharala Gandhi colony",
                "map_link": "https://maps.app.goo.gl/q2v12ih589cvSZrC6",
                "contact": "+91 97010 20668",
                "timings": "Sunday morning 6:00 to 8:30, Saturday night 7:00 to 10:00",
                "about": "Welcome to Calvary Gospel Prayer Fellowship in Dubacherla. We gather every Saturday night and Sunday morning for prayer, worship, and study of the Word."
            },
            {
                "name": "Ramachandrapuram",
                "address": "Ramachandrapuram, Unguturu Mandal, Eluru District",
                "map_link": "https://maps.app.goo.gl/n3LddBQUWJqH7TtC9",
                "contact": "+91 97010 20668",
                "timings": "Sunday morning 11:00 to 1:00, Friday night 7:00 to 10:00",
                "about": "Welcome to our Ramachandrapuram branch. Join our community for uplifting Sunday services and Friday night youth fellowship."
            },
            {
                "name": "Marelamudi",
                "address": "Marelamudi",
                "map_link": "https://maps.app.goo.gl/rKteXgSXBUyUsRJH6",
                "contact": "+91 97010 20668",
                "timings": "Sunday morning 12:30 to 2:00",
                "about": "Welcome to Marelamudi Calvary Gospel branch. We hold holy services every Sunday afternoon. Join us in praise."
            },
            {
                "name": "Dubacherla Colony",
                "address": "",  # Blank initially as requested
                "map_link": "https://maps.app.goo.gl/q2v12ih589cvSZrC6",
                "contact": "+91 97010 20668",
                "timings": "Sunday morning 8:00 to 10:00",
                "about": "Our Dubacherla Colony branch is growing. Sunday morning fellowship is from 8:00 AM to 10:00 AM."
            }
        ]
        
        for c in initial_churches:
            exists = db.query(models.Church).filter(models.Church.name == c["name"]).first()
            if not exists:
                church = models.Church(
                    name=c["name"],
                    address=c["address"],
                    map_link=c["map_link"],
                    contact=c["contact"],
                    timings=c["timings"],
                    about=c["about"],
                    cover_image=None
                )
                db.add(church)
                db.commit()
                print(f"Church branch '{c['name']}' seeded.")
            else:
                print(f"Church branch '{c['name']}' already exists.")

        print("Database seeding completed successfully.")
        
    except Exception as e:
        print(f"Seeding failed: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    seed_database()
