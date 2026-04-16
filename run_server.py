"""启动服务器脚本"""
import sys
import os

os.chdir(r"C:\Users\ahuyk\ai-test-generator")
sys.path.insert(0, r"C:\Users\ahuyk\ai-test-generator")

import uvicorn
from main import app

print("Starting server on port 8000...")
print(f"Python: {sys.executable}")
print(f"CWD: {os.getcwd()}")

uvicorn.run(app, host="0.0.0.0", port=8000, reload=False)
