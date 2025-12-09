import requests

def get_country_code_from_ip(client_ip: str | None) -> str:
    """
    Map IP -> ISO country code (e.g. 'IE', 'GB').
    We do NOT store the IP anywhere, just use it transiently.
    """
    if not client_ip:
        return "??"

    try:
        # Example using ipapi.co – swap if you prefer another service
        resp = requests.get(f"https://ipapi.co/{client_ip}/json/", timeout=1.5)
        if resp.status_code != 200:
            return "??"
        data = resp.json()
        code = data.get("country")  # 'IE', 'GB', 'ES', ...
        if code and len(code) == 2:
            return code
    except Exception:
        pass

    return "??"