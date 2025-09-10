import json

def format_update(text: str):
    update = {}
    update["status"] = "UPDATE"
    update["message"] = text
    return f"data: {json.dumps(update)}\n\n"

def format_result(result: dict):
    result["status"] = "DONE"
    return f"data: {json.dumps(result)}\n\n"

def format_error(message: str):
    error = {}
    error["status"] = "ERROR"
    error["message"] = message
    return f"data: {json.dumps(error)}\n\n"