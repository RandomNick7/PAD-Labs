# -*- coding: utf-8 -*-
# Generated by the protocol buffer compiler.  DO NOT EDIT!
# NO CHECKED-IN PROTOBUF GENCODE
# source: user_routes.proto
# Protobuf Python Version: 5.27.2
"""Generated protocol buffer code."""
from google.protobuf import descriptor as _descriptor
from google.protobuf import descriptor_pool as _descriptor_pool
from google.protobuf import runtime_version as _runtime_version
from google.protobuf import symbol_database as _symbol_database
from google.protobuf.internal import builder as _builder
_runtime_version.ValidateProtobufRuntimeVersion(
    _runtime_version.Domain.PUBLIC,
    5,
    27,
    2,
    '',
    'user_routes.proto'
)
# @@protoc_insertion_point(imports)

_sym_db = _symbol_database.Default()




DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(b'\n\x11user_routes.proto\x12\x0buser_routes\"E\n\x0b\x43redentials\x12\x10\n\x08username\x18\x01 \x01(\t\x12\x10\n\x08password\x18\x02 \x01(\t\x12\x12\n\nnewAccount\x18\x03 \x01(\x08\"-\n\x0cLoginConfirm\x12\x0e\n\x06status\x18\x01 \x01(\x05\x12\r\n\x05token\x18\x02 \x01(\t2O\n\nUserRoutes\x12\x41\n\x08tryLogin\x12\x18.user_routes.Credentials\x1a\x19.user_routes.LoginConfirm\"\x00\x62\x06proto3')

_globals = globals()
_builder.BuildMessageAndEnumDescriptors(DESCRIPTOR, _globals)
_builder.BuildTopDescriptorsAndMessages(DESCRIPTOR, 'user_routes_pb2', _globals)
if not _descriptor._USE_C_DESCRIPTORS:
  DESCRIPTOR._loaded_options = None
  _globals['_CREDENTIALS']._serialized_start=34
  _globals['_CREDENTIALS']._serialized_end=103
  _globals['_LOGINCONFIRM']._serialized_start=105
  _globals['_LOGINCONFIRM']._serialized_end=150
  _globals['_USERROUTES']._serialized_start=152
  _globals['_USERROUTES']._serialized_end=231
# @@protoc_insertion_point(module_scope)
