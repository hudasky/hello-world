import os
import subprocess
from dotenv import load_dotenv
from anthropic import Anthropic
from pathlib import Path
load_dotenv(override=True)
MODEL = os.environ["MODEL_ID"]
WORKDIR = Path.cwd()
client=Anthropic(base_url=os.getenv("ANTHROPIC_BASE_URL"))
SYSTEM =f"你是一个位于{os.getcwd()}的编码助手，使用bash来解决任务，直接执行，不要解释"
TOOLS=[
    {
    "name":"bash","description":"运行shell命令","input_schema":{"type":"object","properties":{"command":{"type":"string"}},"requiered":["command"] }
    },
    {
    "name":"read_file","description":"读取文件内容","input_schema":{"type":"object","properties":{"path":{"type":"string"},"limit":{"type":"integer"}},"requiered":["path"]}
    },
    {
    "name":"write_file","description":"写入文件内容","input_schema":{"type":"object","properties":{"path":{"type":"string"},"content":{"type":"string"}},"requiered":["path","content"]}
    },
    {
    "name":"edit_file","description":"替换文件中的文本","input_schema":{"type":"object","properties":{"path":{"type":"string"},"old_text":{"type":"string"},"new_text":{"type":"string"}},"requiered":["path","old_text","new_text"]}
    },
    {
    "name":"glob","description":"查找匹配glob模式的文件","input_schema":{"type":"object","properties":{"pattern":{"type":"string"}},"requiered":["pattern"]}
    },
    ]

def safe_path(p:str)->str:
    path=(WORKDIR / p).resolve()
    if not path.is_relative_to(WORKDIR):
        raise ValueError(f"路径越界: {p}")
    return path
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
def run_read(path:str,limit:int|None=None)->str:
    try:
        lines=safe_path(path).read_text().splitlines()
        if limit and limit < len(lines):
            lines=lines[:limit] + [f"... ({len(lines) - limit} more lines)"]
        return "\n".join(lines)
    except Exception as e:
        return f"Error: {e}"
def run_write(path:str, content:str)->str:
    try:
        file_path=safe_path(path)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content)
        return f"此次写入{len(content)}个bytes到{path}"
    except Exception as e:
        return f"Error: {e}"
def run_edit(path:str, old_content:str, new_content:str)->str:
    try:
        file_path=safe_path(path)
        content=file_path.read_text()
        if old_content not in content:
            return "Error: 旧内容未在文件中找到"
        file_path.write_text(content.replace(old_content, new_content,1))
        return f"在{path}中编辑成功"
    except Exception as e:
        return f"Error: {e}"
def run_glob(pattern:str)->str:
    import glob as g
    results = []
    try:
        for match in g.glob(pattern, root_dir=WORKDIR):
            if (WORKDIR / match).resolve().is_relative_to(WORKDIR):
                results.append(match)
        return "\n".join(results) if results else "(没有匹配的文件)"
    except Exception as e:
        return f"Error: {e}"
TOOL_HANDLERS={
    "bash":run_bash,
    "read_file":run_read,
    "write_file":run_write,
    "edit_file":run_edit,
    "glob":run_glob
}
def agent_loop(messages:list):
    while True:
        response=client.messages.create(
            model=MODEL,
            messages=messages,
            system=SYSTEM,
            tools=TOOLS,
            max_tokens=2000,
        )
        messages.append({"role":"assistant","content":response.content})
        if response.stop_reason != "tool_use":
            return
        results=[]
        for block in response.content:
            if block.type=="tool_use": 
                print(f"\033[33m$ {block.name}\033[0m")
                handler=TOOL_HANDLERS.get(block.name)
                output=handler(**block.input) if handler else f"Error: 未知工具 {block.name}"
                print(output[:200])
                results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": output
                })
        messages.append({"role":"user","content":results})
if __name__=="__main__":
    print("欢迎使用编码助手，输入exit或q退出")
    history=[]
    while True:
        try:
            query=input("\033[32m>>> \033[0m")
        except (EOFError, KeyboardInterrupt):
            break
        if query.strip().lower() in ["exit","q"]:
            break
        history.append({"role":"user","content":query})
        agent_loop(history)
        response_content=history[-1]["content"]
        if isinstance(response_content, list):
            for block in response_content:
                if getattr(block,"type",None)=="text":
                    print(block.text)
