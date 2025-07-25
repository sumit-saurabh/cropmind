from utils.response_utils import create_success_response, create_error_response
from utils.request_utils import get_request_id

def handle_insurance_options(req):
    # Dummy data for insurance options (Zuno General Insurance)
    insurance_options = [
        {
            "provider": "Zuno General Insurance",
            "product": "Zuno Crop Insurance",
            "description": "Comprehensive crop insurance for farmers covering natural calamities, pests, and diseases.",
            "sum_insured": "Up to ₹2,00,000 per acre",
            "premium": "Starting at ₹150 per acre",
            "contact": "1800-123-4003",
            "website": "https://www.hizuno.com/miscellaneous-insurance"
        },
        {
            "provider": "Zuno General Insurance",
            "product": "Zuno Livestock Insurance",
            "description": "Insurance for cattle and livestock against death due to accident, disease, or natural calamities.",
            "sum_insured": "Up to ₹50,000 per animal",
            "premium": "Starting at ₹100 per animal",
            "contact": "1800-123-4003",
            "website": "https://www.hizuno.com/miscellaneous-insurance"
        }
    ]
    return create_success_response(get_request_id(req), {"insurance_options": insurance_options}) 