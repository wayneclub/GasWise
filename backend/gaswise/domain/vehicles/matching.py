"""Vehicle configuration matching shared by selectors and specification adapters."""


def drive_class(value):
    value = value.casefold()
    if "all-wheel" in value or "4-wheel" in value or "4wd" in value or "awd" in value:
        return "awd"
    if "front" in value or "fwd" in value:
        return "fwd"
    if "rear" in value or "rwd" in value:
        return "rwd"
    return None
