"""DevFlow Web UI"""

from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
from devflow.config import load_config
from devflow.core.agent import Agent
from devflow.llm import DeepSeekClient
from devflow.tools.base import create_tool_registry, set_safe_root

app = FastAPI()

class TaskRequest(BaseModel):
    task: str
    repo_path: str = "."

@app.get("/", response_class=HTMLResponse)
async def index():
    return PAGE

@app.post("/api/run")
async def run_task(req: TaskRequest):
    config = load_config()
    if not config.llm.api_key.get_secret_value():
        return JSONResponse({"error": "请设置 DEEPSEEK_API_KEY"}, status_code=400)
    repo_path = Path(req.repo_path).resolve()
    set_safe_root(repo_path)
    client = DeepSeekClient(config.llm)
    tools = create_tool_registry()
    agent = Agent(client, tools, config=config)
    result = await agent.run(req.task, repo_path)
    return {
        "success": result.success,
        "error": result.error,
        "steps": [{"index": sr.step.index, "description": sr.step.description[:120], "success": sr.success, "output": (sr.output or "")[:300]} for sr in result.step_results] if result.plan else [],
        "files_modified": result.files_modified,
        "verify": {"passed": result.verify_result.passed if result.verify_result else True, "errors": [e.message for e in result.verify_result.errors] if result.verify_result else []},
    }

def main():
    import uvicorn
    uvicorn.run("devflow.api.server:app", host="0.0.0.0", port=8000, reload=True)

