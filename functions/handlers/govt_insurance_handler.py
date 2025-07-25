from utils.response_utils import create_success_response, create_error_response
from utils.request_utils import get_request_id
from handlers.insurance_handler import handle_insurance_options

def handle_govt_schemes(req):
    # Dummy data for government schemes
    schemes = [
        {
            "name": "Pradhan Mantri Fasal Bima Yojana (PMFBY)",
            "description": "Crop insurance scheme for farmers to provide financial support in case of crop failure.",
            "eligibility": "All farmers growing notified crops in notified areas.",
            "benefits": "Coverage against crop loss due to natural calamities, pests, and diseases.",
            "apply_url": "https://pmfby.gov.in/"
        },
        {
            "name": "Pradhan Mantri Krishi Sinchai Yojana (PMKSY)",
            "description": "Scheme to improve irrigation and water use efficiency for farmers.",
            "eligibility": "All farmers.",
            "benefits": "Subsidy for micro-irrigation, drip and sprinkler systems.",
            "apply_url": "https://pmksy.gov.in/"
        },
        {
            "name": "Kisan Credit Card (KCC)",
            "description": "Credit support for farmers to meet agricultural and allied expenses.",
            "eligibility": "All farmers.",
            "benefits": "Short-term credit at subsidized interest rates.",
            "apply_url": "https://www.pmkisan.gov.in/"
        }
    ]
    return create_success_response(get_request_id(req), {"schemes": schemes}) 