# -*- coding: utf-8 -*-
# Generated by the protocol buffer compiler.  DO NOT EDIT!
# NO CHECKED-IN PROTOBUF GENCODE
# source: ensemble-service.proto
# Protobuf Python Version: 5.28.2
"""Generated protocol buffer code."""
from google.protobuf import descriptor as _descriptor
from google.protobuf import descriptor_pool as _descriptor_pool
from google.protobuf import runtime_version as _runtime_version
from google.protobuf import symbol_database as _symbol_database
from google.protobuf.internal import builder as _builder

_runtime_version.ValidateProtobufRuntimeVersion(
    _runtime_version.Domain.PUBLIC, 5, 28, 2, "", "ensemble-service.proto"
)
# @@protoc_insertion_point(imports)

_sym_db = _symbol_database.Default()


DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(
    b'\n\x16\x65nsemble-service.proto\x12\x1e\x63onvergedcomputing.org.grpc.v1"2\n\rStatusRequest\x12\x0e\n\x06member\x18\x01 \x01(\t\x12\x11\n\talgorithm\x18\x02 \x01(\t"T\n\rUpdateRequest\x12\x0e\n\x06member\x18\x01 \x01(\t\x12\x11\n\talgorithm\x18\x02 \x01(\t\x12\x0f\n\x07options\x18\x03 \x01(\t\x12\x0f\n\x07payload\x18\x04 \x01(\t"S\n\rActionRequest\x12\x0e\n\x06member\x18\x01 \x01(\t\x12\x11\n\talgorithm\x18\x02 \x01(\t\x12\x0e\n\x06\x61\x63tion\x18\x03 \x01(\t\x12\x0f\n\x07payload\x18\x04 \x01(\t"\xaf\x01\n\x08Response\x12\x0f\n\x07payload\x18\x01 \x01(\t\x12\x43\n\x06status\x18\x04 \x01(\x0e\x32\x33.convergedcomputing.org.grpc.v1.Response.ResultType"M\n\nResultType\x12\x0f\n\x0bUNSPECIFIED\x10\x00\x12\x0b\n\x07SUCCESS\x10\x01\x12\t\n\x05\x45RROR\x10\x02\x12\n\n\x06\x44\x45NIED\x10\x03\x12\n\n\x06\x45XISTS\x10\x04\x32\xd0\x02\n\x10\x45nsembleOperator\x12h\n\rRequestUpdate\x12-.convergedcomputing.org.grpc.v1.UpdateRequest\x1a(.convergedcomputing.org.grpc.v1.Response\x12h\n\rRequestStatus\x12-.convergedcomputing.org.grpc.v1.StatusRequest\x1a(.convergedcomputing.org.grpc.v1.Response\x12h\n\rRequestAction\x12-.convergedcomputing.org.grpc.v1.ActionRequest\x1a(.convergedcomputing.org.grpc.v1.ResponseB7Z5github.com/converged-computing/ensemble-python/protosb\x06proto3'
)

_globals = globals()
_builder.BuildMessageAndEnumDescriptors(DESCRIPTOR, _globals)
_builder.BuildTopDescriptorsAndMessages(DESCRIPTOR, "ensemble_service_pb2", _globals)
if not _descriptor._USE_C_DESCRIPTORS:
    _globals["DESCRIPTOR"]._loaded_options = None
    _globals["DESCRIPTOR"]._serialized_options = (
        b"Z5github.com/converged-computing/ensemble-python/protos"
    )
    _globals["_STATUSREQUEST"]._serialized_start = 58
    _globals["_STATUSREQUEST"]._serialized_end = 108
    _globals["_UPDATEREQUEST"]._serialized_start = 110
    _globals["_UPDATEREQUEST"]._serialized_end = 194
    _globals["_ACTIONREQUEST"]._serialized_start = 196
    _globals["_ACTIONREQUEST"]._serialized_end = 279
    _globals["_RESPONSE"]._serialized_start = 282
    _globals["_RESPONSE"]._serialized_end = 457
    _globals["_RESPONSE_RESULTTYPE"]._serialized_start = 380
    _globals["_RESPONSE_RESULTTYPE"]._serialized_end = 457
    _globals["_ENSEMBLEOPERATOR"]._serialized_start = 460
    _globals["_ENSEMBLEOPERATOR"]._serialized_end = 796
# @@protoc_insertion_point(module_scope)
