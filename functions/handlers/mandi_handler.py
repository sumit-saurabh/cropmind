import math
from firebase_admin import firestore
from collections import OrderedDict
from utils.response_utils import get_request_id, ordered_json_response
from utils.request_utils import get_field

# Business logic functions only, no Flask route registration

def haversine(lat1, lng1, lat2, lng2):
    R = 6371
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

def find_nearby_mandis(lat, lng, limit=3):
    db = firestore.client()
    mandis = db.collection('mandis').stream()
    mandi_list = []
    for doc in mandis:
        data = doc.to_dict()
        dist = haversine(lat, lng, data['lat'], data['lng'])
        mandi_list.append({**data, 'distance_km': dist})
    mandi_list.sort(key=lambda x: x['distance_km'])
    return mandi_list[:limit]

def find_crop_in_mandis(mandis, crop_slug, language='en'):
    results = []
    for mandi in mandis:
        for crop in mandi.get('crops', []):
            if crop['slug'] == crop_slug:
                crop_name = crop['name']
                if language in crop.get('translations', {}):
                    crop_name = crop['translations'][language]
                results.append({
                    'mandi_id': mandi['mandi_id'],
                    'mandi_name': mandi['mandi_name'],
                    'distance_km': mandi['distance_km'],
                    'address': mandi.get('address', ''),
                    'open_time': mandi.get('open_time', ''),
                    'mobile': mandi.get('mobile', ''),
                    'crop': crop_name,
                    **crop
                })
    return results

def get_crop_trend(mandi_id, crop_slug):
    db = firestore.client()
    doc = db.collection('mandis').document(str(mandi_id)).get()
    if not doc.exists:
        return None
    mandi = doc.to_dict()
    for crop in mandi.get('crops', []):
        if crop['slug'] == crop_slug:
            return {
                'mandi_id': mandi_id,
                'mandi_name': mandi['mandi_name'],
                'crop': crop['name'],
                'price_history': crop.get('price_history', []),
                'trend': crop.get('trend', ''),
                'predicted_price': crop.get('predicted_price', None)
            }
    return None

def get_mandi_details(mandi_id):
    db = firestore.client()
    doc = db.collection('mandis').document(str(mandi_id)).get()
    if not doc.exists:
        return None
    return doc.to_dict()

def search_mandis(pincode=None, name=None, limit=10, language='en'):
    db = firestore.client()
    query = db.collection('mandis')
    results = []
    # Search by pincode (exact match)
    if pincode:
        query = query.where('pincode', '==', str(pincode))
        docs = query.stream()
        for doc in docs:
            data = doc.to_dict()
            for c in data.get('crops', []):
                if language in c.get('translations', {}):
                    c['name'] = c['translations'][language]
            results.append(data)
    # Search by name (case-insensitive, partial match)
    elif name:
        docs = query.stream()
        name_lower = name.lower()
        for doc in docs:
            data = doc.to_dict()
            if name_lower in data.get('mandi_name', '').lower():
                for c in data.get('crops', []):
                    if language in c.get('translations', {}):
                        c['name'] = c['translations'][language]
                results.append(data)
            if len(results) >= limit:
                break
    return results[:limit]

# Handler functions for both Flask and Google Cloud Functions

def handle_mandi_nearby(req):
    request_id = get_request_id(req)
    user_id = get_field('user_id')
    try:
        lat = float(get_field('lat'))
        lng = float(get_field('lng'))
        limit = int(get_field('limit') or 3)
        language = get_field('language') or 'en'
        mandis = find_nearby_mandis(lat, lng, limit=limit)
        result = [
            OrderedDict([
                ('mandi_id', m['mandi_id']),
                ('mandi_name', m['mandi_name']),
                ('distance_km', m['distance_km']),
                ('address', m.get('address', '')),
                ('open_time', m.get('open_time', '')),
                ('mobile', m.get('mobile', '')),
                ('city', m.get('city', '')),
                ('state', m.get('state', '')),
                ('lat', m.get('lat')),
                ('lng', m.get('lng')),
                ('crops', [c['translations'].get(language, c['name']) if 'translations' in c else c['name'] for c in m.get('crops', [])])
            ])
            for m in mandis
        ]
        resp = OrderedDict([
            ("status", "success"),
            ("requestId", request_id),
            ("data", OrderedDict([
                ("user_id", user_id),
                ("mandis", result),
                ("language", language)
            ]))
        ])
        return ordered_json_response(resp)
    except Exception as e:
        err = OrderedDict([
            ("status", "error"),
            ("requestId", request_id),
            ("error", OrderedDict([
                ("code", "ER500"),
                ("message", "Internal server error"),
                ("description", str(e))
            ]))
        ])
        return ordered_json_response(err, status=500)

