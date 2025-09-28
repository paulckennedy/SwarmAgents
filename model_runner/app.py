from fastapi import FastAPI
from pydantic import BaseModel
import os
import subprocess
import glob
import shlex

app = FastAPI()


class Prompt(BaseModel):
    prompt: str


def find_model_file():
    model_dir = os.path.join(os.getcwd(), 'models')
    if not os.path.isdir(model_dir):
        return None
    # prefer common ggml/gguf/bin extensions
    patterns = ['*.ggml.*', '*.gguf', '*.bin', '*.bin.*', '*.pt']
    for p in patterns:
        files = glob.glob(os.path.join(model_dir, p))
        if files:
            return files[0]
    # fallback to any file
    files = glob.glob(os.path.join(model_dir, '*'))
    return files[0] if files else None


def find_llama_bin():
    # common places to put the built llama.cpp binary
    candidates = [
        os.path.join(os.getcwd(), 'llama.cpp', 'main'),
        os.path.join(os.getcwd(), 'llama', 'main'),
        '/app/llama.cpp/main',
        '/app/llama/main'
    ]
    for c in candidates:
        if os.path.exists(c) and os.access(c, os.X_OK):
            return c
    return None


@app.post('/generate')
def generate(prompt: Prompt):
    # If a local llama.cpp binary and a model file exist, run it.
    model = find_model_file()
    llama_bin = find_llama_bin()
    if llama_bin and model:
        # Construct a safe command. Limit tokens to a reasonable number by default.
        cmd = [llama_bin, '-m', model, '-p', prompt.prompt, '-n', '128']
        try:
            proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60, text=True)
            output = proc.stdout.strip()
            if not output:
                # sometimes llama.cpp prints to stderr
                output = proc.stderr.strip()
            return {'response': output}
        except subprocess.TimeoutExpired:
            return {'response': '(model-runner) llama.cpp invocation timed out'}
        except Exception as e:
            return {'response': f'(model-runner) llama.cpp invocation failed: {e}'}

    # Fallback: mock response
    text = f"(model-runner-mock) Generated response for: {prompt.prompt}"
    return {'response': text}
