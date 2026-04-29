import os
os.environ['KMP_DUPLICATE_LIB_OK'] = 'TRUE'

print('=== CUDA (NVIDIA) ===')
try:
    import torch
    print(f'PyTorch CUDA available: {torch.cuda.is_available()}')
    print(f'CUDA version: {torch.version.cuda}')
    if torch.cuda.is_available():
        print(f'GPU: {torch.cuda.get_device_name(0)}')
        print(f'GPU count: {torch.cuda.device_count()}')
    else:
        print('No NVIDIA CUDA GPU detected')
except Exception as e:
    print(f'Error: {e}')

print()
print('=== OpenVINO Devices ===')
try:
    import openvino as ov
    core = ov.Core()
    for dev in core.available_devices:
        name = core.get_property(dev, "FULL_DEVICE_NAME")
        print(f'  {dev}: {name}')
except Exception as e:
    print(f'Error: {e}')

print()
print('=== System GPU Info ===')
import subprocess
try:
    result = subprocess.run(
        ['wmic', 'path', 'win32_VideoController', 'get', 'Name,AdapterRAM,DriverVersion'],
        capture_output=True, text=True, timeout=10
    )
    print(result.stdout.strip())
except Exception as e:
    print(f'Error: {e}')

print()
print('=== PyTorch Backend ===')
try:
    import torch
    print(f'PyTorch version: {torch.__version__}')
    print(f'CPU threads: {torch.get_num_threads()}')
    if hasattr(torch.backends, 'mps'):
        print(f'MPS available: {torch.backends.mps.is_available()}')
except Exception as e:
    print(f'Error: {e}')
