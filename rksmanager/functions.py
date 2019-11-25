"""General-purpose utility functions."""


def get_nested_attr(obj, name_string):
    """
    Get the value of an object attribute given in dot notation.

    Args:
        obj: The top-level object.
        name_string: One or more attributes separated by dots, such as
        "child_object.grandchild_object.grandchild_attribute".

    Returns:
        The value of the final attribute in name_string.

    """
    names = name_string.split(".")
    for name in names:
        obj = getattr(obj, name)
    return obj
