import json
from contextlib import closing

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from . import db, shop

mcp = MCPServer(
    "zrnko-erp",
    instructions="ERP of Zrnko, a small Czech coffee e-shop: products, stock, orders and returns.",
)


def _run(fn, *args) -> str:
    with closing(db.connect()) as conn:
        try:
            return json.dumps(fn(conn, *args), ensure_ascii=False, indent=1)
        except shop.ShopError as e:
            raise ToolError(str(e)) from e


@mcp.tool()
def search_products(query: str) -> str:
    """Full-text search in the product catalogue (name, category, description, SKU).
    Returns price, stock and, for sold-out items, the expected restock date.

    Args:
        query: Words to match, e.g. "mlýnek" or "espresso 1 kg". Czech works best.
    """
    return _run(shop.search_products, query)


@mcp.tool()
def get_product(sku: str) -> str:
    """Get one product by SKU, including current stock.

    Args:
        sku: Product code, e.g. ZR-ETH-250.
    """
    return _run(shop.get_product, sku)


@mcp.tool()
def get_order(order_id: str, customer_email: str) -> str:
    """Get an order with items, status, carrier, tracking number and existing returns.
    Only returns the order if it belongs to customer_email.

    Args:
        order_id: Order number, e.g. OBJ-1041.
        customer_email: E-mail of the customer who placed the order.
    """
    return _run(shop.get_order, order_id, customer_email)


@mcp.tool()
def list_orders(customer_email: str) -> str:
    """List all orders of a customer, newest first (id, date, status).

    Args:
        customer_email: E-mail of the customer.
    """
    return _run(shop.list_orders, customer_email)


@mcp.tool()
def create_return(order_id: str, customer_email: str, sku: str, quantity: int, reason: str) -> str:
    """Register a return (odstoupení od smlouvy) for a delivered order item.
    The ERP enforces the rules: order must be delivered, within 14 days of delivery,
    and quantity cannot exceed what was ordered minus earlier returns.
    Returns the return id and where to send the goods.

    Args:
        order_id: Order number, e.g. OBJ-1041.
        customer_email: E-mail of the customer who placed the order.
        sku: SKU of the item to return.
        quantity: Number of pieces to return.
        reason: Short reason given by the customer.
    """
    return _run(shop.create_return, order_id, customer_email, sku, quantity, reason)


@mcp.resource("shop://policy", mime_type="text/plain")
def policy() -> str:
    """Shipping, payment, return and complaint policy of the shop."""
    return shop.POLICY


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
