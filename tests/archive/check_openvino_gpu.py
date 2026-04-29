import os
os.environ['KMP_DUPLICATE_LIB_OK'] = 'TRUE'

print('=== OpenVINO GPU Device Test ===')
try:
    import openvino as ov
    core = ov.Core()
    print(f'Available devices: {core.available_devices}')

    if 'GPU' in core.available_devices:
        gpu_name = core.get_property("GPU", "FULL_DEVICE_NAME")
        print(f'GPU device name: {gpu_name}')

        print('\n--- Testing GPU with simple model ---')
        try:
            from openvino_genai import VLMPipeline, ChatHistory
            model_path = r"D:\projects\claude\urlparser\models\qwen3-vl-2b-int4"
            print(f'Loading model on GPU: {model_path}')
            pipeline = VLMPipeline(model_path, device="GPU")
            print('Model loaded on GPU successfully!')

            history = ChatHistory()
            history.append({"role": "user", "content": "你好，请用中文简单介绍一下自己"})
            result = pipeline.generate(history, max_new_tokens=100)
            text = str(result.texts[0]).strip()
            print(f'GPU output: {text[:200]}')
            print(f'GPU output length: {len(text)}')
            del pipeline
        except Exception as e:
            print(f'GPU test failed: {e}')
            print(f'Error type: {type(e).__name__}')

        print('\n--- Testing CPU for comparison ---')
        try:
            from openvino_genai import VLMPipeline, ChatHistory
            model_path = r"D:\projects\claude\urlparser\models\qwen3-vl-2b-int4"
            print(f'Loading model on CPU: {model_path}')
            pipeline = VLMPipeline(model_path, device="CPU")
            print('Model loaded on CPU successfully!')

            history = ChatHistory()
            history.append({"role": "user", "content": "你好，请用中文简单介绍一下自己"})
            result = pipeline.generate(history, max_new_tokens=100)
            text = str(result.texts[0]).strip()
            print(f'CPU output: {text[:200]}')
            print(f'CPU output length: {len(text)}')
            del pipeline
        except Exception as e:
            print(f'CPU test failed: {e}')

except ImportError as e:
    print(f'OpenVINO not installed: {e}')
except Exception as e:
    print(f'Error: {e}')
