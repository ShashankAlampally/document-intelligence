"""One focused document search per assignment field; no extra model calls."""

FIELD_SEARCH_QUERIES = {
    "Bid Number": "What is the solicitation number or RFP bid identifier?",
    "Title": "What is the title of the solicitation or request for proposals?",
    "Due Date": (
        "What is the submission closing date, time and timezone, including deadline extensions?"
    ),
    "Bid Submission Type": (
        "How must proposals be submitted: online portal or sealed paper delivery?"
    ),
    "Term of Bid": "What is the initial contract duration and the renewal or extension period?",
    "Pre Bid Meeting": (
        "When and where is the pre-proposal conference, and is attendance mandatory?"
    ),
    "Installation": (
        "What installation, deployment, imaging or device enrollment services are required?"
    ),
    "Bid Bond Requirement": (
        "Is a bid bond or bid security required, and what is its amount or percentage?"
    ),
    "Delivery Date": "What delivery deadline, lead time or delivery scheduling requirements apply?",
    "Payment Terms": "What are the payment terms, invoice requirements and payment deadlines?",
    "Any Additional Documentation Required": (
        "What supporting documents must be submitted: signed addenda, affidavits, insurance, "
        "W-9, Form 1295, references or certificates?"
    ),
    "MFG for Registration": (
        "Which manufacturers require bidder registration or authorized reseller status?"
    ),
    "Contract or Cooperative to use": (
        "Which purchasing cooperative or master contract is referenced?"
    ),
    "Model_no": "What device product model names or model numbers are requested?",
    "Part_no": "What manufacturer part numbers or product SKUs are requested?",
    "Product": "Target Quantity product items quantities",
    "contact_info": "Contact Information Procurement Services",
    "company_name": "Which organization or agency is issuing this solicitation?",
    "Bid Summary": (
        "Purpose of request for proposal: requested products, services, "
        "categories and contract duration"
    ),
    "Product Specification": (
        "What are the technical specifications for each device category: processor, memory RAM, "
        "storage, display and warranty?"
    ),
}


def field_search_queries(names: list[str]) -> list[str]:
    return [FIELD_SEARCH_QUERIES[name] for name in names]
