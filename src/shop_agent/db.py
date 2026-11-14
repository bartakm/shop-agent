import os
import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE products (
    sku TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    category TEXT NOT NULL,
    description TEXT NOT NULL,
    price_czk INTEGER NOT NULL,
    stock INTEGER NOT NULL,
    restock_date TEXT
);
CREATE TABLE customers (
    email TEXT PRIMARY KEY,
    name TEXT NOT NULL
);
CREATE TABLE orders (
    id TEXT PRIMARY KEY,
    customer_email TEXT NOT NULL REFERENCES customers(email),
    created_at TEXT NOT NULL,
    status TEXT NOT NULL,
    carrier TEXT,
    tracking_number TEXT,
    shipped_at TEXT,
    delivered_at TEXT
);
CREATE TABLE order_items (
    order_id TEXT NOT NULL REFERENCES orders(id),
    sku TEXT NOT NULL REFERENCES products(sku),
    quantity INTEGER NOT NULL,
    unit_price_czk INTEGER NOT NULL
);
CREATE TABLE returns (
    id TEXT PRIMARY KEY,
    order_id TEXT NOT NULL REFERENCES orders(id),
    sku TEXT NOT NULL,
    quantity INTEGER NOT NULL,
    reason TEXT NOT NULL,
    created_at TEXT NOT NULL,
    status TEXT NOT NULL
);
"""

PRODUCTS = [
    ("ZR-ETH-250", "Etiopie Yirgacheffe 250 g", "káva", "Zrnková káva, světlé pražení, tóny jasmínu a citrusů. Vhodná na filtr.", 329, 42, None),
    ("ZR-ETH-1000", "Etiopie Yirgacheffe 1 kg", "káva", "Zrnková káva, světlé pražení, tóny jasmínu a citrusů. Vhodná na filtr.", 1149, 6, None),
    ("ZR-BRA-250", "Brazílie Cerrado 250 g", "káva", "Zrnková káva, střední pražení, čokoláda a ořechy. Vhodná na espresso.", 279, 0, "2026-11-20"),
    ("ZR-BRA-1000", "Brazílie Cerrado 1 kg", "káva", "Zrnková káva, střední pražení, čokoláda a ořechy. Vhodná na espresso.", 949, 3, None),
    ("ZR-COL-250", "Kolumbie Huila bez kofeinu 250 g", "káva", "Bezkofeinová zrnková káva (Swiss Water), karamel a červené jablko.", 349, 15, None),
    ("ZR-ESP-1000", "Espresso směs Zrnko 1 kg", "káva", "Směs Brazílie a Indie, tmavší pražení, nízká kyselost. Pro espresso i moka konvičku.", 899, 25, None),
    ("ZR-V60-02", "Hario V60 dripper 02, keramika", "příslušenství", "Keramický dripper na 1-4 šálky. Bílý.", 590, 8, None),
    ("ZR-FLT-100", "Filtry Hario V60 02, 100 ks", "příslušenství", "Papírové filtry pro dripper V60 velikosti 02.", 149, 60, None),
    ("ZR-GRD-C2", "Ruční mlýnek Timemore C2", "příslušenství", "Ruční mlýnek s ocelovými kameny, nastavitelné hrubosti od espressa po french press.", 1690, 0, "2026-12-03"),
    ("ZR-KET-600", "Konvice Fellow Stagg 0,6 l", "příslušenství", "Konvice s husím krkem na přelévanou kávu. Na plotýnku, ne indukce.", 1990, 2, None),
    ("ZR-AER-01", "AeroPress Original", "příslušenství", "Ruční lis na kávu, včetně 350 filtrů.", 1090, 11, None),
    ("ZR-GIFT-500", "Dárková poukázka 500 Kč", "poukázky", "Elektronická poukázka, platnost 12 měsíců.", 500, 999, None),
]

CUSTOMERS = [
    ("jana.novakova@example.cz", "Jana Nováková"),
    ("petr.svoboda@example.cz", "Petr Svoboda"),
    ("eva.dvorakova@example.cz", "Eva Dvořáková"),
    ("tomas.kral@example.cz", "Tomáš Král"),
]

ORDERS = [
    ("OBJ-1041", "jana.novakova@example.cz", "2026-11-02", "doručeno", "Zásilkovna", "Z1234567890", "2026-11-03", "2026-11-05"),
    ("OBJ-1052", "petr.svoboda@example.cz", "2026-11-11", "odesláno", "PPL", "PPL40917733", "2026-11-12", None),
    ("OBJ-1058", "petr.svoboda@example.cz", "2026-11-13", "zaplaceno", None, None, None, None),
    ("OBJ-0987", "eva.dvorakova@example.cz", "2026-10-14", "doručeno", "Česká pošta", "DR1188899CZ", "2026-10-15", "2026-10-17"),
    ("OBJ-1060", "tomas.kral@example.cz", "2026-11-14", "nová", None, None, None, None),
]

ORDER_ITEMS = [
    ("OBJ-1041", "ZR-V60-02", 1, 590),
    ("OBJ-1041", "ZR-FLT-100", 2, 149),
    ("OBJ-1041", "ZR-ETH-250", 2, 329),
    ("OBJ-1052", "ZR-ESP-1000", 1, 899),
    ("OBJ-1052", "ZR-AER-01", 1, 1090),
    ("OBJ-1058", "ZR-BRA-1000", 1, 949),
    ("OBJ-0987", "ZR-KET-600", 1, 1990),
    ("OBJ-1060", "ZR-COL-250", 3, 349),
]


def db_path() -> Path:
    return Path(os.environ.get("SHOP_DB", Path.cwd() / "data" / "shop.db"))


def create(path: Path | str) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.executescript(SCHEMA)
    conn.executemany("INSERT INTO products VALUES (?,?,?,?,?,?,?)", PRODUCTS)
    conn.executemany("INSERT INTO customers VALUES (?,?)", CUSTOMERS)
    conn.executemany("INSERT INTO orders VALUES (?,?,?,?,?,?,?,?)", ORDERS)
    conn.executemany("INSERT INTO order_items VALUES (?,?,?,?)", ORDER_ITEMS)
    conn.commit()
    conn.row_factory = sqlite3.Row
    return conn


def connect(path: Path | str | None = None) -> sqlite3.Connection:
    path = Path(path) if path else db_path()
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        create(path).close()
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn
