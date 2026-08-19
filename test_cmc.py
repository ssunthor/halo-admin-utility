import sys
sys.path.insert(0, "/ai/assets/protos/cmd_connector/generated")
import cmc_service_pb2
print([method for method in dir(cmc_service_pb2) if 'Request' in method])
