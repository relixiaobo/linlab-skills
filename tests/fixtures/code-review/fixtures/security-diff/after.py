def build_headers(request):
    return {"Authorization": request.headers.get("Authorization", "")}


def handle_request(request, logger):
    headers = build_headers(request)
    logger.info("proxy request received", extra={"headers": headers})
    return {"ok": True, "headers": headers}
