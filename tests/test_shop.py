import pytest

from shop_agent import shop
from shop_agent.shop import ShopError


def test_search_marks_sold_out_with_restock_date(conn):
    [grinder] = shop.search_products(conn, "mlýnek")
    assert grinder["available"] is False
    assert grinder["restock_date"] == "2026-12-03"


def test_order_hidden_from_other_customer(conn):
    with pytest.raises(ShopError, match="nebyla nalezena"):
        shop.get_order(conn, "OBJ-1041", "someone.else@example.cz")


def test_order_detail_has_items_and_total(conn):
    order = shop.get_order(conn, "obj-1041", "Jana.Novakova@example.cz")
    assert order["total_czk"] == 590 + 2 * 149 + 2 * 329
    assert {i["sku"] for i in order["items"]} == {"ZR-V60-02", "ZR-FLT-100", "ZR-ETH-250"}


def test_return_within_window(conn):
    r = shop.create_return(conn, "OBJ-1041", "jana.novakova@example.cz", "ZR-V60-02", 1, "dárek dvakrát")
    assert r["return_id"] == "VR-0001"
    assert shop.get_order(conn, "OBJ-1041", "jana.novakova@example.cz")["returns"][0]["sku"] == "ZR-V60-02"


def test_return_cannot_exceed_ordered_quantity(conn):
    shop.create_return(conn, "OBJ-1041", "jana.novakova@example.cz", "ZR-V60-02", 1, "x")
    with pytest.raises(ShopError, match="už vráceno 1"):
        shop.create_return(conn, "OBJ-1041", "jana.novakova@example.cz", "ZR-V60-02", 1, "x")


def test_return_after_14_days_refused(conn):
    with pytest.raises(ShopError, match="Lhůta 14 dnů"):
        shop.create_return(conn, "OBJ-0987", "eva.dvorakova@example.cz", "ZR-KET-600", 1, "indukce")


def test_return_of_undelivered_order_refused(conn):
    with pytest.raises(ShopError, match="nebyla doručena"):
        shop.create_return(conn, "OBJ-1052", "petr.svoboda@example.cz", "ZR-AER-01", 1, "x")
