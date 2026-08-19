import logging
import grpc
import sys
import os
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

_channel = None
_stub = None
_cmc_service_pb2 = None
_cmc_service_pb2_grpc = None

MAX_MESSAGE_LENGTH = 50 * 1024 * 1024

def init_cmc_connector(config: Dict[str, Any]):
    global _channel, _stub, _cmc_service_pb2, _cmc_service_pb2_grpc
    if _channel:
        return

    generated_path = config.get("paths", {}).get("cmc_generated_stubs_path")
    if not generated_path:
        logger.error("cmc_generated_stubs_path must be configured in settings.yaml paths section")
        return
        
    if generated_path not in sys.path:
        sys.path.insert(0, generated_path)

    try:
        import cmc_service_pb2
        import cmc_service_pb2_grpc
        _cmc_service_pb2 = cmc_service_pb2
        _cmc_service_pb2_grpc = cmc_service_pb2_grpc
    except ImportError as e:
        logger.critical(f"Failed to import CMC gRPC stubs. Ensure they are generated: {e}", exc_info=True)
        return

    try:
        cmc_config = config.get("connectors", {}).get("cmc", {})
        host = cmc_config.get("host")
        port = cmc_config.get("port")
        if not host or not port:
            raise ValueError("CMC host or port not found in configuration.")
        cmc_endpoint = f"{host}:{port}"

        channel_options = [
            ('grpc.max_receive_message_length', MAX_MESSAGE_LENGTH),
            ('grpc.max_send_message_length', MAX_MESSAGE_LENGTH),
        ]
        _channel = grpc.insecure_channel(cmc_endpoint, options=channel_options)
        _stub = _cmc_service_pb2_grpc.CmdConnectorServiceStub(_channel)
        logger.info(f"CMC gRPC connector initialized for endpoint: {cmc_endpoint}")

    except Exception as e:
        logger.critical(f"Failed to initialize CMC gRPC channel: {e}", exc_info=True)
        _channel = None
        _stub = None

def get_segment_a_site(segment_id: int) -> Optional[Dict[str, Any]]:
    if not _stub:
        logger.warning("CMC connector not initialized. Cannot get segment A-site.")
        return None

    try:
        from google.protobuf.json_format import MessageToDict
        request = _cmc_service_pb2.GetSegmentASiteRequest(segment_id=segment_id)
        response = _stub.GetSegmentASite(request, timeout=20, metadata=(('client_application', 'HAU'),))

        if response.success and response.segment_data:
            segment_dict = MessageToDict(response.segment_data, preserving_proto_field_name=True)
            return {"success": True, "segment_data": segment_dict}
        else:
            return {"success": False, "error_message": getattr(response, 'error_message', 'Unknown Error')}

    except Exception as e:
        logger.error(f"Error calling CMC GetSegmentASite: {e}", exc_info=True)
        return {"success": False, "error_message": str(e)}

def get_gnid_a_site(gnid_id: int) -> Optional[Dict[str, Any]]:
    if not _stub:
        logger.warning("CMC connector not initialized. Cannot get GNID A-site.")
        return None

    try:
        from google.protobuf.json_format import MessageToDict
        request = _cmc_service_pb2.GetGnidASiteRequest(gnid=gnid_id)
        response = _stub.GetGnidASite(request, timeout=20, metadata=(('client_application', 'HAU'),))

        if response.success and response.site_data:
            site_dict = MessageToDict(response.site_data, preserving_proto_field_name=True)
            return {"success": True, "site_data": site_dict}
        else:
            return {"success": False, "error_message": getattr(response, 'error_message', 'Unknown Error')}

    except Exception as e:
        logger.error(f"Error calling CMC GetGnidASite: {e}", exc_info=True)
        return {"success": False, "error_message": str(e)}

def get_client_basic_info(client_id: int) -> Optional[Dict[str, Any]]:
    if not _stub:
        logger.warning("CMC connector not initialized. Cannot get client basic info.")
        return None

    try:
        request = _cmc_service_pb2.GetClientBasicInfoRequest(client_id=client_id)
        response = _stub.GetClientBasicInfo(request, timeout=20, metadata=(('client_application', 'HAU'),))

        if response.success:
            return {
                "success": True,
                "client_id": response.client_id,
                "client_name": response.client_name,
                "group_id": response.group_id,
                "group_name": response.group_name
            }
        else:
            return {"success": False, "error_message": getattr(response, 'error_message', 'Unknown Error')}

    except Exception as e:
        logger.error(f"Error calling CMC GetClientBasicInfo: {e}", exc_info=True)
        return {"success": False, "error_message": str(e)}
