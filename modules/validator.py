import typing

Ts = typing.Union[str, int, tuple[typing.Union[str, int], ...]]

def __validate(src: dict, key: str, value: Ts):
    key: list[str] = key.split("::")
    for k in key[:-1]:
        if k not in src or not isinstance(src[k], dict):
            return False
        src = src[k]
    if key[-1] not in src:
        return False
    if isinstance(value, tuple):
        return src[key[-1]] in value
    else:
        return src[key[-1]] == value

def validate(src: dict, kv: dict[str, Ts]):
    for k, v in kv.items():
        if not __validate(src, k, v):
            return False
    return True