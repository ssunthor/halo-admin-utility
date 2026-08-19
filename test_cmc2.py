import sys
sys.path.insert(0, "/ai/assets/protos/cmd_connector/generated")
import cmc_service_pb2
print([field.name for field in cmc_service_pb2.GetClientBasicInfoRequest.DESCRIPTOR.fields])
print([field.name for field in cmc_service_pb2.GetClientBasicInfoResponse.DESCRIPTOR.fields])
