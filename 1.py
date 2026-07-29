import os
import subprocess
from dotenv import load_dotenv
from anthropic import Anthropic
load_dotenv(override=True)
MODEL = os.environ["MODEL_ID"]
client=Anthropic(base_url=os.getenv("ANTHROPIC_BASE_URL"))
SYSTEM =f"你是一个位于{os.getcwd()}的编码助手，使用bash来解决任务，直接执行，不要解释"
TOOLS=[{
    "name":"bash",
    "description":"运行shell命令",
    "input_schema":{
        "type":"object",
        "properties":{"command":{"type":"string"}},
        "requiered":["command"]
    }
}]
def run_bash(command:str)->str:
    dangerous=["rm -rf /","sudo","shutdown","reboot","> /dev/"]
    if any(d in command for d in dangerous):
        return "Error: 危险命令已被阻止"
    try:
        o=subprocess.run(command,shell=True,cwd=os.getcwd(),
                         capture_output=True,text=True,
                         timeout=120)
        output=(o.stdout+o.stderr).strip()
        return output[:50000] if output else "no output"
    except subprocess.TimeoutExpired:
        return "Error: Timeout (120s)"
    except OSError as e:
        return f"Error: {e}"
def agent_loop(messages:list):
    while True:
       
        # 执行工具调用，收集结果
