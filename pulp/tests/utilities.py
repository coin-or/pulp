import re


def read_command_line_from_log_file(logPath: str) -> str:
    """
    Read from log file the command line executed.
    """
    with open(logPath) as fp:
        for row in fp.readlines():
            if row.startswith("command line "):
                return row
    raise ValueError(f"Unable to find the command line in {logPath}")


def extract_option_from_command_line(
    command_line: str, option: str, prefix: str = "-", grp_pattern: str = "[a-zA-Z]+"
) -> str:
    pattern = re.compile(rf"{prefix}{option}\s+({grp_pattern})\s*")
    m = pattern.search(command_line)
    if not m:
        print(f"{option} not found in {command_line}")
        return None
    option_value = m.groups()[0]
    return option_value