def handle_mandi_crop_price(req):
    request_id = get_request_id(req)
    user_id = get_field('user_id')
    try:
        lat = float(get_field('lat'))
        lng = float(get_field('lng'))
        crop = get_field('crop')
        limit = int(get_field('limit') or 3)
        language = get_field('language') or 'en'
        mandis = find_nearby_mandis(lat, lng, limit=limit)
        results = find_crop_in_mandis(mandis, crop, language)
        resp = OrderedDict([
            ("status", "success"),
            ("requestId", request_id),
            ("data", OrderedDict([
                ("user_id", user_id),
                ("mandis", results),
                ("language", language)
            ]))
        ])
        return ordered_json_response(resp)
    except Exception as e:
        err = OrderedDict([
            ("status", "error"),
            ("requestId", request_id),
            ("error", OrderedDict([
                ("code", "ER500"),
                ("message", "Internal server error"),
                ("description", str(e))
            ]))
        ])
        return ordered_json_response(err, status=500)

def handle_mandi_crop_trend(req):
    request_id = get_request_id(req)
    user_id = get_field('user_id')
    try:
        mandi_id = get_field('mandi_id')
        crop = get_field('crop')
        language = get_field('language') or 'en'
        trend = get_crop_trend(mandi_id, crop)
        if not trend:
            err = OrderedDict([
                ("status", "error"),
                ("requestId", request_id),
                ("error", OrderedDict([
                    ("code", "ER404"),
                    ("message", "Not found"),
                    ("description", f"No trend data for mandi_id={mandi_id}, crop={crop}")
                ]))
            ])
            return ordered_json_response(err, status=404)
        # Localize crop name
        if 'crop' in trend and language != 'en':
            mandi = get_mandi_details(mandi_id)
            if mandi:
                for c in mandi.get('crops', []):
                    if c['slug'] == crop and language in c.get('translations', {}):
                        trend['crop'] = c['translations'][language]
        resp = OrderedDict([
            ("status", "success"),
            ("requestId", request_id),
            ("data", OrderedDict([
                ("user_id", user_id),
                *trend.items()
            ]))
        ])
        return ordered_json_response(resp)
    except Exception as e:
        err = OrderedDict([
            ("status", "error"),
            ("requestId", request_id),
            ("error", OrderedDict([
                ("code", "ER500"),
                ("message", "Internal server error"),
                ("description", str(e))
            ]))
        ])
        return ordered_json_response(err, status=500)

def handle_mandi_details(req):
    request_id = get_request_id(req)
    user_id = get_field('user_id')
    try:
        mandi_id = get_field('mandi_id')
        language = get_field('language') or 'en'
        details = get_mandi_details(mandi_id)
        if not details:
            err = OrderedDict([
                ("status", "error"),
                ("requestId", request_id),
                ("error", OrderedDict([
                    ("code", "ER404"),
                    ("message", "Not found"),
                    ("description", f"No mandi found for mandi_id={mandi_id}")
                ]))
            ])
            return ordered_json_response(err, status=404)
        # Localize crop names
        for c in details.get('crops', []):
            if language in c.get('translations', {}):
                c['name'] = c['translations'][language]
        resp = OrderedDict([
            ("status", "success"),
            ("requestId", request_id),
            ("data", OrderedDict([
                ("user_id", user_id),
                *details.items()
            ]))
        ])
        return ordered_json_response(resp)
    except Exception as e:
        err = OrderedDict([
            ("status", "error"),
            ("requestId", request_id),
            ("error", OrderedDict([
                ("code", "ER500"),
                ("message", "Internal server error"),
                ("description", str(e))
            ]))
        ])
        return ordered_json_response(err, status=500)

def handle_mandi_search(req):
    request_id = get_request_id(req)
    user_id = get_field('user_id')
    try:
        pincode = get_field('pincode')
        name = get_field('name')
        limit = int(get_field('limit') or 10)
        language = get_field('language') or 'en'
        if not pincode and not name:
            err = OrderedDict([
                ("status", "error"),
                ("requestId", request_id),
                ("error", OrderedDict([
                    ("code", "ER400"),
                    ("message", "Missing search parameter"),
                    ("description", "Provide either pincode or name for search")
                ]))
            ])
            return ordered_json_response(err, status=400)
        results = search_mandis(pincode=pincode, name=name, limit=limit, language=language)
        resp = OrderedDict([
            ("status", "success"),
            ("requestId", request_id),
            ("data", OrderedDict([
                ("user_id", user_id),
                ("mandis", results),
                ("language", language)
            ]))
        ])
        return ordered_json_response(resp)
    except Exception as e:
        err = OrderedDict([
            ("status", "error"),
            ("requestId", request_id),
            ("error", OrderedDict([
                ("code", "ER500"),
                ("message", "Internal server error"),
                ("description", str(e))
            ]))
        ])
        return ordered_json_response(err, status=500)

