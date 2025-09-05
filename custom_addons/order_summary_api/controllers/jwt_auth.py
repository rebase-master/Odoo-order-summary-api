import logging

import jwt
import datetime
from odoo import http, _
from odoo.http import request
from odoo.exceptions import AccessDenied

SECRET_KEY = "super_secret_jwt_key"  # 🔐 move this to Odoo config in production
_logger = logging.getLogger(__name__)

class JwtAuthController(http.Controller):

    @http.route('/api/v1/auth', type='json', auth='none', methods=['POST'], csrf=False)
    def authenticate(self, **kwargs):
        data = request.get_json_data()
        params = data.get("params", {})

        _logger.info(">>> received params: %s", params)
        login = params.get("login")
        password = params.get("password")
        db = params.get("db")
        credential = {'login': login, 'password': password, 'type': 'password'}

        if not all([db, login, password]):
            return {"error": "db, login, password are required"}

        try:
            uid = request.session.authenticate(db, credential)
        except AccessDenied:
            return {"error": "Invalid credentials"}

        payload = {
            "uid": uid["uid"] if isinstance(uid, dict) else uid,
            "login": login,
            "db": db,
            "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=2)
        }
        token = jwt.encode(payload, SECRET_KEY, algorithm="HS256")

        return {"token": token}
