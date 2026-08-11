from re import sub
from textwrap import dedent

########################################################################################


def camel_to_kebab(s: str) -> str:
    return snake_to_kebab(s=camel_to_snake(s))


def camel_to_snake(s: str) -> str:
    new = sub(
        pattern=r"(.)([A-Z][a-z]+)",
        repl=r"\1_\2",
        string=s,
    )

    return sub(
        pattern=r"([a-z0-9])([A-Z])",
        repl=r"\1_\2",
        string=new,
    ).lower()


def snake_to_kebab(s: str) -> str:
    return s.replace("_", "-")


########################################################################################


def dotted_join(*crumbs: int | str) -> str:
    return ".".join(str(p) for p in crumbs)


########################################################################################


def normalize_trigger(sql: str) -> str:
    return " ".join(dedent(text=sql).strip().split())
