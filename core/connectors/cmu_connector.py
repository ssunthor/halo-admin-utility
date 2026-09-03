import logging
import grpc
import sys
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

_channel = None
_stub = None
_cmu_pb2 = None
_cmu_pb2_grpc = None

MAX_MESSAGE_LENGTH = 50 * 1024 * 1024

def init_cmu_connector(config: Dict[str, Any]):
    global _channel, _stub, _cmu_pb2, _cmu_pb2_grpc
    if _channel:
        return

    generated_path = config.get("paths", {}).get("cmu_generated_stubs_path")
    if not generated_path:
        logger.error("cmu_generated_stubs_path must be configured in settings.yaml paths section")
        return
        
    if generated_path not in sys.path:
        sys.path.insert(0, generated_path)

    try:
        import cmu_pb2
        import cmu_pb2_grpc
        _cmu_pb2 = cmu_pb2
        _cmu_pb2_grpc = cmu_pb2_grpc
    except ImportError as e:
        logger.critical(f"Failed to import CMU gRPC stubs. Ensure they are generated: {e}", exc_info=True)
        return

    try:
        cmu_config = config.get("connectors", {}).get("cmu", {})
        host = cmu_config.get("host")
        port = cmu_config.get("port")
        if not host or not port:
            raise ValueError("CMU host or port not found in configuration.")
        cmu_endpoint = f"{host}:{port}"

        channel_options = [
            ('grpc.max_receive_message_length', MAX_MESSAGE_LENGTH),
            ('grpc.max_send_message_length', MAX_MESSAGE_LENGTH),
        ]
        _channel = grpc.insecure_channel(cmu_endpoint, options=channel_options)
        _stub = _cmu_pb2_grpc.CmuServiceStub(_channel)
        logger.info(f"CMU connector initialized. Connecting to {cmu_endpoint}")
    except Exception as e:
        logger.error(f"Failed to initialize CMU connector: {e}", exc_info=True)
        _channel = None
        _stub = None

def create_identity(app_name: str, environment: str, description: str = "", requestor: str = "HAU") -> Dict[str, Any]:
    if not _stub:
        logger.warning("CMU connector not initialized. Cannot create identity.")
        return {"success": False, "error_message": "Connector not initialized"}
        
    try:
        request = _cmu_pb2.IdentityCreateRequest(
            app_name=app_name, 
            environment=environment, 
            description=description, 
            requestor=requestor
        )
        response = _stub.IdentityCreate(request, timeout=60, metadata=(('x-client-id', 'HAU'),))
        
        if response.success:
            return {"success": True, "result_json": response.result_json}
        else:
            return {"success": False, "error_message": getattr(response, 'message', 'Unknown Error')}
    except grpc.RpcError as e:
        err_msg = f"gRPC Error: {e.code().name} - {e.details()}"
        logger.error(f"gRPC Error calling CMU IdentityCreate: {err_msg}")
        return {"success": False, "error_message": err_msg}
    except Exception as e:
        logger.error(f"Error calling CMU IdentityCreate: {e}", exc_info=True)
        return {"success": False, "error_message": str(e)}

def write_to_vault(path: str, kv_pairs: Dict[str, str]) -> Dict[str, Any]:
    if not _stub:
        logger.warning("CMU connector not initialized. Cannot write to vault.")
        return {"success": False, "error_message": "Connector not initialized"}
        
    try:
        request = _cmu_pb2.VaultWriteRequest(path=path, kv_pairs=kv_pairs)
        response = _stub.VaultWrite(request, timeout=30, metadata=(('x-client-id', 'HAU'),))
        
        if response.success:
            return {"success": True, "message": getattr(response, 'message', 'Success')}
        else:
            return {"success": False, "error_message": getattr(response, 'message', 'Unknown Error')}
    except grpc.RpcError as e:
        err_msg = f"gRPC Error: {e.code().name} - {e.details()}"
        logger.error(f"gRPC Error calling CMU VaultWrite: {err_msg}")
        return {"success": False, "error_message": err_msg}
    except Exception as e:
        logger.error(f"Error calling CMU VaultWrite: {e}", exc_info=True)
        return {"success": False, "error_message": str(e)}

def delete_identity(client_id: str) -> Dict[str, Any]:
    if not _stub:
        logger.warning("CMU connector not initialized. Cannot delete identity.")
        return {"success": False, "error_message": "Connector not initialized"}
        
    try:
        request = _cmu_pb2.IdentityDeleteRequest(client_id=client_id)
        response = _stub.IdentityDelete(request, timeout=60, metadata=(('x-client-id', 'HAU'),))
        
        if response.success:
            return {"success": True, "message": getattr(response, 'message', 'Success')}
        else:
            return {"success": False, "error_message": getattr(response, 'message', 'Unknown Error')}
    except grpc.RpcError as e:
        err_msg = f"gRPC Error: {e.code().name} - {e.details()}"
        logger.error(f"gRPC Error calling CMU IdentityDelete: {err_msg}")
        return {"success": False, "error_message": err_msg}
    except Exception as e:
        logger.error(f"Error calling CMU IdentityDelete: {e}", exc_info=True)
        return {"success": False, "error_message": str(e)}

def delete_from_vault(path: str, key: str = "") -> Dict[str, Any]:
    if not _stub:
        logger.warning("CMU connector not initialized. Cannot delete from vault.")
        return {"success": False, "error_message": "Connector not initialized"}
        
    try:
        request = _cmu_pb2.VaultDeleteRequest(path=path, key=key)
        response = _stub.VaultDelete(request, timeout=60, metadata=(('x-client-id', 'HAU'),))
        
        if response.success:
            return {"success": True, "message": getattr(response, 'message', 'Success')}
        else:
            return {"success": False, "error_message": getattr(response, 'message', 'Unknown Error')}
    except grpc.RpcError as e:
        err_msg = f"gRPC Error: {e.code().name} - {e.details()}"
        logger.error(f"gRPC Error calling CMU VaultDelete: {err_msg}")
        return {"success": False, "error_message": err_msg}
    except Exception as e:
        logger.error(f"Error calling CMU VaultDelete: {e}", exc_info=True)
        return {"success": False, "error_message": str(e)}
