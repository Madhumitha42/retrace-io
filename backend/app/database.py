import sqlite3
import os
from contextlib import contextmanager

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "lost_found.db")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

@contextmanager
def get_db_context():
    conn = get_db()
    try:
        yield conn
    finally:
        conn.close()

PUBLIC_LOST_FIELDS = {
    "id", "title", "description", "category", "primary_color",
    "location_name", "latitude", "longitude", "lost_datetime",
    "owner_name", "image_url", "image_hash", "created_at"
}

PUBLIC_FOUND_FIELDS = {
    "id", "title", "description", "category", "primary_color",
    "location_name", "latitude", "longitude", "found_datetime",
    "finder_name", "image_url", "image_hash", "public_notes", "created_at"
}

def to_public_lost(item: dict) -> dict:
    """Return a projection of lost item dict containing only public safe fields."""
    if not item:
        return {}
    return {k: v for k, v in item.items() if k in PUBLIC_LOST_FIELDS}

def to_public_found(item: dict) -> dict:
    """Return a projection of found item dict containing only public safe fields."""
    if not item:
        return {}
    return {k: v for k, v in item.items() if k in PUBLIC_FOUND_FIELDS}

def init_db():
    """Create SQLite tables, indexes, column migrations and insert initial realistic seed data."""
    with get_db_context() as conn:
        cursor = conn.cursor()

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS lost_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            category TEXT NOT NULL,
            primary_color TEXT NOT NULL,
            location_name TEXT NOT NULL,
            latitude REAL NOT NULL,
            longitude REAL NOT NULL,
            lost_datetime TEXT NOT NULL,
            hidden_characteristic TEXT NOT NULL,
            owner_name TEXT NOT NULL,
            owner_contact TEXT NOT NULL,
            image_url TEXT,
            image_hash TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS found_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            category TEXT NOT NULL,
            primary_color TEXT NOT NULL,
            location_name TEXT NOT NULL,
            latitude REAL NOT NULL,
            longitude REAL NOT NULL,
            found_datetime TEXT NOT NULL,
            finder_name TEXT NOT NULL,
            finder_contact TEXT NOT NULL,
            image_url TEXT,
            image_hash TEXT,
            public_notes TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS match_verifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lost_item_id INTEGER,
            found_item_id INTEGER,
            claimant_input TEXT,
            similarity_score REAL,
            is_verified INTEGER,
            client_ip TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        """)

        # Migrations for existing DBs if columns are missing
        cursor.execute("PRAGMA table_info(lost_items)")
        lost_cols = [row[1] for row in cursor.fetchall()]
        if "image_hash" not in lost_cols:
            cursor.execute("ALTER TABLE lost_items ADD COLUMN image_hash TEXT")

        cursor.execute("PRAGMA table_info(found_items)")
        found_cols = [row[1] for row in cursor.fetchall()]
        if "image_hash" not in found_cols:
            cursor.execute("ALTER TABLE found_items ADD COLUMN image_hash TEXT")

        cursor.execute("PRAGMA table_info(match_verifications)")
        verif_cols = [row[1] for row in cursor.fetchall()]
        if "client_ip" not in verif_cols:
            cursor.execute("ALTER TABLE match_verifications ADD COLUMN client_ip TEXT")

        # Create indexes on category and created_at
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_lost_category ON lost_items(category);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_lost_created ON lost_items(created_at);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_found_category ON found_items(category);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_found_created ON found_items(created_at);")

        # Seed data check
        cursor.execute("SELECT COUNT(*) FROM lost_items")
        lost_count = cursor.fetchone()[0]

        if lost_count == 0:
            lost_seeds = [
                (
                    "Black College Bag",
                    "I lost a black college bag near the library. It has a blue water bottle in the side pocket and notebook inside.",
                    "Bag",
                    "Black",
                    "College Library Main Entrance",
                    12.9716,
                    77.5946,
                    "2026-09-18T14:00:00",
                    "Blue keychain with turtle attached to left zipper, small tear on bottom strap",
                    "Rohan Sharma",
                    "rohan.sharma@example.edu",
                    "https://images.unsplash.com/photo-1553062407-98eeb64c6a62?auto=format&fit=crop&w=600&q=80",
                    None
                ),
                (
                    "iPhone 15 Pro",
                    "Lost my dark grey iPhone near the Student Cafeteria around lunchtime. Has a transparent silicone case.",
                    "Electronics",
                    "Grey",
                    "Student Cafeteria Block A",
                    12.9722,
                    77.5950,
                    "2026-09-18T12:30:00",
                    "Lockscreen wallpaper is a golden retriever puppy, scratch on bottom left bezel",
                    "Ananya Patel",
                    "ananya.p@example.com",
                    "https://images.unsplash.com/photo-1592750475338-74b7b21085ab?auto=format&fit=crop&w=600&q=80",
                    None
                ),
                (
                    "Silver Car Keys",
                    "Set of silver keys lost near the Sports Complex basketball court.",
                    "Keys",
                    "Silver",
                    "Campus Sports Complex",
                    12.9705,
                    77.5930,
                    "2026-09-17T18:00:00",
                    "Red leather lanyard with a brass compass charm",
                    "Vikram Verma",
                    "vikram.v@example.com",
                    "https://images.unsplash.com/photo-1582142839970-2b9322079f82?auto=format&fit=crop&w=600&q=80",
                    None
                )
            ]

            cursor.executemany("""
                INSERT INTO lost_items (title, description, category, primary_color, location_name, latitude, longitude, lost_datetime, hidden_characteristic, owner_name, owner_contact, image_url, image_hash)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, lost_seeds)

            found_seeds = [
                (
                    "Dark Backpack",
                    "Found a dark school bag near Block B path containing a hydration bottle and some study notes.",
                    "Bag",
                    "Black",
                    "Academic Block B Pathway",
                    12.9718,
                    77.5949,
                    "2026-09-18T15:15:00",
                    "Security Desk Staff",
                    "security.desk@campus.edu",
                    "https://images.unsplash.com/photo-1553062407-98eeb64c6a62?auto=format&fit=crop&w=600&q=80",
                    None,
                    "Handed over to Block B security guard."
                ),
                (
                    "Smartphone with Clear Case",
                    "Found a grey smartphone lying on a bench outside Student Union.",
                    "Electronics",
                    "Grey",
                    "Student Union Bench",
                    12.9723,
                    77.5952,
                    "2026-09-18T13:00:00",
                    "Priya Nair",
                    "priya.nair@example.edu",
                    "https://images.unsplash.com/photo-1592750475338-74b7b21085ab?auto=format&fit=crop&w=600&q=80",
                    None,
                    "Currently with cafeteria staff."
                ),
                (
                    "Keychain with Lanyard",
                    "Found keys with a lanyard on the grass near sports ground.",
                    "Keys",
                    "Silver",
                    "Sports Ground Edge",
                    12.9708,
                    77.5933,
                    "2026-09-17T19:30:00",
                    "David Ray",
                    "david.ray@example.com",
                    "https://images.unsplash.com/photo-1582142839970-2b9322079f82?auto=format&fit=crop&w=600&q=80",
                    None,
                    "Kept safely at main gate."
                )
            ]

            cursor.executemany("""
                INSERT INTO found_items (title, description, category, primary_color, location_name, latitude, longitude, found_datetime, finder_name, finder_contact, image_url, image_hash, public_notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, found_seeds)

            conn.commit()

if __name__ == "__main__":
    init_db()
    print("Database initialized successfully.")
