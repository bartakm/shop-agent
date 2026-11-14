import os
import sqlite3
from datetime import date

RETURN_WINDOW_DAYS = 14

POLICY = """Zrnko s.r.o. - zásady obchodu (fiktivní e-shop pro demo)

Doprava: Zásilkovna 79 Kč, PPL 119 Kč, Česká pošta 129 Kč, nad 1 500 Kč zdarma.
Expedice: zaplacené objednávky odesíláme do 2 pracovních dnů. Doručení obvykle 1-2 pracovní dny od odeslání.
Platba: kartou, převodem, dobírka +39 Kč.
Odstoupení od smlouvy: do 14 dnů od doručení bez udání důvodu. Zboží vrátit nepoškozené.
  Otevřenou kávu nelze vrátit z hygienických důvodů, pokud není vadná.
  Peníze vracíme do 14 dnů od přijetí vráceného zboží.
Reklamace vadného zboží: 24 měsíců. Reklamaci posuzuje člověk, ne automat.
Slevy, kompenzace a výjimky z pravidel schvaluje pouze vedoucí obchodu.
Kontakt na člověka: podpora@zrnko.example, Po-Pá 9-16.
"""


class ShopError(Exception):
    pass


def today() -> date:
    return date.fromisoformat(os.environ["SHOP_TODAY"]) if os.environ.get("SHOP_TODAY") else date.today()


def _product(row: sqlite3.Row) -> dict:
    p = dict(row)
    p["available"] = p["stock"] > 0
    if p["available"]:
        p.pop("restock_date")
    return p


def search_products(conn: sqlite3.Connection, query: str) -> list[dict]:
    words = [w for w in query.lower().split() if w]
    rows = conn.execute("SELECT * FROM products ORDER BY sku").fetchall()
    hits = [
        r for r in rows
        if all(w in f"{r['sku']} {r['name']} {r['category']} {r['description']}".lower() for w in words)
    ]
    return [_product(r) for r in hits]


def get_product(conn: sqlite3.Connection, sku: str) -> dict:
    row = conn.execute("SELECT * FROM products WHERE sku = ?", (sku.upper(),)).fetchone()
    if row is None:
        raise ShopError(f"Produkt {sku} neexistuje.")
    return _product(row)


def _owned_order(conn: sqlite3.Connection, order_id: str, customer_email: str) -> sqlite3.Row:
    row = conn.execute(
        "SELECT * FROM orders WHERE id = ? AND lower(customer_email) = lower(?)",
        (order_id.upper(), customer_email.strip()),
    ).fetchone()
    if row is None:
        raise ShopError(f"Objednávka {order_id} k e-mailu {customer_email} nebyla nalezena.")
    return row


def _order_detail(conn: sqlite3.Connection, order: sqlite3.Row) -> dict:
    items = conn.execute(
        """SELECT i.sku, p.name, i.quantity, i.unit_price_czk
           FROM order_items i JOIN products p ON p.sku = i.sku WHERE i.order_id = ?""",
        (order["id"],),
    ).fetchall()
    returns = conn.execute(
        "SELECT id, sku, quantity, status, created_at FROM returns WHERE order_id = ?", (order["id"],)
    ).fetchall()
    detail = {k: v for k, v in dict(order).items() if v is not None}
    detail["items"] = [dict(i) for i in items]
    detail["total_czk"] = sum(i["quantity"] * i["unit_price_czk"] for i in items)
    detail["returns"] = [dict(r) for r in returns]
    return detail


def get_order(conn: sqlite3.Connection, order_id: str, customer_email: str) -> dict:
    return _order_detail(conn, _owned_order(conn, order_id, customer_email))


def list_orders(conn: sqlite3.Connection, customer_email: str) -> list[dict]:
    rows = conn.execute(
        "SELECT id, created_at, status FROM orders WHERE lower(customer_email) = lower(?) ORDER BY created_at DESC",
        (customer_email.strip(),),
    ).fetchall()
    return [dict(r) for r in rows]


def create_return(
    conn: sqlite3.Connection, order_id: str, customer_email: str, sku: str, quantity: int, reason: str
) -> dict:
    order = _owned_order(conn, order_id, customer_email)
    if order["status"] != "doručeno":
        raise ShopError(f"Objednávka {order['id']} ještě nebyla doručena (stav: {order['status']}), vrácení nelze založit.")
    delivered = date.fromisoformat(order["delivered_at"])
    days = (today() - delivered).days
    if days > RETURN_WINDOW_DAYS:
        raise ShopError(
            f"Lhůta {RETURN_WINDOW_DAYS} dnů na odstoupení uplynula (doručeno {delivered}, tj. před {days} dny). "
            "Případnou reklamaci vady musí posoudit člověk."
        )
    sku = sku.upper()
    ordered = conn.execute(
        "SELECT COALESCE(SUM(quantity), 0) FROM order_items WHERE order_id = ? AND sku = ?", (order["id"], sku)
    ).fetchone()[0]
    already = conn.execute(
        "SELECT COALESCE(SUM(quantity), 0) FROM returns WHERE order_id = ? AND sku = ?", (order["id"], sku)
    ).fetchone()[0]
    if quantity < 1 or quantity > ordered - already:
        raise ShopError(
            f"Nelze vrátit {quantity} ks {sku}: objednáno {ordered} ks, už vráceno {already} ks."
        )
    count = conn.execute("SELECT COUNT(*) FROM returns").fetchone()[0]
    return_id = f"VR-{count + 1:04d}"
    conn.execute(
        "INSERT INTO returns VALUES (?,?,?,?,?,?,?)",
        (return_id, order["id"], sku, quantity, reason, today().isoformat(), "čeká na zboží"),
    )
    conn.commit()
    return {
        "return_id": return_id,
        "order_id": order["id"],
        "sku": sku,
        "quantity": quantity,
        "status": "čeká na zboží",
        "send_to": "Zrnko s.r.o., Sokolská 12, 702 00 Ostrava",
        "refund_note": "Peníze vrátíme do 14 dnů od přijetí zboží.",
    }
