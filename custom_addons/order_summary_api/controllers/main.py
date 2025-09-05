import logging
from functools import wraps
from odoo import http
from odoo.http import request
import jwt

SECRET_KEY = "super_secret_jwt_key"  # TODO: Move to Odoo config in production
_logger = logging.getLogger(__name__)

# -----------------------
# JWT decorator
# -----------------------
def jwt_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        # Authorization: Bearer <token>
        auth_header = request.httprequest.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return {"error": "Missing or invalid Authorization header"}

        token = auth_header.split(" ")[1]
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
            user_id = payload["uid"]

            user = request.env['res.users'].sudo().browse(user_id)
            if not user.exists():
                return {"error": "Invalid user_id"}

            kwargs['env'] = request.env(user=user.id)
        except jwt.ExpiredSignatureError:
            return {"error": "Token expired"}
        except jwt.InvalidTokenError:
            return {"error": "Invalid token"}

        return func(*args, **kwargs)
    return wrapper

# -----------------------
# Order Summary Controller
# -----------------------
class OrderSummaryController(http.Controller):

    @http.route('/api/v1/order-summary', type='json', auth='none', methods=['POST'], csrf=False)
    @jwt_required
    def order_summary(self, **kwargs):
        env = kwargs.get('env')

        data = request.get_json_data()
        params = data.get("params", {})
        order_id = params.get("order_id")

        if not order_id:
            return {"error": "order_id is required"}
        try:
            order_id = int(order_id)
        except ValueError:
            return {"error": "Invalid order_id"}

        order = env['sale.order'].browse(order_id)
        if not order.exists():
            return {"error": "Order not found"}

        # Filters
        delivery_ids = params.get('delivery_ids')
        if delivery_ids:
            delivery_ids = [int(x) for x in delivery_ids.split(',')]

        product_templates = params.get('product_templates')
        if product_templates:
            product_templates = [x for x in product_templates.split(',')]

        domain = [('order_id', '=', order.id)]
        if delivery_ids:
            domain.append(('delivery_id', 'in', delivery_ids))
        if product_templates:
            domain.append(('product_template_id', 'in', product_templates))

        lines_summary = env['sale.order.line'].read_group(
            domain=domain,
            fields=['product_id', 'product_uom_qty', 'price_total'],
            groupby=['product_id'],
            lazy=False
        )

        lines_data = []
        for l in lines_summary:
            lines_data.append({
                'product_id': l['product_id'][0],
                'product_name': l['product_id'][1],
                'total_qty': l['product_uom_qty'],
                'total_amount': l['price_total'],
            })

        original_lines = [
            {
                "product": l.product_id.display_name,
                "qty": l.product_uom_qty,
                "price": l.price_unit,
                "subtotal": l.price_subtotal,
            }
            for l in order.order_line
        ]

        return {
            'order_id': order.id,
            'customer': order.partner_id.name,
            'total_amount': order.amount_total,
            'summary_lines': lines_data,
            'lines': original_lines,
        }
