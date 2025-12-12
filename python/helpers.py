from typing import List

__all__ = [
    "snake_to_pascal_case", "format_list"
]


def snake_to_pascal_case(name: str):
    return "".join([word[0].upper() + word[1:] for word in name.split("_")])


def format_list(items: List[str], max_text_width) -> str:
    lines = [""]
    current_line = 0
    for item in items:
        can_fit = (len(lines[current_line]) + len(item) + 2) <= max_text_width
        if not can_fit:
            lines[current_line] = lines[current_line].rstrip(" ")
            current_line += 1
            lines.append("")
        lines[current_line] += item + ", "

    return "\n".join(lines).rstrip(", ")
