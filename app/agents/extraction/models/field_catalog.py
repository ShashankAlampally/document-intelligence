"""Assignment fields grouped into small, reusable extraction tasks."""

from typing import Literal

FieldName = Literal[
    "Bid Number",
    "Title",
    "Due Date",
    "Bid Submission Type",
    "Term of Bid",
    "Pre Bid Meeting",
    "Installation",
    "Bid Bond Requirement",
    "Delivery Date",
    "Payment Terms",
    "Any Additional Documentation Required",
    "MFG for Registration",
    "Contract or Cooperative to use",
    "Model_no",
    "Part_no",
    "Product",
    "contact_info",
    "company_name",
    "Bid Summary",
    "Product Specification",
]

FIELD_GROUPS = {
    "bid_details": ["Bid Number", "Title", "Due Date"],
    "contract_requirements": ["Bid Submission Type", "Term of Bid", "Pre Bid Meeting"],
    "deployment_and_security": ["Installation", "Bid Bond Requirement", "Delivery Date"],
    "delivery_and_documents": [
        "Payment Terms",
        "Any Additional Documentation Required",
        "MFG for Registration",
    ],
    "products": ["Contract or Cooperative to use", "Model_no", "Part_no"],
    "contacts_and_products": ["Product", "contact_info", "company_name"],
    "summary_and_specs": ["Bid Summary", "Product Specification"],
}
FIELD_NAMES = [name for names in FIELD_GROUPS.values() for name in names]

FIELD_GUIDANCE = {
    "Bid Number": "Official solicitation / RFP identifier.",
    "Title": "Full title of the bid or RFP.",
    "Due Date": (
        "Submission deadline with stated time zone. An explicitly revised deadline in the latest "
        "numbered addendum overrides a differing portal listing: use its stated deadline verbatim "
        "and describe the portal discrepancy in notes. Do not leave it unresolved merely because "
        "the portal shows another time."
    ),
    "Bid Submission Type": "Submission method: portal, sealed paper, email, etc.",
    "Term of Bid": "Contract duration and renewal options.",
    "Pre Bid Meeting": "Meeting date, time, location, mandatory attendance; None only if explicit.",
    "Installation": "Required installation, deployment or imaging services.",
    "Bid Bond Requirement": "Required security amount/percentage; Not required only if explicit.",
    "Delivery Date": "Delivery date, relative window or schedule; not submission date.",
    "Payment Terms": (
        "Payment deadlines and invoicing conditions. Name the payer AND recipient for each rule. "
        "Separate district-to-vendor terms from prime-to-subcontractor/supplier terms. "
        "If only subcontractor terms are supported, label them explicitly and say direct "
        "district-to-vendor terms are not established; do not substitute one for the other."
    ),
    "Any Additional Documentation Required": (
        "List every supported required document, form, signed addendum, reference, catalog, "
        "insurance form or certificate. Include submission timing and exceptions when supported. "
        "Do not stop after the first two documents; explicitly describe incomplete evidence."
    ),
    "MFG for Registration": (
        "Name the manufacturer(s) requiring registration/authorized reseller status, e.g. Dell. "
        "A Letter of Authorization is a document, not a manufacturer. "
        "Use null if no manufacturer name is supported."
    ),
    "Contract or Cooperative to use": "Referenced state contract or cooperative vehicle.",
    "Model_no": "Requested product model numbers; distinguish them from part/SKU numbers.",
    "Part_no": "Requested part/SKU numbers; do not invent them from model numbers.",
    "Product": "Product names and associated quantities.",
    "contact_info": "Procurement contact name, email and phone when stated.",
    "company_name": "Issuing organization or agency, not the vendor or manufacturer.",
    "Bid Summary": "Write 3–6 sentences summarizing only supported facts, citing all used sources.",
    "Product Specification": "Technical requirements: CPU, RAM, storage, display, warranty, etc.",
}
