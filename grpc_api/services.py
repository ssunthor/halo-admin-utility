import logging
import grpc
from concurrent import futures
from typing import Dict, Any

from grpc_health.v1 import health, health_pb2, health_pb2_grpc
from grpc_reflection.v1alpha import reflection

try:
    import hau_pb2
    import hau_pb2_grpc
    import sera_standard_pb2
    import sera_standard_pb2_grpc
except ImportError:
    pass

from grpc_api.hau_service import HauServiceServicer
from grpc_api.sera_standard_service import SeraStandardServiceImpl

logger = logging.getLogger(__name__)

def serve(config: Dict[str, Any]):
    max_workers = int(config['system_services']['grpc']['max_workers'])
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=max_workers))
    
    # 1. Register HAU-specific Service
    hau_service = HauServiceServicer(config)
    hau_pb2_grpc.add_HauServiceServicer_to_server(hau_service, server)
    
    # 2. Register SERA Standard Service
    sera_service = SeraStandardServiceImpl(config)
    sera_standard_pb2_grpc.add_SeraAppServiceServicer_to_server(sera_service, server)
    
    # Setup standard Health & Reflection
    health_servicer = health.HealthServicer()
    health_pb2_grpc.add_HealthServicer_to_server(health_servicer, server)
    health_servicer.set("hau.HauService", health_pb2.HealthCheckResponse.ServingStatus.SERVING)
    health_servicer.set("sera.standard.v1.SeraAppService", health_pb2.HealthCheckResponse.ServingStatus.SERVING)
    
    reflection.enable_server_reflection((
        hau_pb2.DESCRIPTOR.services_by_name['HauService'].full_name,
        sera_standard_pb2.DESCRIPTOR.services_by_name['SeraAppService'].full_name,
        health_pb2.DESCRIPTOR.services_by_name['Health'].full_name, 
        reflection.SERVICE_NAME
    ), server)
    
    address = f"{config['system_services']['grpc']['host']}:{config['system_services']['grpc']['port']}"
    server.add_insecure_port(address)
    logger.info(f"HAU Global gRPC server started on {address}")
    server.start()
    server.wait_for_termination()
