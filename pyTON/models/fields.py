from pydantic import Field


def create_field_generator(prepend_description: str = None):
    """
    Returns function which calls field generator function with additional
    arguments.

    :param str prepend_description: Text which is automatically prepended
    to passed field description
    """

    def define_field(description: str = None, **kwargs):
        formatted_description = ("" if prepend_description is None else (prepend_description + " ")) \
                                + "" if description is None else description

        return Field(**kwargs, description=formatted_description)

    return define_field


"""
List of field generators which are commonly used to describe model properties
according to their types in TL specification.
"""
Int32 = create_field_generator(prepend_description="(tl: int32)")
Int53 = create_field_generator(prepend_description="(tl: int53)")
Int64 = create_field_generator(prepend_description="(tl: int64)")
Bytes = create_field_generator(prepend_description="(tl: bytes)")
