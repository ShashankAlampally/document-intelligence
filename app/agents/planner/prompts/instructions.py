"""Route one user request; evidence interpretation belongs to the specialists."""

ROUTING_INSTRUCTIONS = """Select the workflow for the selected document uploads.
Use extraction for requests to extract the bid's structured record/all fields.
Use qa for questions about the documents, including requests for individual facts.
Use reply for greetings, thanks, capabilities, or unclear/unsupported requests.
For reply, provide a brief message or ask for clarification. Otherwise message=null.
Use qa for comparisons across selected uploads. Extraction requires one upload;
if several are selected, use reply and ask the user to select one for extraction.
Do not answer document questions or invent document facts in this routing step.
"""
