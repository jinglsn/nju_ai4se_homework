import keyring

DEFAULT_SERVICE = "harness-llm"


def set_api_key(service: str = DEFAULT_SERVICE, key: str | None = None) -> None:
    if key is None:
        import getpass
        key = getpass.getpass("Enter API key: ")
    keyring.set_password(service, "api_key", key)


def get_api_key(service: str = DEFAULT_SERVICE) -> str | None:
    return keyring.get_password(service, "api_key")


def clear_api_key(service: str = DEFAULT_SERVICE) -> None:
    try:
        keyring.delete_password(service, "api_key")
    except keyring.errors.PasswordDeleteError:
        pass


def key_status(service: str = DEFAULT_SERVICE) -> str:
    key = get_api_key(service)
    return "configured" if key else "not configured"