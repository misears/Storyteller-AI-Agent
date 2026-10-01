import ipaddress


def is_loopback_host(host: str) -> bool:
    if host.lower() == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def validate_public_narration(text: str, secrets: list[str]) -> None:
    lowered = text.casefold()
    leaked = [secret for secret in secrets if secret and secret.casefold() in lowered]
    if leaked:
        raise ValueError("public narration contains protected secret content")