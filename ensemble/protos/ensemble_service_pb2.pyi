from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class StatusRequest(_message.Message):
    __slots__ = ("member",)
    MEMBER_FIELD_NUMBER: _ClassVar[int]
    member: str
    def __init__(self, member: _Optional[str] = ...) -> None: ...

class ActionRequest(_message.Message):
    __slots__ = ("member", "action", "payload")
    MEMBER_FIELD_NUMBER: _ClassVar[int]
    ACTION_FIELD_NUMBER: _ClassVar[int]
    PAYLOAD_FIELD_NUMBER: _ClassVar[int]
    member: str
    action: str
    payload: str
    def __init__(self, member: _Optional[str] = ..., action: _Optional[str] = ..., payload: _Optional[str] = ...) -> None: ...

class Response(_message.Message):
    __slots__ = ("payload", "status")
    class ResultType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        UNSPECIFIED: _ClassVar[Response.ResultType]
        SUCCESS: _ClassVar[Response.ResultType]
        ERROR: _ClassVar[Response.ResultType]
        DENIED: _ClassVar[Response.ResultType]
        EXISTS: _ClassVar[Response.ResultType]
    UNSPECIFIED: Response.ResultType
    SUCCESS: Response.ResultType
    ERROR: Response.ResultType
    DENIED: Response.ResultType
    EXISTS: Response.ResultType
    PAYLOAD_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    payload: str
    status: Response.ResultType
    def __init__(self, payload: _Optional[str] = ..., status: _Optional[_Union[Response.ResultType, str]] = ...) -> None: ...
