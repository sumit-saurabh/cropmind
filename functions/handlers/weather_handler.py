from utils.response_utils import create_error_response, create_success_response
from utils.request_utils import get_request_id

def handle_weather_request(req):
    import requests
    try:
        if req.method == 'GET':
            lat = req.args.get('lat')
            lon = req.args.get('lon')
        else:
            data = req.get_json(force=True, silent=True)
            lat = data.get('lat')
            lon = data.get('lon')
        if not lat or not lon:
            return create_error_response(get_request_id(req), "ER400", "Missing lat/lon", "Latitude and longitude are required.", 400)
        url = f"https://ape.peat-cloud.com/v2/weather?lat={lat}&lon={lon}"
        headers = {
            "Accept-Encoding": "gzip",
            "Accept-Language": "en",
            "api-key": "d0723c386c6590bcbcb75df05f60fce9ba8685db",
            "Connection": "Keep-Alive",
            "Host": "ape.peat-cloud.com",
            "User-Agent": "plantix-production-4.5.1"
        }
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code != 200:
            return create_error_response(get_request_id(req), "ER500", "Weather API error", f"Status: {resp.status_code}, Body: {resp.text}", 500)
        return create_success_response(get_request_id(req), resp.json())
    except Exception as e:
        import traceback
        return create_error_response(get_request_id(req), "ER500", "Internal server error", str(e) + "\n" + traceback.format_exc(), 500) 