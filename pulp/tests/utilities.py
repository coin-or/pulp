import re


def read_command_line_from_log_file(logPath):
    """
    Read from log file the command line executed.
    """
    with open(logPath) as fp:
        for row in fp.readlines():
            if row.startswith("command line "):
                return row
    raise ValueError(f"Unable to find the command line in {logPath}")


def extract_option_from_command_line(
    command_line, option, prefix="-", grp_pattern="[a-zA-Z]+"
):
    """
    Extract option value from command line string.

    :param command_line: str that we extract the option value from
    :param option: str representing the option name (e.g., presolve, sec, etc)
    :param prefix: str (default: '-')
    :param grp_pattern: str (default: '[a-zA-Z]+') - regex to capture option value

    :return: option value captured (str); otherwise, None

    example:

    >>> cmd = "cbc model.mps -presolve off -timeMode elapsed -branch"
    >>> extract_option_from_command_line(cmd, "presolve")
    'off'

    >>> cmd = "cbc model.mps -strong 101 -timeMode elapsed -branch"
    >>> extract_option_from_command_line(cmd, "strong", grp_pattern="\d+")
    '101'
    """
    pattern = re.compile(rf"{prefix}{option}\s+({grp_pattern})\s*")
    m = pattern.search(command_line)
    if not m:
        print(f"{option} not found in {command_line}")
        return None
    option_value = m.groups()[0]
    return option_value
