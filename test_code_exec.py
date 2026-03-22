import os
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()
genai.configure(api_key=os.environ["GEMINI_API_KEY"])

model = genai.GenerativeModel(
    model_name="gemini-3.1-pro-preview",
    tools="code_execution"
)

chat = model.start_chat()
resp = chat.send_message("חשב את (3+4j) * (1-2j) באמצעות פייתון כולל הקוד.")

print("TEXT PROPERTY:")
print(resp.text)
print("-" * 40)
print("PARTS:")
for i, part in enumerate(resp.parts):
    print(f"Part {i}: {type(part)}")
    if hasattr(part, "executable_code"):
        print("-- CODE --")
        print(part.executable_code.code)
    if hasattr(part, "code_execution_result"):
        print("-- RESULT --")
        print(part.code_execution_result.output)
