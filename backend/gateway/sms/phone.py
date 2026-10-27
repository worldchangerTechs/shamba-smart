import re


_KENYAN_MOBILE = re.compile(r"^\+254[17]\d{8}$")


def normalize_kenyan_phone(value):
    if not isinstance(value, str):
        raise ValueError("Enter a Kenyan mobile number, for example 0712 345 678.")

    compact = re.sub(r"[\s().-]", "", value)
    if compact.startswith("+254"):
        normalized = compact
    elif compact.startswith("254"):
        normalized = f"+{compact}"
    elif compact.startswith("0"):
        normalized = f"+254{compact[1:]}"
    elif compact.startswith(("7", "1")):
        normalized = f"+254{compact}"
    else:
        raise ValueError("Enter a Kenyan mobile number, for example 0712 345 678.")

    if not _KENYAN_MOBILE.fullmatch(normalized):
        raise ValueError("Enter a Kenyan mobile number, for example 0712 345 678.")
    return normalized
