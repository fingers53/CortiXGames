
def read_html(file_name: str) -> str:
    with open(os.path.join("templates", file_name), "r", encoding="utf-8") as f:
        return f.read()

def render_template(
    file_name: str, request: Request, context: Optional[dict] = None
) -> HTMLResponse:
    session_id, csrf_token, new_cookie = ensure_session_tokens(request)
    base_context = {
        "request": request,
        "csrf_token": csrf_token,
    }
    if context:
        base_context.update(context)

    response = templates.TemplateResponse(file_name, base_context)
    if new_cookie:
        response.set_cookie("session_id", session_id, httponly=True, samesite="lax")
    return response
