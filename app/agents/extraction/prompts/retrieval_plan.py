"""Extra local searches for fields whose answers span several topics."""

from app.agents.extraction.prompts.search_queries import FIELD_SEARCH_QUERIES

BROAD_QUERIES = {
    "contact_info": [
        "Contact Information Procurement Services",
        "Named procurement buyer contact name email phone for this solicitation",
    ],
    "Product": [
        "Target quantities for student laptops Chromebooks and tablets",
        "Target quantities for staff laptops and desktop computers",
        "Target quantities for touch and non-touch display monitors",
    ],
    "Product Specification": [
        "Chromebook minimum requirements processor memory storage display warranty",
        "Student Windows laptop minimum requirements processor memory storage warranty",
        "Student tablet minimum requirements processor storage operating system warranty",
        "Staff laptop tiers minimum requirements processor memory storage warranty",
        "Staff desktop tiers minimum requirements processor memory storage video card warranty",
        "Touch and non-touch display monitor minimum requirements resolution warranty",
    ],
    "Any Additional Documentation Required": [
        "Required Form 1295 certificate of interested parties submission",
        "Required signed addendum acknowledgement return with proposal",
        "Required business references contact details with proposal",
        "Required catalog price list submission",
        "Required insurance form certificate and submission timing",
        "Required factory authorized repair maintenance certifications for resellers",
    ],
}


TOPIC_TERMS = {
    "contact_info": [[], ["buyer"]],
    "Any Additional Documentation Required": [
        ["1295"],
        ["addendum"],
        ["references"],
        ["catalog"],
        ["insurance"],
        ["certifications"],
    ],
    "Product": [["student"], ["staff"], ["monitor"]],
    "Product Specification": [
        ["chromebook"],
        ["student", "windows"],
        ["tablet"],
        ["staff", "laptop"],
        ["staff", "desktop"],
        ["monitor"],
    ],
}


def retrieval_plan(names, top_k=5):
    requests = []
    for name in names:
        queries = BROAD_QUERIES.get(name, [FIELD_SEARCH_QUERIES[name]])
        for index, query in enumerate(queries):
            request = {"query": query, "top_k": top_k, "field_name": name}
            if name in TOPIC_TERMS:
                request["required_terms"] = TOPIC_TERMS[name][index]
            requests.append(request)
    return requests
