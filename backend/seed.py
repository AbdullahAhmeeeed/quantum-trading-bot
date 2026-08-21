import models, database, auth
from sqlalchemy.orm import Session

def seed_user():
    db = next(database.get_db())
    if not db.query(models.User).filter(models.User.username == "admin").first():
        hashed_pw = auth.get_password_hash("quantum123")
        new_user = models.User(username="admin", email="admin@quantum.com", hashed_password=hashed_pw)
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        
        new_portfolio = models.Portfolio(user_id=new_user.id, allocated_balance=5000000.0)
        db.add(new_portfolio)
        db.commit()
        print("Seeded 'admin' user with password 'quantum123'")

if __name__ == "__main__":
    seed_user()