PAGE = """<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>DevFlow - AI 编程助手</title>
<style>
:root{--bg:#0a0a0a;--s1:#111111;--s2:#1a1a1a;--s3:#252525;--bdr:#2a2a2a;--t1:#ededed;--t2:#999;--t3:#666;--ac:#3b82f6;--gr:#10b981;--rd:#ef4444;--r:14px}
*{box-sizing:border-box;margin:0;padding:0}
body{font:15px/1.7 -apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif;background:var(--bg);color:var(--t1);min-height:100vh}
::-webkit-scrollbar{width:5px}::-webkit-scrollbar-track{background:transparent}::-webkit-scrollbar-thumb{background:var(--s3);border-radius:3px}

/* 导航栏 */
nav{display:flex;align-items:center;justify-content:space-between;padding:16px 36px;background:var(--s1);border-bottom:1px solid var(--bdr)}
nav .logo{font-size:18px;font-weight:700;letter-spacing:-.3px}
nav .logo span{color:var(--ac)}
nav .logo .v{font-size:11px;background:var(--ac);color:#fff;padding:2px 9px;border-radius:12px;margin-left:10px}
nav .status{font-size:13px;color:var(--t2);display:flex;gap:20px}
nav .status b{color:var(--t1)}

/* 主布局 */
.container{max-width:1000px;margin:0 auto;padding:32px 40px}

/* 统计卡片 */
.stats{display:grid;grid-template-columns:repeat(4,1fr);gap:18px;margin-bottom:36px}
.stat{background:var(--s1);border:1px solid var(--bdr);border-radius:var(--r);padding:24px 22px}
.stat .v{font-size:32px;font-weight:700;line-height:1.1;margin-bottom:6px}
.stat .l{font-size:13px;color:var(--t3)}

/* 任务卡片 */
.card{background:var(--s1);border:1px solid var(--bdr);border-radius:var(--r);padding:28px 30px;margin-bottom:24px}
.card.active{border-color:var(--ac);box-shadow:0 0 0 1px var(--ac)}
.card h3{font-size:16px;font-weight:600;margin-bottom:18px}

/* 输入框 */
textarea{width:100%;background:var(--bg);color:var(--t1);border:1px solid var(--bdr);border-radius:10px;padding:18px 20px;font:inherit;font-size:15px;resize:vertical;min-height:130px;transition:border .2s;line-height:1.8}
textarea:focus{outline:none;border-color:var(--ac);box-shadow:0 0 0 3px rgba(59,130,246,.1)}
textarea::placeholder{color:var(--t3)}

/* 按钮 */
.btn{display:inline-flex;align-items:center;gap:8px;background:var(--ac);color:#fff;border:none;padding:12px 28px;border-radius:10px;font:inherit;font-size:15px;font-weight:500;cursor:pointer;transition:all .15s}
.btn:hover{filter:brightness(1.1);transform:translateY(-1px)}
.btn:active{transform:translateY(0)}
.btn:disabled{opacity:.3;cursor:not-allowed;transform:none}
.spin{display:inline-block;width:15px;height:15px;border:2px solid rgba(255,255,255,.2);border-top-color:#fff;border-radius:50%;animation:sp .6s linear infinite}
@keyframes sp{to{transform:rotate(360deg)}}

/* 模板 */
.templates{display:flex;flex-wrap:wrap;gap:10px;margin:14px 0 0}
.template{font-size:13px;padding:6px 14px;background:var(--s2);border:1px solid var(--bdr);border-radius:22px;cursor:pointer;color:var(--t2);transition:all .15s;white-space:nowrap}
.template:hover{color:var(--t1);border-color:var(--ac);background:rgba(59,130,246,.08)}

/* 操作栏 */
.actions{display:flex;align-items:center;justify-content:space-between;margin-top:20px}
.hint{font-size:13px;color:var(--t3)}
.hint kbd{display:inline-block;background:var(--s2);border:1px solid var(--bdr);border-radius:5px;padding:1px 7px;font:inherit;font-size:12px}

/* 结果区 */
.step{display:flex;gap:14px;padding:14px 0;border-bottom:1px solid var(--bdr);align-items:flex-start}
.step:last-child{border:none}
.step-badge{width:28px;height:28px;border-radius:14px;display:flex;align-items:center;justify-content:center;font-size:12px;flex-shrink:0;margin-top:2px;font-weight:700}
.badge-ok{background:rgba(16,185,129,.12);color:var(--gr)}
.badge-fail{background:rgba(239,68,68,.12);color:var(--rd)}
.step-body{flex:1;min-width:0}
.step-desc{font-size:14px;line-height:1.6}
.step-output{font-size:13px;color:var(--t3);margin-top:4px;font-family:"SF Mono","Fira Code","Cascadia Code",monospace;background:var(--bg);padding:6px 10px;border-radius:6px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}

/* 文件列表 */
.file-list{margin-top:4px}
.file-item{display:flex;align-items:center;gap:8px;padding:7px 12px;font-size:13px;color:var(--t3);background:var(--s2);border-radius:8px;margin:4px 0}
.file-item span{color:var(--t2);font-family:"SF Mono","Fira Code",monospace;font-size:12px}

/* 进度条 */
.progress-wrap{height:5px;background:var(--s2);border-radius:5px;margin:14px 0;overflow:hidden}
.progress-fill{height:100%;background:var(--ac);border-radius:5px;transition:width .5s}

/* 错误 */
.errors{margin-top:12px;font-size:14px;color:var(--rd)}
.errors div{padding:4px 0}

/* 工具页 */
.tool-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:14px}
.tool-card{background:var(--s2);padding:18px 20px;border-radius:var(--r);border:1px solid var(--bdr)}
.tool-card .name{font-size:15px;font-weight:600;margin-bottom:4px}
.tool-card .desc{font-size:13px;color:var(--t3);line-height:1.5}

/* 关于页 */
.about-info{font-size:14px;color:var(--t2);line-height:2.4}

/* 底部 */
footer{text-align:center;padding:32px;font-size:13px;color:var(--t3)}
</style>
</head>
<body>

<nav>
  <div class="logo">Dev<span>Flow</span><span class="v">v0.1</span></div>
  <div class="status">周预算 <b>$20</b> · 5小时预算 <b>$3.5</b> · 模型 <b>V4 Flash</b></div>
</nav>

<div class="container">

<!-- 统计 -->
<div class="stats">
  <div class="stat"><div class="v" style="color:var(--ac)">9</div><div class="l">可用工具</div></div>
  <div class="stat"><div class="v" style="color:var(--gr)">70%</div><div class="l">测试覆盖率</div></div>
  <div class="stat"><div class="v" style="color:#f59e0b">$20</div><div class="l">周预算上限</div></div>
  <div class="stat"><div class="v">25</div><div class="l">测试全部通过</div></div>
</div>

<!-- 任务区 -->
<div class="card active" id="task-area">
  <h3>编程任务</h3>
  <textarea id="input" placeholder="描述你的编程任务...&#10;&#10;例如：在 src/api/ 下添加一个 /health 健康检查端点，返回 {&quot;status&quot;: &quot;ok&quot;}&#10;例如：创建 utils/date.py，实现日期格式化和时间差计算函数"></textarea>
  <div class="templates">
    <span class="template" onclick='fill("创建 hello.py，包含一个返回 hello world 的函数")'>👋 创建 Hello World</span>
    <span class="template" onclick='fill("在 src/api/ 下添加 /health GET 健康检查端点")'>🏥 添加健康检查</span>
    <span class="template" onclick='fill("给项目添加 pytest 单元测试")'>🧪 添加单元测试</span>
    <span class="template" onclick='fill("创建 requirements.txt 列出所有依赖")'>📦 导出依赖清单</span>
    <span class="template" onclick='fill("实现一个递归遍历目录并统计文件数量的函数")'>🔧 写工具函数</span>
  </div>
  <div class="actions">
    <div class="hint">按 <kbd>Ctrl</kbd> + <kbd>Enter</kbd> 快速提交</div>
    <button class="btn" onclick="run()" id="go">开始执行</button>
  </div>
</div>

<!-- 结果区 -->
<div class="card" style="display:none" id="result-area">
  <h3 id="rTitle"></h3>
  <div class="progress-wrap" id="progressWrap" style="display:none"><div class="progress-fill" id="progress" style="width:0"></div></div>
  <div id="steps"></div>
  <div class="file-list" id="files"></div>
  <div class="errors" id="errors"></div>
</div>

<!-- 工具区 -->
<div class="card" id="tools-area" style="display:none">
  <h3>9 个可用工具</h3>
  <div class="tool-grid">
    <div class="tool-card"><div class="name">📖 读取文件</div><div class="desc">读取文件内容，支持指定行范围，自动过滤越界路径</div></div>
    <div class="tool-card"><div class="name">✏️ 写入文件</div><div class="desc">创建新文件或覆写已有文件，自动创建父目录</div></div>
    <div class="tool-card"><div class="name">🔧 精确编辑</div><div class="desc">精确字符串替换，要求原字符串在文件中唯一匹配</div></div>
    <div class="tool-card"><div class="name">⚡ 执行命令</div><div class="desc">Shell 命令执行，30秒超时，危险命令自动拦截</div></div>
    <div class="tool-card"><div class="name">🔍 代码搜索</div><div class="desc">正则表达式搜索项目代码，支持文件类型过滤</div></div>
    <div class="tool-card"><div class="name">📊 查看改动</div><div class="desc">Git diff 查看工作区未暂存和已暂存的代码改动</div></div>
    <div class="tool-card"><div class="name">📜 提交历史</div><div class="desc">查看最近的 Git 提交记录，支持自定义数量</div></div>
    <div class="tool-card"><div class="name">📌 仓库状态</div><div class="desc">查看 Git 仓库当前状态，列出修改/新增/删除文件</div></div>
  </div>
</div>

<!-- 关于 -->
<div class="card" id="about-area" style="display:none">
  <h3>关于 devflow-ai</h3>
  <div class="about-info">
    <div>核心模型：<b>DeepSeek V4 Flash</b> · 1M 上下文窗口</div>
    <div>许可证：<b>MIT</b> · Python 3.11+</div>
    <div>接口形式：CLI + Web UI</div>
    <div>内置预算保护：$20 / 周 · $3.5 / 5小时</div>
    <div>开源地址：github.com/你的用户名/devflow-ai</div>
  </div>
</div>

</div>

<footer>DeepSeek V4 Flash · 极低成本 · MIT 开源</footer>

<script>
function fill(t){document.getElementById('input').value=t;document.getElementById('input').focus()}
function show(id){['task-area','tools-area','about-area'].forEach(x=>document.getElementById(x).style.display=x===id?'block':'none')}

async function run(){
  var t=document.getElementById('input').value.trim();if(!t)return;
  var btn=document.getElementById('go'),card=document.getElementById('result-area');
  btn.disabled=true;btn.innerHTML='<span class="spin"></span> 分析中';
  card.style.display='block';
  document.getElementById('rTitle').innerHTML='<span style="display:flex;align-items:center;gap:10px"><span class="spin"></span> Agent 正在分析任务...</span>';
  document.getElementById('steps').innerHTML='';
  document.getElementById('files').innerHTML='';
  document.getElementById('errors').innerHTML='';
  document.getElementById('progressWrap').style.display='block';
  document.getElementById('progress').style.width='25%';
  try{
    var r=await fetch('/api/run',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({task:t,repo_path:'.'})});
    document.getElementById('progress').style.width='85%';
    var d=await r.json();
    document.getElementById('progress').style.width='100%';
    setTimeout(function(){document.getElementById('progressWrap').style.display='none'},800);
    if(d.success){document.getElementById('rTitle').innerHTML='任务执行完成'}else{document.getElementById('rTitle').innerHTML='任务执行失败: '+(d.error||'未知错误')}
    var h='';
    (d.steps||[]).forEach(function(s){
      h+='<div class="step"><div class="step-badge '+(s.success?'badge-ok':'badge-fail')+'">'+(s.success?'OK':'!')+'</div><div class="step-body"><div class="step-desc">步骤 '+(s.index||'?')+': '+s.description+'</div>'+(s.output?'<div class="step-output">'+s.output+'</div>':'')+'</div></div>';
    });
    document.getElementById('steps').innerHTML=h||'<div style="color:var(--t3);font-size:14px;padding:12px 0">无执行步骤</div>';
    var fh='';
    (d.files_modified||[]).forEach(function(f){fh+='<div class="file-item">📄 <span>'+f+'</span></div>'});
    if(fh)document.getElementById('files').innerHTML='<div style="font-size:14px;font-weight:600;margin:14px 0 8px">修改的文件</div>'+fh;
    if(d.verify&&d.verify.errors&&d.verify.errors.length){document.getElementById('errors').innerHTML='<div style="font-size:14px;font-weight:600;margin:10px 0 6px">验证错误</div>'+d.verify.errors.map(function(e){return '<div>'+e+'</div>'}).join('')}
  }catch(e){document.getElementById('rTitle').innerHTML='网络错误: '+e.message;document.getElementById('progressWrap').style.display='none'}
  btn.disabled=false;btn.innerHTML='开始执行';
}
document.addEventListener('keydown',function(e){if((e.ctrlKey||e.metaKey)&&e.key==='Enter'){e.preventDefault();run()}});
</script>
</body>
</html>"""
