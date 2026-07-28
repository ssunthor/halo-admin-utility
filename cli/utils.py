import os
import sys
import click
import grpc

class MetadataClientInterceptor(grpc.UnaryUnaryClientInterceptor, grpc.UnaryStreamClientInterceptor):
    def __init__(self, key, value):
        self._key = key
        self._value = value

    def _amend(self, details):
        metadata = list(details.metadata) if details.metadata else []
        metadata.append((self._key, self._value))
        
        class _ClientCallDetails(grpc.ClientCallDetails):
            def __init__(self, method, timeout, metadata, credentials, wait_for_ready):
                self.method = method
                self.timeout = timeout
                self.metadata = metadata
                self.credentials = credentials
                self.wait_for_ready = wait_for_ready
        
        return _ClientCallDetails(
            details.method, details.timeout, tuple(metadata), details.credentials, getattr(details, 'wait_for_ready', None)
        )

    def intercept_unary_unary(self, continuation, client_call_details, request):
        return continuation(self._amend(client_call_details), request)

    def intercept_unary_stream(self, continuation, client_call_details, request):
        return continuation(self._amend(client_call_details), request)

def ensure_stubs_path_in_sys(config):
    try:
        stubs_path = config['paths']['generated_stubs_path']
        stubs_parent = os.path.abspath(os.path.join(stubs_path, '..', '..', '..'))
        if stubs_parent not in sys.path:
            sys.path.insert(0, stubs_parent)
        if stubs_path not in sys.path:
            sys.path.insert(0, stubs_path)
    except KeyError:
        pass

def get_hau_stub(config):
    """Retrieve the HAU gRPC stub."""
    ensure_stubs_path_in_sys(config)
    import hau_pb2_grpc
    
    host = config['system_services']['grpc']['host']
    port = config['system_services']['grpc']['port']
    acronym = config['module_info']['acronym']
    
    channel = grpc.insecure_channel(f"{host}:{port}")
    interceptor = MetadataClientInterceptor('x-client-id', acronym)
    channel = grpc.intercept_channel(channel, interceptor)
    
    return hau_pb2_grpc.HauServiceStub(channel)

def get_sera_stub(config):
    """Retrieve the SERA gRPC stub."""
    ensure_stubs_path_in_sys(config)
    import sera_standard_pb2_grpc
    
    host = config['system_services']['grpc']['host']
    port = config['system_services']['grpc']['port']
    acronym = config['module_info']['acronym']
    
    channel = grpc.insecure_channel(f"{host}:{port}")
    interceptor = MetadataClientInterceptor('x-client-id', acronym)
    channel = grpc.intercept_channel(channel, interceptor)
    
    return sera_standard_pb2_grpc.SeraAppServiceStub(channel)


def print_grpc_json(response):
    """Standardized method to dump raw gRPC JSON"""
    from google.protobuf.json_format import MessageToDict
    import click
    import json
    
    resp_dict = MessageToDict(response, preserving_proto_field_name=True)
    
    # Attempt to extract and print only the inner JSON payload like OMU
    if 'result_json' in resp_dict and isinstance(resp_dict['result_json'], str):
        try:
            parsed = json.loads(resp_dict['result_json'])
            click.echo(json.dumps(parsed, indent=2))
            return
        except json.JSONDecodeError:
            pass
            
    if 'manifests' in resp_dict and isinstance(resp_dict['manifests'], list):
        for m in resp_dict['manifests']:
            if 'live_state_json' in m and isinstance(m['live_state_json'], str):
                try:
                    m['live_state_json'] = json.loads(m['live_state_json'])
                except json.JSONDecodeError:
                    pass
            
    click.echo(json.dumps(resp_dict, indent=2))

def handle_grpc_errors(func):
    """Decorator to catch and beautifully format gRPC errors"""
    import functools
    import grpc
    import click
    import sys
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except grpc.RpcError as e:
            click.secho(f"gRPC Error [{e.code().name}]: {e.details()}", fg="red", err=True)
            sys.exit(1)
    return wrapper
