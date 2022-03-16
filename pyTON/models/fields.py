from pydantic import Field


def create_field_generator(prepend_title: str = None):
    """
    Returns function which calls field generator function with additional
    arguments.

    :param str prepend_title: Text which is automatically prepended
    to passed field title.
    """

    def define_field(title: str = None, **kwargs):
        next_title = ""

        if prepend_title is not None:
            next_title = next_title + prepend_title

        if title is not None:
            next_title = (". " if len(next_title) > 0 else "") + title

        return Field(**kwargs, title=next_title)

    return define_field


"""
List of field generators which are commonly used to describe model properties
according to their types in TL specification.
"""
Int32 = create_field_generator(prepend_title="int32")
Int53 = create_field_generator(prepend_title="int53")
Int64 = create_field_generator(prepend_title="int64")
Bytes = create_field_generator(prepend_title="bytes")
