import os
import sys
import logging

logger = logging.getLogger(__name__)

def check_and_generate_stubs(config: dict) -> tuple:
    UTILITY_NAME = "hau"
    
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
    MODULE_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, '..'))

    paths_config = config.get('paths', {})
    
    # Target Protos
    utility_proto_src_dir = os.path.join(MODULE_ROOT, paths_config.get("proto_source_dir", "grpc_api/protos"))
    utility_proto_file = os.path.join(utility_proto_src_dir, f"{UTILITY_NAME}.proto")
    
    sera_proto_src_dir = paths_config.get("sera_proto_source_dir")
    if not sera_proto_src_dir:
        logger.critical("'paths.sera_proto_source_dir' is not defined in config.")
        return False, False
        
    sera_proto_file = os.path.join(sera_proto_src_dir, "sera_standard.proto")
    
    output_dir = paths_config.get('generated_stubs_path')
    if not output_dir:
        logger.critical("'paths.generated_stubs_path' is not defined in config.")
        return False, False
    
    expected_utility_stub = os.path.join(output_dir, f'{UTILITY_NAME}_pb2.py')
    expected_sera_stub = os.path.join(output_dir, 'sera_standard_pb2.py')
    
    regenerate = False
    if not os.path.exists(expected_utility_stub) or not os.path.exists(expected_sera_stub):
        regenerate = True
        logger.info("gRPC stubs not found. Will generate.")
    else:
        if os.path.exists(utility_proto_file) and os.path.getmtime(utility_proto_file) > os.path.getmtime(expected_utility_stub):
            regenerate = True
            logger.info(f"Source {UTILITY_NAME}.proto file is newer than generated stubs. Will regenerate.")
        elif os.path.exists(sera_proto_file) and os.path.getmtime(sera_proto_file) > os.path.getmtime(expected_sera_stub):
            regenerate = True
            logger.info("Source sera_standard.proto file is newer than generated stubs. Will regenerate.")
    
    if regenerate:
        logger.info(f"--- {UTILITY_NAME.upper()} gRPC Stub Generation ---")
        logger.info(f"Outputting to shared location: {output_dir}")
        try:
            os.makedirs(output_dir, exist_ok=True)
            path_parts = output_dir.strip(os.sep).split(os.sep)
            current_path = ""
            if output_dir.startswith(os.sep):
                current_path = os.sep
            for part in path_parts:
                if not part: continue
                current_path = os.path.join(current_path, part)
                if current_path and os.path.isdir(current_path):
                    init_file = os.path.join(current_path, "__init__.py")
                    if not os.path.exists(init_file):
                        with open(init_file, "w") as f: pass

            import grpc_tools
            from grpc_tools import protoc
            proto_include_path = os.path.join(os.path.dirname(grpc_tools.__file__), '_proto')
            
            for p_file, p_dir in [(utility_proto_file, utility_proto_src_dir), (sera_proto_file, sera_proto_src_dir)]:
                if not os.path.exists(p_file):
                    logger.warning(f"Proto file not found: {p_file}")
                    continue

                command = [
                    'grpc_tools.protoc',
                    f'--proto_path={p_dir}',
                    f'--proto_path={proto_include_path}',
                    f'--python_out={output_dir}',
                    f'--grpc_python_out={output_dir}',
                    p_file,
                ]
                
                exit_code = protoc.main(command)
                if exit_code != 0:
                    raise RuntimeError(f"protoc generation failed for {p_file} with exit code {exit_code}")
            
            logger.info("Successfully generated stubs.")
        except Exception as e:
            logger.critical(f"FATAL: Stub generation failed: {e}", exc_info=True)
            return False, False
    else:
        logger.info("gRPC stubs are up-to-date.")
    
    return True, regenerate
